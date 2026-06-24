"""Constant Contact tool executors."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.services.constant_contact_tools import CONSTANT_CONTACT_TOOL_EXECUTORS
from app.services.tool_service import list_registered_actions
from app.services.tool_types import ToolContext


def _ctx() -> ToolContext:
    return ToolContext(
        settings=SimpleNamespace(disable_connectors=False),
        client=MagicMock(),
        org_id="org-1",
        actor_id="user-1",
        connector_id="conn-cc",
        environment_name="production",
    )


def test_constant_contact_tools_registered():
    for action in (
        "constant_contact.contacts.list",
        "constant_contact.contacts.get",
        "constant_contact.campaigns.list",
        "constant_contact.contacts.create",
        "constant_contact.contacts.update",
        "constant_contact.campaigns.create",
        "constant_contact.lists.add_contacts",
        "constant_contact.tags.apply",
        "constant_contact.campaigns.schedule",
    ):
        assert action in CONSTANT_CONTACT_TOOL_EXECUTORS
        assert action in list_registered_actions()


@patch("app.services.constant_contact_tools.enforce_rate_limit")
@patch("app.services.constant_contact_tools.ensure_constant_contact_session")
@patch("app.services.constant_contact_tools.list_contacts")
def test_constant_contact_contacts_list(mock_list, mock_session, _rate):
    mock_session.return_value = ("conn-cc", "token")
    mock_list.return_value = {"contacts": [{"contact_id": "abc"}]}
    result = CONSTANT_CONTACT_TOOL_EXECUTORS["constant_contact.contacts.list"](_ctx(), {"limit": 10})
    assert result.success
    assert result.data["contacts"][0]["contact_id"] == "abc"
    mock_list.assert_called_once()


@patch("app.services.constant_contact_tools.enforce_rate_limit")
@patch("app.services.constant_contact_tools.ensure_constant_contact_session")
@patch("app.services.constant_contact_tools.list_email_campaigns")
def test_constant_contact_campaigns_list(mock_list, mock_session, _rate):
    mock_session.return_value = ("conn-cc", "token")
    mock_list.return_value = {"campaigns": [{"campaign_id": "camp-1"}]}
    result = CONSTANT_CONTACT_TOOL_EXECUTORS["constant_contact.campaigns.list"](_ctx(), {})
    assert result.success
    assert result.data["campaigns"][0]["campaign_id"] == "camp-1"


@patch("app.services.constant_contact_tools.enforce_rate_limit")
@patch("app.services.constant_contact_tools.ensure_constant_contact_session")
@patch("app.services.constant_contact_tools.add_list_memberships")
def test_constant_contact_lists_add_contacts(mock_add, mock_session, _rate):
    mock_session.return_value = ("conn-cc", "token")
    mock_add.return_value = {"activity_id": "act-1"}
    result = CONSTANT_CONTACT_TOOL_EXECUTORS["constant_contact.lists.add_contacts"](
        _ctx(),
        {"contact_ids": ["c1"], "list_ids": ["l1"]},
    )
    assert result.success
    mock_add.assert_called_once_with(
        "token",
        source={"contact_ids": ["c1"]},
        list_ids=["l1"],
    )


@patch("app.services.constant_contact_tools.enforce_rate_limit")
@patch("app.services.constant_contact_tools.ensure_constant_contact_session")
@patch("app.services.constant_contact_tools.schedule_email_campaign")
def test_constant_contact_campaigns_schedule(mock_schedule, mock_session, _rate):
    mock_session.return_value = ("conn-cc", "token")
    mock_schedule.return_value = {"scheduled_date": "0"}
    result = CONSTANT_CONTACT_TOOL_EXECUTORS["constant_contact.campaigns.schedule"](
        _ctx(),
        {"campaign_activity_id": "activity-1", "scheduled_date": "0"},
    )
    assert result.success
    mock_schedule.assert_called_once_with("token", "activity-1", scheduled_date="0")
