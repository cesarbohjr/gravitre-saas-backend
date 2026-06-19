"""Tier 6: Platform CS workspace rollups."""
from __future__ import annotations

from unittest.mock import MagicMock

from app.services.platform_cs_workspace_service import list_platform_tenant_summaries


def _table(select_data: list | None = None) -> MagicMock:
    mock = MagicMock()
    mock.select.return_value = mock
    mock.eq.return_value = mock
    mock.in_.return_value = mock
    mock.order.return_value = mock
    mock.limit.return_value = mock
    mock.execute.return_value = MagicMock(data=select_data or [])
    return mock


def test_list_platform_tenant_summaries_sorts_critical_first():
    orgs = [
        {"id": "org-healthy", "name": "Healthy Co", "slug": "healthy", "created_at": "2026-01-01T00:00:00+00:00"},
        {"id": "org-critical", "name": "Critical Co", "slug": "critical", "created_at": "2026-01-02T00:00:00+00:00"},
    ]
    snapshots = [
        {
            "org_id": "org-healthy",
            "score": 90,
            "grade": "healthy",
            "risks": [],
            "recorded_at": "2026-06-01T00:00:00+00:00",
            "lookback_days": 30,
        },
        {
            "org_id": "org-critical",
            "score": 40,
            "grade": "critical",
            "risks": [{"code": "connectors"}],
            "recorded_at": "2026-06-01T00:00:00+00:00",
            "lookback_days": 30,
        },
    ]

    def table_router(name: str):
        if name == "organizations":
            return _table(orgs)
        if name == "integration_health_snapshots":
            return _table(snapshots)
        if name == "integration_suggestions":
            return _table([{"org_id": "org-critical"}])
        if name == "workflow_failure_alerts":
            return _table([])
        return _table([])

    client = MagicMock()
    client.table.side_effect = table_router

    payload = list_platform_tenant_summaries(client, limit=10)
    assert payload["summary"]["total"] == 2
    assert payload["summary"]["critical"] == 1
    assert payload["tenants"][0]["orgId"] == "org-critical"
    assert payload["tenants"][0]["openSuggestions"] == 1
