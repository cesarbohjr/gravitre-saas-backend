"""In-memory Supabase double that honours query filters.

Mocks whose ``eq()`` returns ``self`` let a test pass while the code under test
filters on the wrong column, or not at all. This double applies every ``eq``
filter, enforces primary keys, and makes batch inserts atomic, which is what
PostgREST does. Only the query-builder surface the conversation store uses is
implemented.
"""
from __future__ import annotations

import copy
import uuid
from dataclasses import dataclass
from typing import Any, Callable


class FakeAPIError(Exception):
    """Stands in for postgrest.APIError (e.g. a 23505 unique violation)."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


@dataclass
class FakeResponse:
    data: list[dict[str, Any]]
    error: Any = None


Hook = Callable[["FakeQuery"], None]


class FakeQuery:
    def __init__(self, client: "FakeSupabase", table: str) -> None:
        self.client = client
        self.table = table
        self.op = "select"
        self.payload: Any = None
        self.filters: list[tuple[str, Any]] = []
        self._order: tuple[str, bool] | None = None
        self._limit: int | None = None

    def select(self, *_columns: Any, **_kwargs: Any) -> "FakeQuery":
        self.op = "select"
        return self

    def insert(self, payload: dict[str, Any] | list[dict[str, Any]]) -> "FakeQuery":
        self.op = "insert"
        self.payload = payload
        return self

    def update(self, payload: dict[str, Any]) -> "FakeQuery":
        self.op = "update"
        self.payload = payload
        return self

    def eq(self, column: str, value: Any) -> "FakeQuery":
        self.filters.append((column, value))
        return self

    def order(self, column: str, desc: bool = False) -> "FakeQuery":
        self._order = (column, desc)
        return self

    def limit(self, n: int) -> "FakeQuery":
        self._limit = n
        return self

    def _matches(self, row: dict[str, Any]) -> bool:
        return all(row.get(col) == val for col, val in self.filters)

    def execute(self) -> FakeResponse:
        for hook in list(self.client.hooks):
            hook(self)
        self.client.log.append((self.op, self.table, list(self.filters)))
        rows = self.client.tables.setdefault(self.table, [])
        if self.op == "select":
            found = [copy.deepcopy(r) for r in rows if self._matches(r)]
            if self._order:
                col, desc = self._order
                found.sort(key=lambda r: str(r.get(col) or ""), reverse=desc)
            if self._limit is not None:
                found = found[: self._limit]
            return FakeResponse(found)
        if self.op == "insert":
            batch = self.payload if isinstance(self.payload, list) else [self.payload]
            prepared = []
            existing = {r.get("id") for r in rows}
            for raw in batch:
                row = copy.deepcopy(raw)
                row.setdefault("id", str(uuid.uuid4()))
                if row["id"] in existing or row["id"] in {p["id"] for p in prepared}:
                    # Atomic: nothing from this batch lands.
                    raise FakeAPIError("23505", f"duplicate key value violates unique constraint {self.table}_pkey")
                prepared.append(row)
            rows.extend(prepared)
            return FakeResponse(copy.deepcopy(prepared))
        if self.op == "update":
            changed = []
            for row in rows:
                if self._matches(row):
                    row.update(copy.deepcopy(self.payload))
                    changed.append(copy.deepcopy(row))
            return FakeResponse(changed)
        raise AssertionError(f"unsupported op {self.op}")


class FakeSupabase:
    def __init__(self) -> None:
        self.tables: dict[str, list[dict[str, Any]]] = {}
        self.hooks: list[Hook] = []
        self.log: list[tuple[str, str, list[tuple[str, Any]]]] = []

    def table(self, name: str) -> FakeQuery:
        return FakeQuery(self, name)

    def rows(self, table: str, **match: Any) -> list[dict[str, Any]]:
        return [r for r in self.tables.get(table, []) if all(r.get(k) == v for k, v in match.items())]

    def seed_conversation(self, *, org_id: str, user_id: str, conversation_id: str | None = None) -> str:
        cid = conversation_id or str(uuid.uuid4())
        self.tables.setdefault("conversations", []).append(
            {"id": cid, "org_id": org_id, "user_id": user_id, "message_count": 0}
        )
        return cid
