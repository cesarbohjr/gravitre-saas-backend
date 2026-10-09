"""Tests for source sync service."""
from __future__ import annotations

from app.services.source_sync_service import (
    DEFAULT_SYNC_INTERVAL_SECONDS,
    _is_due,
    _sync_interval_seconds,
    list_recent_source_activity,
    validate_saas_connector_link,
)


def test_sync_interval_defaults() -> None:
    assert _sync_interval_seconds({}) == DEFAULT_SYNC_INTERVAL_SECONDS
    assert _sync_interval_seconds({"syncIntervalSeconds": 120}) == 120


def test_is_due_without_last_sync() -> None:
    from datetime import datetime, timezone

    assert _is_due({"metadata": {}}, now=datetime.now(timezone.utc)) is True


def test_validate_saas_requires_connector_id() -> None:
    class DummyClient:
        def table(self, *_args, **_kwargs):
            return self

        def select(self, *_args, **_kwargs):
            return self

        def eq(self, *_args, **_kwargs):
            return self

        def limit(self, *_args, **_kwargs):
            return self

        def execute(self):
            return type("R", (), {"data": []})()

    errors = validate_saas_connector_link(
        DummyClient(),
        "org-1",
        type_id="hubspot",
        config={},
        environment="production",
    )
    assert "Linked connector is required" in errors[0]


class _AuditQuery:
    def __init__(self, rows):
        self.rows = rows
        self.filters = {}

    def select(self, *_a, **_k):
        return self

    def eq(self, key, value):
        self.rows = [r for r in self.rows if key not in r or str(r[key]) == str(value)]
        return self

    def in_(self, key, values):
        wanted = {str(v) for v in values}
        self.rows = [r for r in self.rows if str(r.get(key)) in wanted]
        return self

    def like(self, *_a, **_k):
        return self

    def order(self, *_a, **_k):
        self.rows = sorted(self.rows, key=lambda r: r["created_at"], reverse=True)
        return self

    def limit(self, n):
        self.rows = self.rows[:n]
        return self

    def execute(self):
        return type("R", (), {"data": self.rows})()


class _AuditClient:
    def __init__(self, rows):
        self.rows = rows

    def table(self, _name):
        return _AuditQuery(list(self.rows))


def test_recent_source_activity_groups_syncs_oldest_first_and_builds_feed() -> None:
    rows = []
    for i in range(9):
        rows.append(
            {
                "resource_id": "src-a",
                "action": "source.sync.scheduled",
                "metadata": {"status": "error" if i >= 7 else "success", "records": 10 + i, "error": "boom" if i >= 7 else None},
                "created_at": f"2026-10-0{1 + i % 9}T00:00:0{i}Z",
            }
        )
    rows.append({"resource_id": "src-b", "action": "source.created", "metadata": {}, "created_at": "2026-09-01T00:00:00Z"})
    rows.append({"resource_id": "src-b", "action": "source.deleted", "metadata": {}, "created_at": "2026-09-02T00:00:00Z"})
    out = list_recent_source_activity(_AuditClient(rows), "org-1", ["src-a", "src-b"])
    syncs = out["syncs"]["src-a"]
    assert len(syncs) == 7
    assert syncs[-1]["status"] == "error" and syncs[-1]["error"] == "boom"
    assert syncs[0]["createdAt"] < syncs[-1]["createdAt"]
    assert "src-b" not in out["syncs"]
    assert out["feed"][0]["kind"] == "sync"
    assert all(e["kind"] != "deleted" for e in out["feed"])
    assert len(out["feed"]) == 8


def test_recent_source_activity_without_sources_reads_nothing() -> None:
    class Boom:
        def table(self, *_a):
            raise AssertionError("should not query")

    assert list_recent_source_activity(Boom(), "org-1", []) == {"syncs": {}, "feed": []}
