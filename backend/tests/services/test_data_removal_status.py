"""Disconnect copy and the removal receipts view follow the switches that actually run."""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from app.services import data_removal_status as drs

NOW = datetime(2026, 10, 13, 12, 0, tzinfo=timezone.utc)


class _Table:
    def __init__(self, client: _Client, name: str) -> None:
        self.client = client
        self.name = name
        self.filters: list[tuple[str, str, Any]] = []
        self._limit: int | None = None

    def select(self, *_a: Any, **_k: Any) -> _Table:
        return self

    def eq(self, key: str, value: Any) -> _Table:
        self.filters.append(("eq", key, value))
        return self

    def gte(self, key: str, value: Any) -> _Table:
        self.filters.append(("gte", key, value))
        return self

    def in_(self, key: str, values: list[Any]) -> _Table:
        self.filters.append(("in", key, list(values)))
        return self

    def order(self, *_a: Any, **_k: Any) -> _Table:
        return self

    def limit(self, value: int) -> _Table:
        self._limit = value
        return self

    def execute(self) -> MagicMock:
        if self.name in self.client.fail:
            raise RuntimeError("relation does not exist")
        rows = [dict(r) for r in self.client.store.get(self.name, [])]
        for op, key, value in self.filters:
            if op == "eq":
                rows = [r for r in rows if r.get(key) == value]
            elif op == "in":
                rows = [r for r in rows if r.get(key) in value]
            elif op == "gte":
                rows = [r for r in rows if r.get(key) is not None and str(r[key]) >= value]
        if self._limit is not None:
            rows = rows[: self._limit]
        out = MagicMock()
        out.data = rows
        return out


class _Client:
    def __init__(self, store: dict[str, list[dict[str, Any]]], fail: tuple[str, ...] = ()) -> None:
        self.store = store
        self.fail = fail

    def table(self, name: str) -> _Table:
        return _Table(self, name)


def _settings(**over: Any) -> SimpleNamespace:
    base = {
        "domain_event_relay_enabled": False,
        "source_purge_dry_run": True,
        "connector_provider_revoke_on_disconnect": False,
        "source_deletion_propagation_enabled": False,
        "memory_source_lineage_enabled": False,
    }
    base.update(over)
    return SimpleNamespace(**base)


@pytest.mark.parametrize(
    ("relay", "dry_run", "mode"),
    [(False, True, "off"), (False, False, "off"), (True, True, "test"), (True, None, "test"), (True, False, "on")],
)
def test_policy_mode_follows_relay_and_dry_run(relay: bool, dry_run: Any, mode: str) -> None:
    policy = drs.removal_policy(_settings(domain_event_relay_enabled=relay, source_purge_dry_run=dry_run))
    assert policy["dataRemoval"] == mode


def test_policy_reports_revoke_and_supported_vendors() -> None:
    off = drs.removal_policy(_settings())
    assert off["providerRevokeEnabled"] is False
    on = drs.removal_policy(_settings(connector_provider_revoke_on_disconnect=True))
    assert on["providerRevokeEnabled"] is True
    assert {"hubspot", "slack", "salesforce"} <= set(on["providerRevokeVendors"])
    assert "zendesk" not in on["providerRevokeVendors"]


def test_policy_memories_follow_lineage(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(drs, "liveness_enabled", lambda _s: True)
    assert drs.removal_policy(_settings())["memoriesIncluded"] is True
    monkeypatch.setattr(drs, "liveness_enabled", lambda _s: False)
    assert drs.removal_policy(_settings())["memoriesIncluded"] is False


def _store() -> dict[str, list[dict[str, Any]]]:
    return {
        "connectors": [
            {"id": "c-live", "org_id": "org-1", "name": "HubSpot", "vendor": "hubspot", "deleted_at": "2026-10-12T10:00:00+00:00"},
            {"id": "c-plan", "org_id": "org-1", "name": "Zendesk", "vendor": "zendesk", "deleted_at": "2026-10-11T10:00:00+00:00"},
            {"id": "c-none", "org_id": "org-1", "name": "Notion", "vendor": "notion", "deleted_at": "2026-10-10T10:00:00+00:00"},
            {"id": "c-old", "org_id": "org-1", "name": "Old", "vendor": "slack", "deleted_at": "2026-01-01T10:00:00+00:00"},
            {"id": "c-active", "org_id": "org-1", "name": "Active", "vendor": "slack", "deleted_at": None},
            {"id": "c-other", "org_id": "org-2", "name": "Other org", "vendor": "slack", "deleted_at": "2026-10-12T10:00:00+00:00"},
        ],
        "source_purge_receipts": [
            {"org_id": "org-1", "connector_id": "c-live", "dry_run": False, "counts": {"rag_documents": 0}, "created_at": "2026-10-12T11:00:00+00:00"},
            {"org_id": "org-1", "connector_id": "c-live", "dry_run": True, "counts": {"rag_documents": 7}, "created_at": "2026-10-12T12:00:00+00:00"},
            {"org_id": "org-1", "connector_id": "c-plan", "dry_run": True, "counts": {"rag_documents": 3, "agent_memories": 2}, "created_at": "2026-10-11T11:00:00+00:00"},
            {"org_id": "org-2", "connector_id": "c-none", "dry_run": False, "counts": {"rag_documents": 9}, "created_at": "2026-10-11T11:00:00+00:00"},
        ],
    }


def test_list_removals_is_org_scoped_recent_and_prefers_live_receipts() -> None:
    rows = drs.list_removals(_Client(_store()), "org-1", "test", now=NOW)
    by_id = {r["connectorId"]: r for r in rows}
    assert set(by_id) == {"c-live", "c-plan", "c-none"}
    assert by_id["c-live"]["status"] == "removed"
    assert by_id["c-live"]["counts"] == {"rag_documents": 0}
    assert by_id["c-plan"]["status"] == "planned"
    assert by_id["c-plan"]["counts"] == {"rag_documents": 3, "agent_memories": 2}
    # Another org's receipt for the same connector id is never shown.
    assert by_id["c-none"]["status"] == "queued"
    assert by_id["c-none"]["counts"] == {}


def test_list_removals_without_relay_says_not_started() -> None:
    rows = drs.list_removals(_Client(_store()), "org-1", "off", now=NOW)
    assert {r["connectorId"]: r["status"] for r in rows}["c-none"] == "not_started"


def test_list_removals_survives_missing_receipts_table() -> None:
    rows = drs.list_removals(_Client(_store(), fail=("source_purge_receipts",)), "org-1", "test", now=NOW)
    assert [r["status"] for r in rows] == ["queued", "queued", "queued"]


def test_list_removals_empty_when_nothing_disconnected() -> None:
    assert drs.list_removals(_Client({"connectors": []}), "org-1", "on", now=NOW) == []


def test_data_removal_route_is_not_shadowed_by_connector_id_route() -> None:
    from app.routers.connectors import connectors_router

    paths = [r.path for r in connectors_router.routes if "GET" in getattr(r, "methods", set())]
    assert paths.index("/api/connectors/data-removal") < paths.index("/api/connectors/{connector_id}")
