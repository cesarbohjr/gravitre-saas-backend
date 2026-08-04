from __future__ import annotations

from unittest.mock import patch

from app.connectors.microsoft365 import (
    _graph_user_root,
    create_calendar_event,
    get_user,
    list_calendar_events,
    list_mail_messages,
    send_mail,
)


def test_graph_user_root_uses_me_alias():
    assert _graph_user_root("me") == "/me"
    assert _graph_user_root("") == "/me"
    assert _graph_user_root("abc-123") == "/users/abc-123"


def test_get_user():
    with patch("app.connectors.microsoft365._request") as req:
        req.return_value = {"id": "me", "displayName": "Test User"}
        out = get_user("token")
    assert out["displayName"] == "Test User"
    # Personal MSA tokens reject /users/me — signed-in path is /me.
    req.assert_called_once_with("token", "GET", "/me")


def test_list_mail_messages():
    with patch("app.connectors.microsoft365._request") as req:
        req.return_value = {"value": [{"id": "msg-1"}]}
        out = list_mail_messages("token", top=10)
    assert out["value"][0]["id"] == "msg-1"
    assert req.call_args[0][2] == "/me/messages"
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
    assert req.call_args[0][2] == "/me/calendar/events"
    params = req.call_args[1]["params"]
    assert "start/dateTime ge" in params["$filter"]


def test_send_mail_uses_me_root():
    with patch("app.connectors.microsoft365._request") as req:
        req.return_value = {}
        send_mail("token", subject="Hi", body="Body", to_recipients=["a@example.com"])
    assert req.call_args[0][2] == "/me/sendMail"


def test_create_calendar_event_uses_me_root():
    with patch("app.connectors.microsoft365._request") as req:
        req.return_value = {"id": "evt-1"}
        create_calendar_event(
            "token",
            subject="Meet",
            start_datetime="2026-08-20T15:00:00",
            end_datetime="2026-08-20T16:00:00",
        )
    assert req.call_args[0][2] == "/me/calendar/events"
