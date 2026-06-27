from __future__ import annotations

from unittest.mock import patch

from app.connectors.microsoft365 import get_user, list_calendar_events, list_mail_messages


def test_get_user():
    with patch("app.connectors.microsoft365._request") as req:
        req.return_value = {"id": "me", "displayName": "Test User"}
        out = get_user("token")
    assert out["displayName"] == "Test User"
    req.assert_called_once_with("token", "GET", "/users/me")


def test_list_mail_messages():
    with patch("app.connectors.microsoft365._request") as req:
        req.return_value = {"value": [{"id": "msg-1"}]}
        out = list_mail_messages("token", top=10)
    assert out["value"][0]["id"] == "msg-1"
    params = req.call_args[1]["params"]
    assert params["$top"] == 10


def test_list_calendar_events_with_filter():
    with patch("app.connectors.microsoft365._request") as req:
        req.return_value = {"value": []}
        list_calendar_events(
            "token",
            start_datetime="2026-06-01T00:00:00Z",
            end_datetime="2026-06-07T23:59:59Z",
        )
    params = req.call_args[1]["params"]
    assert "start/dateTime ge" in params["$filter"]
