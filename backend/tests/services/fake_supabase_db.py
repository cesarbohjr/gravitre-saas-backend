"""In-memory Supabase/PostgREST stand-in that records every write.

Just enough of the query-builder surface for the services the brain uses:
``table().select/insert/upsert/update/delete`` with ``eq``/``filter`` and the
usual modifiers, plus ``rpc()``. Every mutating ``execute()`` is appended to
``writes``; ``snapshot()`` returns the table contents for equality checks.
"""
from __future__ import annotations

import copy
import threading
from types import SimpleNamespace
from typing import Any


class _Query:
    def __init__(self, db: "FakeSupabaseDB", table: str) -> None:
        self._db = db
        self._table = table
        self._op = "select"
        self._payload: Any = None
        self._filters: list[tuple[str, Any]] = []
        self._limit: int | None = None

    # -- verbs -----------------------------------------------------------------
    def select(self, *_a: Any, **_k: Any) -> "_Query":
        self._op = "select"
        return self

    def insert(self, payload: Any, *_a: Any, **_k: Any) -> "_Query":
        self._op, self._payload = "insert", payload
        return self

    def upsert(self, payload: Any, *_a: Any, **_k: Any) -> "_Query":
        self._op, self._payload = "upsert", payload
        return self

    def update(self, payload: Any, *_a: Any, **_k: Any) -> "_Query":
        self._op, self._payload = "update", payload
        return self

    def delete(self, *_a: Any, **_k: Any) -> "_Query":
        self._op = "delete"
        return self

    # -- filters / modifiers -----------------------------------------------------
    def eq(self, column: str, value: Any) -> "_Query":
        self._filters.append((column, value))
        return self

    def limit(self, n: int, *_a: Any, **_k: Any) -> "_Query":
        self._limit = n
        return self

    def __getattr__(self, _name: str) -> Any:
        # order, gt, neq, in_, filter, single, maybe_single, ...: accepted, ignored.
        return lambda *_a, **_k: self

    def _matches(self, row: dict[str, Any]) -> bool:
        return all(str(row.get(col)) == str(val) for col, val in self._filters)

    def execute(self) -> SimpleNamespace:
        db = self._db
        with db.lock:
            if self._op == "select":
                rows = db.tables.get(self._table, [])
                found = [copy.deepcopy(r) for r in rows if self._matches(r)]
                if self._limit is not None:
                    found = found[: self._limit]
                return SimpleNamespace(data=found)
            db.writes.append((self._op, self._table, copy.deepcopy(self._payload), list(self._filters)))
            rows = db.tables.setdefault(self._table, [])
            if self._op in {"insert", "upsert"}:
                items = self._payload if isinstance(self._payload, list) else [self._payload]
                for item in items:
                    rows.append(copy.deepcopy(item))
                return SimpleNamespace(data=copy.deepcopy(items))
            if self._op == "update":
                hit = []
                for row in rows:
                    if self._matches(row):
                        row.update(copy.deepcopy(self._payload))
                        hit.append(copy.deepcopy(row))
                return SimpleNamespace(data=hit)
            if self._op == "delete":
                kept = [r for r in rows if not self._matches(r)]
                gone = len(rows) - len(kept)
                db.tables[self._table] = kept
                return SimpleNamespace(data=[{}] * gone)
        return SimpleNamespace(data=[])


class _Rpc:
    def __init__(self, db: "FakeSupabaseDB", name: str, params: Any) -> None:
        self._db, self._name, self._params = db, name, params

    def execute(self) -> SimpleNamespace:
        with self._db.lock:
            self._db.writes.append(("rpc", self._name, copy.deepcopy(self._params), []))
        return SimpleNamespace(data=None)


class FakeSupabaseDB:
    def __init__(self) -> None:
        self.tables: dict[str, list[dict[str, Any]]] = {}
        self.writes: list[tuple[str, str, Any, list[tuple[str, Any]]]] = []
        self.lock = threading.RLock()

    def table(self, name: str) -> _Query:
        return _Query(self, name)

    def from_(self, name: str) -> _Query:
        return _Query(self, name)

    def rpc(self, name: str, params: Any = None) -> _Rpc:
        return _Rpc(self, name, params)

    def snapshot(self) -> dict[str, list[dict[str, Any]]]:
        with self.lock:
            return copy.deepcopy(self.tables)
