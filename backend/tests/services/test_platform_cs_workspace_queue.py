"""Tier 6: Platform CS workspace queue + backfill."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from app.services.platform_cs_workspace_service import (
    assign_platform_tenant,
    backfill_platform_health_snapshots,
    snooze_platform_tenant,
)


def _table(select_data: list | None = None) -> MagicMock:
    mock = MagicMock()
    mock.select.return_value = mock
    mock.eq.return_value = mock
    mock.in_.return_value = mock
    mock.order.return_value = mock
    mock.limit.return_value = mock
    mock.execute.return_value = MagicMock(data=select_data or [])
    mock.upsert.return_value = mock
    mock.upsert.return_value.execute.return_value = MagicMock(data=[])
    return mock


@patch("app.services.platform_cs_workspace_service.backfill_missing_integration_health_snapshots")
def test_backfill_platform_health_snapshots(mock_backfill):
    mock_backfill.return_value = {"backfilled": 2, "requested": 2, "results": [], "errors": []}
    client = MagicMock()
    payload = backfill_platform_health_snapshots(client, limit=10, actor_id="user-1")
    assert payload["backfilled"] == 2
    mock_backfill.assert_called_once()


def test_assign_platform_tenant_upserts_queue_row():
    queue = _table([])
    upsert_result = MagicMock(
        data=[
            {
                "org_id": "org-1",
                "assigned_to": "user-1",
                "assigned_email": "ops@gravitre.app",
                "assigned_at": "2026-06-22T00:00:00+00:00",
                "snoozed_until": None,
                "note": "Follow up",
                "updated_at": "2026-06-22T00:00:00+00:00",
            }
        ]
    )
    queue.upsert.return_value.execute.return_value = upsert_result
    client = MagicMock()
    client.table.return_value = queue

    result = assign_platform_tenant(
        client,
        "org-1",
        assignee_user_id="user-1",
        assignee_email="ops@gravitre.app",
        note="Follow up",
        actor_id="user-1",
    )
    assert result["assignedEmail"] == "ops@gravitre.app"
    assert result["isSnoozed"] is False


def test_snooze_platform_tenant_sets_until():
    future = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
    queue = _table(
        [
            {
                "org_id": "org-1",
                "assigned_to": None,
                "assigned_email": None,
                "assigned_at": None,
                "snoozed_until": None,
                "note": None,
                "updated_at": "2026-06-22T00:00:00+00:00",
            }
        ]
    )
    queue.upsert.return_value.execute.return_value = MagicMock(
        data=[
            {
                "org_id": "org-1",
                "assigned_to": None,
                "assigned_email": None,
                "assigned_at": None,
                "snoozed_until": future,
                "note": None,
                "updated_at": "2026-06-22T00:00:00+00:00",
            }
        ]
    )

    def table_router(name: str):
        if name == "platform_cs_tenant_queue":
            return queue
        return _table([])

    client = MagicMock()
    client.table.side_effect = table_router

    result = snooze_platform_tenant(client, "org-1", hours=24, actor_id="user-1")
    assert result["isSnoozed"] is True
    assert result["snoozeHours"] == 24
