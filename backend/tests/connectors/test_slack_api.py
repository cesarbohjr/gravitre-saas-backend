from __future__ import annotations

from unittest.mock import patch

import pytest

from app.connectors.slack import (
    conversation_history,
    list_conversations,
    list_users,
    slack_api_call,
)


def test_list_conversations():
    with patch("app.connectors.slack.httpx.Client") as client_cls:
        response = client_cls.return_value.__enter__.return_value.get.return_value
        response.is_success = True
        response.text = '{"ok": true, "channels": [{"id": "C1"}]}'
        response.json.return_value = {"ok": True, "channels": [{"id": "C1"}]}
        data = list_conversations("xoxb-test", limit=50)
    assert data["channels"][0]["id"] == "C1"


def test_conversation_history_requires_channel():
    with pytest.raises(ValueError, match="channel"):
        conversation_history("xoxb-test", "")


def test_list_users():
    with patch("app.connectors.slack.httpx.Client") as client_cls:
        response = client_cls.return_value.__enter__.return_value.get.return_value
        response.is_success = True
        response.text = '{"ok": true, "members": [{"id": "U1"}]}'
        response.json.return_value = {"ok": True, "members": [{"id": "U1"}]}
        data = list_users("xoxb-test")
    assert data["members"][0]["id"] == "U1"


def test_slack_api_call_ok_false():
    with patch("app.connectors.slack.httpx.Client") as client_cls:
        response = client_cls.return_value.__enter__.return_value.get.return_value
        response.is_success = True
        response.text = '{"ok": false, "error": "invalid_auth"}'
        response.json.return_value = {"ok": False, "error": "invalid_auth"}
        with pytest.raises(ValueError, match="invalid_auth"):
            slack_api_call("bad-token", "users.list")
