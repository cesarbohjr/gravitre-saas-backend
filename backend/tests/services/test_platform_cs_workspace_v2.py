"""Tier 6 v2: Platform CS alerts + escalation."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.services.platform_cs_workspace_service import (
    PlatformCsWorkspaceError,
    escalate_platform_tenant,
    list_platform_cs_alerts,
)


def _table(select_data: list | None = None) -> MagicMock:
    mock = MagicMock()
    mock.select.return_value = mock
    mock.eq.return_value = mock
    mock.in_.return_value = mock
    mock.order.return_value = mock
    mock.limit.return_value = mock
    result = MagicMock()
    result.data = select_data or []
    result.error = None
    mock.execute.return_value = result
    upsert_mock = MagicMock()
    upsert_mock.execute.return_value = MagicMock(data=[])
    mock.upsert.return_value = upsert_mock
    return mock


def test_list_platform_cs_alerts_merges_failure_and_suggestions():
    failures = [
        {
            "id": "alert-1",
            "org_id": "org-1",
            "workflow_id": "wf-1",
            "alert_type": "auth_expiry",
            "severity": "critical",
            "title": "Token expiring",
            "message": "Refresh soon",
            "predicted_at": "2026-06-22T10:00:00+00:00",
            "status": "open",
        }
    ]
    suggestions = [
        {
            "id": "sug-1",
            "org_id": "org-2",
            "suggestion_type": "connect_connector",
            "title": "Connect Slack",
            "message": "High tool usage",
            "priority": 1,
            "suggested_at": "2026-06-22T09:00:00+00:00",
            "status": "open",
        }
    ]
    orgs = [
        {"id": "org-1", "name": "Acme"},
        {"id": "org-2", "name": "Beta"},
    ]

    def table_router(name: str):
        if name == "workflow_failure_alerts":
            return _table(failures)
        if name == "integration_suggestions":
            return _table(suggestions)
        if name == "organizations":
            return _table(orgs)
        return _table([])

    client = MagicMock()
    client.table.side_effect = table_router

    payload = list_platform_cs_alerts(client, limit=10)
    assert payload["count"] == 2
    kinds = {item["kind"] for item in payload["alerts"]}
    assert kinds == {"failure", "suggestion"}
    assert payload["alerts"][0]["orgName"] in {"Acme", "Beta"}


def test_escalate_platform_tenant_records_queue_without_webhook():
    orgs = [{"id": "org-1", "name": "Acme", "slug": "acme"}]
    queue = _table([])
    queue.upsert.return_value.execute.return_value = MagicMock(data=[])

    def table_router(name: str):
        if name == "organizations":
            return _table(orgs)
        if name == "integration_health_snapshots":
            return _table([])
        if name == "integration_suggestions":
            return _table([])
        if name == "workflow_failure_alerts":
            return _table([])
        if name == "platform_cs_tenant_queue":
            return queue
        return _table([])

    client = MagicMock()
    client.table.side_effect = table_router

    result = escalate_platform_tenant(
        client,
        "org-1",
        actor_id="user-1",
        actor_email="ops@gravitre.app",
        note="Needs on-call",
        webhook_url="",
        app_base_url="https://app.gravitre.app",
    )
    assert result["orgName"] == "Acme"
    assert result["delivered"] is False
    assert "not configured" in (result["deliveryError"] or "")
    queue.upsert.assert_called_once()


@patch("app.services.platform_cs_workspace_service.httpx.post")
def test_escalate_platform_tenant_posts_webhook(mock_post):
    mock_post.return_value = MagicMock(is_success=True, status_code=200)
    orgs = [{"id": "org-1", "name": "Acme", "slug": "acme"}]
    queue = _table([])
    queue.upsert.return_value.execute.return_value = MagicMock(data=[])

    def table_router(name: str):
        if name == "organizations":
            return _table(orgs)
        if name == "platform_cs_tenant_queue":
            return queue
        return _table([])

    client = MagicMock()
    client.table.side_effect = table_router

    result = escalate_platform_tenant(
        client,
        "org-1",
        actor_email="ops@gravitre.app",
        webhook_url="https://hooks.example.com/slack",
    )
    assert result["delivered"] is True
    mock_post.assert_called_once()


def test_escalate_unknown_org_raises():
    client = MagicMock()
    client.table.return_value = _table([])
    with pytest.raises(PlatformCsWorkspaceError):
        escalate_platform_tenant(client, "missing-org")
