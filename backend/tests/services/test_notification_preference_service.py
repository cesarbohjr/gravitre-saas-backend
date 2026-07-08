"""Tests for per-event notification preferences."""
from __future__ import annotations

from unittest.mock import MagicMock

from app.services.notification_emitter import emit_notification
from app.services.notification_preference_service import (
    channel_enabled,
    default_preferences_payload,
    flatten_structured_preferences,
    structured_preferences,
)


def test_default_assignment_changed_email_is_off():
    defaults = structured_preferences({})
    assert defaults["assignment_changed"]["email_enabled"] is False
    assert defaults["run_failed"]["email_enabled"] is True


def test_flatten_and_structured_round_trip():
    structured = {
        "assignment_changed": {"bell_enabled": True, "email_enabled": False},
        "run_failed": {"bell_enabled": True, "email_enabled": True},
    }
    flat = flatten_structured_preferences(structured)
    assert flat["email_assignment_changed"] is False
    assert flat["email_run_failed"] is True


def test_emit_notification_still_writes_when_email_disabled(client=None):
    client = MagicMock()
    client.table.return_value.insert.return_value.execute.return_value.data = [{"id": "notif-2"}]
    client.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
        {"preferences": flatten_structured_preferences(
            {"assignment_changed": {"bell_enabled": True, "email_enabled": False}}
        )}
    ]

    notification_id = emit_notification(
        client,
        org_id="org-1",
        user_id="user-1",
        event_type="assignment_changed",
        title="Assignment updated",
        body="Reassigned to you.",
        entity_ref={"result_url": "/assignments/job-1"},
        channel_hints={"email": True},
    )

    assert notification_id == "notif-2"
    assert channel_enabled(client, "org-1", "user-1", "assignment_changed", "email") is False
    assert "email_assignment_changed" in default_preferences_payload()
