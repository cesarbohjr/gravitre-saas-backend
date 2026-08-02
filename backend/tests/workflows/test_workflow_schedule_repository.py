"""Regression: schedule writes must match prod schema (enabled only)."""
from __future__ import annotations

from unittest.mock import MagicMock

from app.workflows.repository import create_workflow_schedule, update_workflow_schedule


def test_create_workflow_schedule_omits_is_enabled():
    client = MagicMock()
    client.table.return_value.insert.return_value.execute.return_value = MagicMock(
        data=[
            {
                "id": "s1",
                "org_id": "org-1",
                "workflow_id": "wf-1",
                "cron_expression": "0 9 * * 1",
                "enabled": True,
            }
        ]
    )
    create_workflow_schedule(
        client,
        "org-1",
        "wf-1",
        "0 9 * * 1",
        "production",
        True,
        "2026-08-04T16:00:00+00:00",
        "user-1",
        timezone_name="America/Los_Angeles",
        schedule_type="recurring",
        name="Weekly",
    )
    row = client.table.return_value.insert.call_args[0][0]
    assert row["enabled"] is True
    assert "is_enabled" not in row
    assert row["timezone"] == "America/Los_Angeles"
    assert row["schedule_type"] == "recurring"


def test_update_workflow_schedule_omits_is_enabled():
    client = MagicMock()
    chain = (
        client.table.return_value.update.return_value.eq.return_value.eq.return_value.eq.return_value
    )
    chain.execute.return_value = MagicMock(data=[{"id": "s1", "enabled": False}])
    update_workflow_schedule(
        client,
        "org-1",
        "s1",
        "production",
        None,
        False,
        None,
        "user-1",
    )
    payload = client.table.return_value.update.call_args[0][0]
    assert payload["enabled"] is False
    assert "is_enabled" not in payload
