"""In-memory Supabase double for the storage/retention tests (filters are applied)."""
from __future__ import annotations

import copy
import uuid
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any


class FakeQuery:
    def __init__(self, client: FakeClient, table: str) -> None:
        self.client = client
        self.table = table
        self.op = "select"
        self.payload: Any = None
        self.on_conflict: str | None = None
        self.filters: list[Callable[[dict[str, Any]], bool]] = []
        self.filter_log: list[tuple[str, str, Any]] = []
        self._order: tuple[str, bool] | None = None
        self._limit: int | None = None

    def select(self, *_a: Any, **_k: Any) -> FakeQuery:
        self.op = "select"
        return self

    def insert(self, payload: Any) -> FakeQuery:
        self.op, self.payload = "insert", payload
        return self

    def update(self, payload: dict[str, Any]) -> FakeQuery:
        self.op, self.payload = "update", payload
        return self

    def upsert(self, payload: Any, on_conflict: str | None = None) -> FakeQuery:
        self.op, self.payload, self.on_conflict = "upsert", payload, on_conflict
        return self

    def delete(self) -> FakeQuery:
        self.op = "delete"
        return self

    def eq(self, col: str, val: Any) -> FakeQuery:
        self.filter_log.append(("eq", col, val))
        self.filters.append(lambda r: r.get(col) == val)
        return self

    def lt(self, col: str, val: Any) -> FakeQuery:
        self.filter_log.append(("lt", col, val))
        self.filters.append(lambda r: r.get(col) is not None and str(r.get(col)) < str(val))
        return self

    def is_(self, col: str, val: Any) -> FakeQuery:
        self.filter_log.append(("is", col, val))
        self.filters.append(lambda r: r.get(col) is None if val == "null" else r.get(col) == val)
        return self

    def order(self, col: str, desc: bool = False) -> FakeQuery:
        self._order = (col, desc)
        return self

    def limit(self, n: int) -> FakeQuery:
        self._limit = n
        return self

    def _match(self, row: dict[str, Any]) -> bool:
        return all(f(row) for f in self.filters)

    def execute(self) -> SimpleNamespace:
        self.client.calls.append(("table", self.table, self.op, list(self.filter_log)))
        hook = self.client.table_errors.get((self.table, self.op))
        if hook is not None:
            raise hook
        rows = self.client.tables.setdefault(self.table, [])
        if self.op == "select":
            found = [copy.deepcopy(r) for r in rows if self._match(r)]
            if self._order:
                col, desc = self._order
                found.sort(key=lambda r: str(r.get(col) or ""), reverse=desc)
            if self._limit is not None:
                found = found[: self._limit]
            return SimpleNamespace(data=found)
        if self.op == "insert":
            batch = self.payload if isinstance(self.payload, list) else [self.payload]
            out = []
            for raw in batch:
                row = copy.deepcopy(raw)
                row.setdefault("id", str(uuid.uuid4()))
                rows.append(row)
                out.append(copy.deepcopy(row))
            return SimpleNamespace(data=out)
        if self.op == "upsert":
            batch = self.payload if isinstance(self.payload, list) else [self.payload]
            keys = [k.strip() for k in (self.on_conflict or "id").split(",")]
            out = []
            for raw in batch:
                match = next((r for r in rows if all(r.get(k) == raw.get(k) for k in keys)), None)
                if match is None:
                    match = {"id": str(uuid.uuid4())}
                    rows.append(match)
                match.update(copy.deepcopy(raw))
                out.append(copy.deepcopy(match))
            return SimpleNamespace(data=out)
        if self.op == "update":
            changed = []
            for row in rows:
                if self._match(row):
                    row.update(copy.deepcopy(self.payload))
                    changed.append(copy.deepcopy(row))
            return SimpleNamespace(data=changed)
        if self.op == "delete":
            gone = [r for r in rows if self._match(r)]
            self.client.tables[self.table] = [r for r in rows if not self._match(r)]
            return SimpleNamespace(data=copy.deepcopy(gone))
        raise AssertionError(self.op)


class FakeRpc:
    def __init__(self, client: FakeClient, name: str, params: dict[str, Any]) -> None:
        self.client, self.name, self.params = client, name, params

    def execute(self) -> SimpleNamespace:
        self.client.calls.append(("rpc", self.name, dict(self.params)))
        self.client.events.append(("rpc", self.name))
        handler = self.client.rpc_handlers.get(self.name)
        if handler is None:
            raise AssertionError(f"unexpected rpc {self.name}")
        return SimpleNamespace(data=handler(self.params))


class FakeBucket:
    def __init__(self, client: FakeClient, bucket: str) -> None:
        self.client, self.bucket = client, bucket

    def upload(self, path: str, data: bytes, file_options: dict[str, Any] | None = None) -> dict[str, Any]:
        self.client.events.append(("upload", self.bucket, path))
        if self.client.upload_error is not None:
            raise self.client.upload_error
        self.client.uploads.append({"bucket": self.bucket, "path": path, "data": data, "options": file_options})
        return {"Key": path}

    def create_signed_url(self, path: str, ttl: int) -> dict[str, Any]:
        return {"signedURL": f"https://supabase.test/{self.bucket}/{path}?ttl={ttl}"}


class FakeClient:
    def __init__(self) -> None:
        self.tables: dict[str, list[dict[str, Any]]] = {}
        self.calls: list[tuple] = []
        self.events: list[tuple] = []
        self.uploads: list[dict[str, Any]] = []
        self.upload_error: Exception | None = None
        self.rpc_handlers: dict[str, Callable[[dict[str, Any]], Any]] = {}
        self.table_errors: dict[tuple[str, str], Exception] = {}
        self.storage = SimpleNamespace(from_=lambda bucket: FakeBucket(self, bucket))

    def table(self, name: str) -> FakeQuery:
        return FakeQuery(self, name)

    def rpc(self, name: str, params: dict[str, Any]) -> FakeRpc:
        return FakeRpc(self, name, params)

    def rpc_calls(self, name: str) -> list[dict[str, Any]]:
        return [c[2] for c in self.calls if c[0] == "rpc" and c[1] == name]


class FakeS3:
    """Records put/head/delete/presign; ``fail_on`` makes one operation raise."""

    def __init__(self, fail_on: str | None = None) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}
        self.calls: list[tuple[str, str, str]] = []
        self.fail_on = fail_on

    def _maybe_fail(self, op: str) -> None:
        if self.fail_on == op:
            err = Exception("denied")
            err.response = {"Error": {"Code": "AccessDenied", "Message": "secret-should-not-leak"}}
            raise err

    def put_object(self, *, Bucket: str, Key: str, Body: bytes, **_kw: Any) -> dict[str, Any]:
        self.calls.append(("put", Bucket, Key))
        self._maybe_fail("put")
        self.objects[(Bucket, Key)] = Body
        return {}

    def head_object(self, *, Bucket: str, Key: str) -> dict[str, Any]:
        self.calls.append(("head", Bucket, Key))
        self._maybe_fail("head")
        if (Bucket, Key) not in self.objects:
            raise KeyError(Key)
        return {"ContentLength": len(self.objects[(Bucket, Key)])}

    def delete_object(self, *, Bucket: str, Key: str) -> dict[str, Any]:
        self.calls.append(("delete", Bucket, Key))
        self._maybe_fail("delete")
        self.objects.pop((Bucket, Key), None)
        return {}

    def generate_presigned_url(self, op: str, Params: dict[str, Any], ExpiresIn: int) -> str:
        self.calls.append(("presign", Params["Bucket"], Params["Key"]))
        return f"https://s3.test/{Params['Bucket']}/{Params['Key']}?X-Amz-Expires={ExpiresIn}"
