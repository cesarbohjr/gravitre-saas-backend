"""A tiny PostgREST stand-in over a throwaway cluster, for service code under test.

Implements only what the tests here drive: ``table(t).select(...).eq(...).limit(n)``
and ``table(t).insert(row)``, each ``.execute()``-d as one SQL statement through
psql. Comparisons are not cast, so a malformed uuid fails the way PostgREST does
(an error, not an empty result). Every statement is recorded in ``statements``.
"""
from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

from tests.db.pg_harness import Pg


def _lit(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, dict | list):
        value = json.dumps(value)
    return "'" + str(value).replace("'", "''") + "'"


def _ident(name: str) -> str:
    if not name.replace("_", "").isalnum():
        raise ValueError(f"unsafe identifier {name!r}")
    return f'"{name}"'


class PgRestError(RuntimeError):
    pass


class _Query:
    def __init__(self, client: PgRestClient, table: str) -> None:
        self.client = client
        self.table = table
        self.where: list[str] = []
        self.limit_n: int | None = None
        self.row: dict[str, Any] | None = None

    def select(self, _cols: str = "*") -> _Query:
        return self

    def eq(self, col: str, value: Any) -> _Query:
        self.where.append(f"{_ident(col)} = {_lit(value)}")
        return self

    def limit(self, n: int) -> _Query:
        self.limit_n = int(n)
        return self

    def insert(self, row: dict[str, Any]) -> _Query:
        self.row = dict(row)
        return self

    def execute(self) -> SimpleNamespace:
        t = f"public.{_ident(self.table)}"
        if self.row is not None:
            cols = ", ".join(_ident(c) for c in self.row)
            vals = ", ".join(_lit(v) for v in self.row.values())
            sql = f"WITH ins AS (INSERT INTO {t} ({cols}) VALUES ({vals}) RETURNING *) SELECT row_to_json(ins) FROM ins;"
        else:
            where = (" WHERE " + " AND ".join(self.where)) if self.where else ""
            limit = f" LIMIT {self.limit_n}" if self.limit_n is not None else ""
            sql = f"SELECT row_to_json(r) FROM (SELECT * FROM {t}{where}{limit}) r;"
        return SimpleNamespace(data=self.client.run(sql))


class PgRestClient:
    def __init__(self, pg: Pg) -> None:
        self.pg = pg
        self.statements: list[str] = []

    def table(self, name: str) -> _Query:
        return _Query(self, name)

    def run(self, sql: str) -> list[dict[str, Any]]:
        self.statements.append(sql)
        res = self.pg.psql(sql, check=False)
        if res.returncode != 0:
            raise PgRestError(res.stderr.strip())
        return [json.loads(line) for line in res.stdout.splitlines() if line.strip()]
