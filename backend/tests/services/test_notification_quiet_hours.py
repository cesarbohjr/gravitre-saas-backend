"""Quiet hours in Settings > Notifications: stored with the per-person matrix, honoured for email and Slack."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.services.notification_emitter import emit_notification
from app.services.notification_preference_service import (
    flatten_structured_preferences,
    held_by_quiet_hours,
    quiet_hours_active,
    structured_preferences,
)

QUIET = {"enabled": True, "from": "20:00", "to": "08:00", "timezone": "America/Los_Angeles"}


def _at(hour: int, minute: int = 0) -> datetime:
    # October 2026: Los Angeles is UTC-7.
    return datetime(2026, 10, 19, (hour + 7) % 24, minute, tzinfo=timezone.utc)


@pytest.mark.parametrize("hour,expected", [(21, True), (2, True), (7, True), (8, False), (12, False), (19, False)])
def test_window_crosses_midnight_in_the_persons_zone(hour, expected):
    assert quiet_hours_active(QUIET, _at(hour)) is expected


def test_disabled_or_empty_window_is_never_quiet():
    assert quiet_hours_active({**QUIET, "enabled": False}, _at(23)) is False
    assert quiet_hours_active({**QUIET, "from": "08:00", "to": "08:00"}, _at(8)) is False


def test_quiet_hours_survive_matrix_updates_and_reject_bad_values():
    flat = flatten_structured_preferences({"quiet_hours": QUIET, "run_failed": {"email_enabled": False}})
    assert flat["quiet_hours"] == QUIET and flat["email_run_failed"] is False
    again = flatten_structured_preferences({"weekly_summary": {"email_enabled": True}}, flat)
    assert again["quiet_hours"] == QUIET
    assert "quiet_hours" not in structured_preferences(again)
    with pytest.raises(ValueError):
        flatten_structured_preferences({"quiet_hours": {**QUIET, "timezone": "Mars/Base"}})
    with pytest.raises(ValueError):
        flatten_structured_preferences({"quiet_hours": {**QUIET, "from": "25:00"}})


def _client_with(prefs: dict) -> MagicMock:
    client = MagicMock()
    client.table.return_value.insert.return_value.execute.return_value.data = [{"id": "notif-1"}]
    client.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
        {"preferences": prefs}
    ]
    return client


def test_held_skips_email_and_slack_but_never_approvals():
    client = _client_with(flatten_structured_preferences({"quiet_hours": QUIET}))
    assert held_by_quiet_hours(client, "o", "u", "run_failed", "email", _at(22)) is True
    assert held_by_quiet_hours(client, "o", "u", "run_failed", "bell", _at(22)) is False
    assert held_by_quiet_hours(client, "o", "u", "approval_needed", "slack", _at(22)) is False
    assert held_by_quiet_hours(client, "o", "u", "run_failed", "email", _at(12)) is False


def test_emitter_keeps_inbox_row_and_skips_email_and_slack_during_quiet_hours():
    prefs = flatten_structured_preferences(
        {"quiet_hours": QUIET, "run_failed": {"email_enabled": True, "slack_enabled": True}}
    )
    client = _client_with(prefs)
    with (
        patch("app.services.notification_preference_service.quiet_hours_active", return_value=True),
        patch("app.services.notification_emitter._send_email_if_configured") as email,
        patch("app.services.notification_emitter._send_slack_dm_if_configured") as slack,
        patch("app.services.notification_emitter._publish_live_notification") as bell,
    ):
        notification_id = emit_notification(
            client, org_id="o", user_id="u", event_type="run_failed", title="t", body="b",
            channel_hints={"email": True, "slack": True},
        )
    assert notification_id == "notif-1"
    email.assert_not_called()
    slack.assert_not_called()
    bell.assert_called_once()
