"""Tests for unified notification emission."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services.notification_emitter import emit_notification, normalize_event_type


def test_normalize_event_type_maps_assignment_created():
    assert normalize_event_type("assignment_created") == "assignment_changed"


def test_emit_notification_writes_durable_row_first():
    client = MagicMock()
    client.table.return_value.insert.return_value.execute.return_value.data = [{"id": "notif-1"}]

    with patch("app.services.notification_emitter._publish_live_notification") as mock_live, patch(
        "app.services.notification_emitter._record_connector_activity"
    ):
        notification_id = emit_notification(
            client,
            org_id="org-1",
            user_id="user-1",
            event_type="run_completed",
            title="Workflow run completed",
            body="Run finished with status completed.",
            entity_ref={
                "entity_type": "workflow_run",
                "entity_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                "result_url": "/runs/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            },
            channel_hints={"bell": True, "email": False},
        )

    assert notification_id == "notif-1"
    insert_call = client.table.return_value.insert.call_args[0][0]
    assert insert_call["type"] == "run_completed"
    assert insert_call["url"] == "/runs/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    assert insert_call["entity_type"] == "workflow_run"
    assert insert_call["entity_id"] == "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    mock_live.assert_called_once()


@patch("app.services.notification_preference_service.channel_enabled", return_value=True)
@patch("app.services.notification_emitter._send_email_if_configured")
def test_emit_notification_passes_email_context(mock_send_email, _mock_channel):
    client = MagicMock()
    client.table.return_value.insert.return_value.execute.return_value.data = [{"id": "notif-2"}]

    with patch("app.services.notification_emitter._publish_live_notification"), patch(
        "app.services.notification_emitter._record_connector_activity"
    ):
        emit_notification(
            client,
            org_id="org-1",
            user_id="user-1",
            event_type="run_completed",
            title="Workflow run completed",
            body="Done",
            entity_ref={
                "entity_type": "workflow_run",
                "entity_id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
                "result_url": "/runs/bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
            },
            channel_hints={"bell": True, "email": True},
            email_context={
                "kind": "workflow_completion",
                "run_id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
                "workflow_name": "Demo",
                "final_status": "completed",
            },
        )

    mock_send_email.assert_called_once()
    assert mock_send_email.call_args.kwargs["email_context"]["kind"] == "workflow_completion"


def test_emit_notification_skips_without_user():
    client = MagicMock()
    assert emit_notification(client, org_id="org-1", user_id="", event_type="system", title="x", body="y") is None
    client.table.assert_not_called()


def test_emit_notification_strips_non_uuid_vendor_entity_id():
    """HubSpot list_id '19' must not hit notifications.entity_id (uuid column)."""
    client = MagicMock()
    client.table.return_value.insert.return_value.execute.return_value.data = [{"id": "notif-3"}]

    with patch("app.services.notification_emitter._publish_live_notification"), patch(
        "app.services.notification_emitter._record_connector_activity"
    ):
        notification_id = emit_notification(
            client,
            org_id="org-1",
            user_id="11111111-1111-1111-1111-111111111111",
            event_type="run_completed",
            title="Extension write completed",
            body="List created",
            entity_ref={
                "entity_type": "connector",
                "entity_id": "19",
                "result_url": "/runs/22222222-2222-2222-2222-222222222222",
            },
            channel_hints={"bell": True, "email": False},
        )

    assert notification_id == "notif-3"
    insert_call = client.table.return_value.insert.call_args[0][0]
    assert insert_call["entity_id"] is None
    assert insert_call["url"] == "/runs/22222222-2222-2222-2222-222222222222"
