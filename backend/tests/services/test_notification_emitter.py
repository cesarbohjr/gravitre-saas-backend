"""Tests for unified notification emission."""
from __future__ import annotations

from unittest.mock import MagicMock

from app.services.notification_emitter import emit_notification, normalize_event_type


def test_normalize_event_type_maps_assignment_created():
    assert normalize_event_type("assignment_created") == "assignment_changed"


def test_emit_notification_writes_durable_row_first():
    client = MagicMock()
    client.table.return_value.insert.return_value.execute.return_value.data = [{"id": "notif-1"}]

    notification_id = emit_notification(
        client,
        org_id="org-1",
        user_id="user-1",
        event_type="run_completed",
        title="Workflow run completed",
        body="Run finished with status completed.",
        entity_ref={
            "entity_type": "workflow_run",
            "entity_id": "run-1",
            "result_url": "/runs/run-1",
        },
        channel_hints={"bell": True, "email": False},
    )

    assert notification_id == "notif-1"
    insert_call = client.table.return_value.insert.call_args[0][0]
    assert insert_call["type"] == "run_completed"
    assert insert_call["url"] == "/runs/run-1"
    assert insert_call["entity_type"] == "workflow_run"
    assert insert_call["entity_id"] == "run-1"


def test_emit_notification_skips_without_user():
    client = MagicMock()
    assert emit_notification(client, org_id="org-1", user_id="", event_type="system", title="x", body="y") is None
    client.table.assert_not_called()
