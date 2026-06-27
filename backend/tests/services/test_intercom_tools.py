"""Intercom tool executors."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.services.intercom_tools import INTERCOM_TOOL_EXECUTORS
from app.services.tool_service import list_registered_actions
from app.services.tool_types import ToolContext


def _ctx() -> ToolContext:
    return ToolContext(
        settings=SimpleNamespace(disable_connectors=False),
        client=MagicMock(),
        org_id="org-1",
        actor_id="user-1",
        connector_id="conn-ic",
        environment_name="production",
    )


def test_intercom_tools_registered():
    for action in INTERCOM_TOOL_EXECUTORS:
        assert action in list_registered_actions()


@patch("app.services.intercom_tools.enforce_rate_limit")
@patch("app.services.intercom_tools.ensure_intercom_session")
@patch("app.services.intercom_tools.get_contact")
def test_intercom_contacts_get(mock_get, mock_session, _rate):
    mock_session.return_value = ("conn-ic", "token")
    mock_get.return_value = {"id": "contact-1", "email": "a@example.com"}
    result = INTERCOM_TOOL_EXECUTORS["intercom.contacts.get"](_ctx(), {"contact_id": "contact-1"})
    assert result.success
    mock_get.assert_called_once_with("token", "contact-1")


@patch("app.services.intercom_tools.enforce_rate_limit")
@patch("app.services.intercom_tools.ensure_intercom_session")
@patch("app.services.intercom_tools.list_conversations")
def test_intercom_conversations_list(mock_list, mock_session, _rate):
    mock_session.return_value = ("conn-ic", "token")
    mock_list.return_value = {"conversations": [{"id": "conv-1"}]}
    result = INTERCOM_TOOL_EXECUTORS["intercom.conversations.list"](_ctx(), {})
    assert result.success
