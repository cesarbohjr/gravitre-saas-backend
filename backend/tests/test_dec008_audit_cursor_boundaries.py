"""DEC-008: deterministic cursor boundaries for both audit readers.

No database credentials or provider writes: fake PostgREST applies the actual
seek predicate to fixed multi-tenant, same-timestamp fixtures.
"""
from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID

import pytest

from app.audit import query as audit


T = "2026-11-23T12:00:00+00:00"
OLDER = "2026-11-22T12:00:00+00:00"
ORG_A = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
ORG_B = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
RESOURCE = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"


def event(number: int, org: str = ORG_A, timestamp: str = T):
    return {
        "id": f"00000000-0000-4000-8000-{number:012d}",
        "org_id": org,
        "resource_type": "job",
        "resource_id": RESOURCE,
        "action": "job.updated",
        "actor_id": None,
        "metadata": {},
        "created_at": timestamp,
    }


EVENTS = [event(i) for i in range(1, 8)] + [
    event(99, ORG_B), event(100, ORG_B, OLDER), event(8, ORG_A, OLDER)
]


class FakeQuery:
    def __init__(self, rows):
        self.rows = list(rows)
        self.order_keys = []
        self.max_rows = None

    def select(self, *_):
        return self

    def eq(self, key, value):
        self.rows = [row for row in self.rows if row[key] == value]
        return self

    def like(self, key, pattern):
        self.rows = [row for row in self.rows if row[key].startswith(pattern.rstrip("%"))]
        return self

    def gte(self, key, value):
        self.rows = [row for row in self.rows if row[key] >= value]
        return self

    def lte(self, key, value):
        self.rows = [row for row in self.rows if row[key] <= value]
        return self

    def or_(self, expression):
        # Match PostgREST's two-arm descending seek filter.
        import re
        match = re.fullmatch(
            r"created_at\.lt\.(.*),and\(created_at\.eq\.(.*),id\.lt\.([0-9a-f-]+)\)",
            expression,
        )
        assert match, f"Unexpected seek predicate: {expression}"
        before, tied, last_id = match.groups()
        assert before == tied
        self.rows = [
            row for row in self.rows
            if (row["created_at"], row["id"]) < (before, last_id)
        ]
        return self

    def order(self, key, desc=False):
        self.order_keys.append((key, desc))
        return self

    def limit(self, count):
        self.max_rows = count
        return self

    def execute(self):
        rows = self.rows
        # Stable two-column descending order; first key is the primary sort.
        for key, descending in reversed(self.order_keys):
            rows = sorted(rows, key=lambda row: row[key], reverse=descending)
        return SimpleNamespace(data=rows[:self.max_rows])


class FakeClient:
    def table(self, name):
        assert name == "audit_events"
        return FakeQuery(EVENTS)

    def rpc(self, name, payload):
        assert name == "audit_query"
        rows = [
            row for row in EVENTS
            if row["org_id"] == payload["p_org_id"]
            and row["resource_type"] == payload["p_resource_type"]
            and row["resource_id"] == payload["p_resource_id"]
        ]
        if payload["p_action_prefix"]:
            rows = [row for row in rows if row["action"].startswith(payload["p_action_prefix"])]
        if payload["p_cursor_created_at"] is not None:
            boundary = (payload["p_cursor_created_at"], payload["p_cursor_id"])
            rows = [row for row in rows if (row["created_at"], row["id"]) < boundary]
        rows.sort(key=lambda row: (row["created_at"], row["id"]), reverse=True)
        return SimpleNamespace(execute=lambda: SimpleNamespace(data=rows[:payload["p_limit"]]))


@pytest.fixture(autouse=True)
def fake_service(monkeypatch):
    monkeypatch.setattr(audit, "shared_service_client", lambda *_: FakeClient())


@pytest.mark.parametrize("reader", ["log", "resource"])
@pytest.mark.parametrize("page_size", [1, 2, 3, 7])
def test_no_missing_duplicate_or_cross_tenant_rows(reader, page_size):
    cursor = None
    seen = []
    for _ in range(12):
        if reader == "log":
            items, next_cursor = audit.query_audit_log(None, ORG_A, page_size, cursor=cursor)
        else:
            items, next_cursor = audit.query_audit_events(
                None, ORG_A, "job", RESOURCE, page_size, cursor=cursor
            )
        seen.extend(row["id"] for row in items)
        if next_cursor is None:
            break
        assert next_cursor != cursor, "Cursor must advance"
        cursor = next_cursor
    else:
        pytest.fail("Pagination did not terminate")
    expected = [
        row["id"] for row in sorted(
            (row for row in EVENTS if row["org_id"] == ORG_A),
            key=lambda row: (row["created_at"], row["id"]), reverse=True
        )
    ]
    assert seen == expected
    assert len(seen) == len(set(seen))


@pytest.mark.parametrize("bad", ["not-base64!", audit._encode_cursor(T, "not-a-uuid"), audit._encode_cursor("2026-11-23T12:00:00", str(UUID(RESOURCE)))])
def test_malformed_cursor_does_not_inject_seek_filter(bad):
    assert audit._decode_cursor(bad) is None
