"""Tests for activity feed service."""
from __future__ import annotations

from unittest.mock import MagicMock

from app.services.activity_feed_service import list_recent_activity, record_activity_event


def test_record_activity_event_inserts_connector_write():
    client = MagicMock()
    client.table.return_value.insert.return_value.execute.return_value.data = [{"id": "act-1"}]

    activity_id = record_activity_event(
        client,
        org_id="org-1",
        user_id="user-1",
        source="connector_write",
        event_type="task_completed",
        title="Post to Slack #sales",
        body="Message posted to Slack #sales.",
        integration="slack",
        url="https://example.slack.com/archives/C123/p456",
    )

    assert activity_id == "act-1"
    row = client.table.return_value.insert.call_args[0][0]
    assert row["source"] == "connector_write"
    assert row["integration"] == "slack"


def test_list_recent_activity_returns_normalized_rows():
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = [
        {
            "id": "act-1",
            "source": "connector_write",
            "event_type": "task_completed",
            "title": "Created HubSpot deal",
            "body": 'Created HubSpot deal "Acme" (id: 42).',
            "status": "completed",
            "integration": "hubspot",
            "created_at": "2026-07-07T12:00:00+00:00",
        }
    ]

    rows = list_recent_activity(client, org_id="org-1", user_id="user-1", limit=5)

    assert len(rows) == 1
    assert rows[0]["title"] == "Created HubSpot deal"
    assert rows[0]["integration"] == "hubspot"
