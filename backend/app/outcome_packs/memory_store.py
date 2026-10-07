"""In-memory store with the PostgREST query surface the outcome runtime uses.

Certification runs every pack through the real measurement engine against this
store, so "VERIFIED results can be produced" and "duplicates cannot double
count" are proven by the same code path production uses. It also enforces the
ledger's partial unique indexes (see the matching migration).
"""
from __future__ import annotations

import copy
import uuid
from typing import Any


class MemoryStoreError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


def _path_value(row: dict[str, Any], column: str) -> Any:
    if "->>" in column or "->" in column:
        head, _, rest = column.replace("->>", "->").partition("->")
        current: Any = row.get(head)
        for part in rest.split("->"):
            current = current.get(part) if isinstance(current, dict) else None
        if "->>" in column and current is not None and not isinstance(current, str):
            return str(current).lower() if isinstance(current, bool) else str(current)
        return current
    return row.get(column)


def _contains(haystack: Any, needle: Any) -> bool:
    if isinstance(needle, dict):
        return isinstance(haystack, dict) and all(_contains(haystack.get(k), v) for k, v in needle.items())
    if isinstance(needle, list):
        return isinstance(haystack, list) and all(any(_contains(h, n) for h in haystack) for n in needle)
    return haystack == needle


# Ledger uniqueness, mirroring supabase/migrations/*_outcome_pack_ledger_claims.sql
def _ledger_unique_keys(row: dict[str, Any]) -> list[tuple[str, ...]]:
    if row.get("outcome_event") != "play_business_result":
        return []
    meta = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
    keys: list[tuple[str, ...]] = []
    if meta.get("verification_state") == "VERIFIED SUCCESS" and meta.get("counted_in_total") is True and meta.get("claim_key"):
        keys.append(("claim", str(row.get("org_id")), str(meta["claim_key"])))
    if meta.get("decision_key"):
        keys.append(("decision", str(row.get("org_id")), str(meta["decision_key"])))
    return keys


class _Query:
    def __init__(self, store: "MemoryStore", table: str) -> None:
        self.store = store
        self.table = table
        self.op = "select"
        self.payload: Any = None
        self.filters: list[Any] = []
        self._order: tuple[str, bool] | None = None
        self._limit: int | None = None

    def select(self, *_a: Any, **_k: Any) -> "_Query":
        return self

    def insert(self, payload: Any) -> "_Query":
        self.op, self.payload = "insert", payload
        return self

    def update(self, payload: dict[str, Any]) -> "_Query":
        self.op, self.payload = "update", payload
        return self

    def eq(self, column: str, value: Any) -> "_Query":
        wanted = str(value).lower() if isinstance(value, bool) else value
        self.filters.append(lambda r, c=column, v=wanted: _path_value(r, c) == v or str(_path_value(r, c)) == str(v))
        return self

    def in_(self, column: str, values: list[Any]) -> "_Query":
        allowed = {str(v) for v in values}
        self.filters.append(lambda r, c=column: str(_path_value(r, c)) in allowed)
        return self

    def gte(self, column: str, value: Any) -> "_Query":
        self.filters.append(lambda r, c=column, v=value: _path_value(r, c) is not None and str(_path_value(r, c)) >= str(v))
        return self

    def lte(self, column: str, value: Any) -> "_Query":
        self.filters.append(lambda r, c=column, v=value: _path_value(r, c) is not None and str(_path_value(r, c)) <= str(v))
        return self

    def contains(self, column: str, value: Any) -> "_Query":
        self.filters.append(lambda r, c=column, v=value: _contains(_path_value(r, c), v))
        return self

    def order(self, column: str, desc: bool = False) -> "_Query":
        self._order = (column, desc)
        return self

    def limit(self, n: int) -> "_Query":
        self._limit = n
        return self

    def _match(self, row: dict[str, Any]) -> bool:
        return all(f(row) for f in self.filters)

    def execute(self) -> Any:
        rows = self.store.tables.setdefault(self.table, [])
        if self.op == "select":
            found = [copy.deepcopy(r) for r in rows if self._match(r)]
            if self._order:
                col, desc = self._order
                found.sort(key=lambda r: str(r.get(col) or ""), reverse=desc)
            if self._limit is not None:
                found = found[: self._limit]
            return _Response(found)
        if self.op == "insert":
            batch = self.payload if isinstance(self.payload, list) else [self.payload]
            prepared = []
            taken = {k for r in rows for k in _ledger_unique_keys(r)}
            for raw in batch:
                row = copy.deepcopy(raw)
                row.setdefault("id", str(uuid.uuid4()))
                for key in _ledger_unique_keys(row):
                    if key in taken:
                        raise MemoryStoreError("23505", f"duplicate key value violates unique constraint ({key[0]})")
                    taken.add(key)
                prepared.append(row)
            rows.extend(prepared)
            return _Response(copy.deepcopy(prepared))
        if self.op == "update":
            changed = []
            for row in rows:
                if self._match(row):
                    row.update(copy.deepcopy(self.payload))
                    changed.append(copy.deepcopy(row))
            return _Response(changed)
        raise AssertionError(self.op)


class _Response:
    def __init__(self, data: list[dict[str, Any]]) -> None:
        self.data = data
        self.error = None


class MemoryStore:
    def __init__(self) -> None:
        self.tables: dict[str, list[dict[str, Any]]] = {}

    def table(self, name: str) -> _Query:
        return _Query(self, name)

    def rows(self, table: str) -> list[dict[str, Any]]:
        return list(self.tables.get(table, []))
