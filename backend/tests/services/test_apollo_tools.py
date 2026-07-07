"""Apollo tool executors."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.services.apollo_tools import APOLLO_TOOL_EXECUTORS
from app.services.tool_service import list_registered_actions
from app.services.tool_types import ToolContext


def _ctx() -> ToolContext:
    return ToolContext(
        settings=SimpleNamespace(disable_connectors=False),
        client=MagicMock(),
        org_id="org-1",
        actor_id="user-1",
        connector_id="conn-apollo",
        environment_name="production",
    )


def test_apollo_tools_registered():
    for action in APOLLO_TOOL_EXECUTORS:
        assert action in list_registered_actions()


@patch("app.services.apollo_tools.enforce_rate_limit")
@patch("app.services.apollo_tools.resolve_apollo_connector")
@patch("app.services.apollo_tools.search_people")
def test_apollo_people_search(mock_search, mock_session, _rate):
    mock_session.return_value = ("conn-apollo", {"Authorization": "Bearer token"})
    mock_search.return_value = {"people": [], "pagination": {"page": 1}}
    result = APOLLO_TOOL_EXECUTORS["apollo.people.search"](_ctx(), {"person_titles": ["CEO"]})
    assert result.success
    mock_search.assert_called_once()


@patch("app.services.apollo_tools.enforce_rate_limit")
@patch("app.services.apollo_tools.resolve_apollo_connector")
@patch("app.services.apollo_tools.create_contact")
def test_apollo_contacts_create(mock_create, mock_session, _rate):
    mock_session.return_value = ("conn-apollo", {"Authorization": "Bearer token"})
    mock_create.return_value = {"contact": {"id": "c1"}}
    result = APOLLO_TOOL_EXECUTORS["apollo.contacts.create"](
        _ctx(), {"first_name": "Ada", "last_name": "Lovelace", "email": "ada@example.com"}
    )
    assert result.success


@patch("app.services.apollo_tools.enforce_rate_limit")
@patch("app.services.apollo_tools.resolve_apollo_connector")
@patch("app.services.apollo_tools.delete_contact")
def test_apollo_contacts_delete(mock_delete, mock_session, _rate):
    mock_session.return_value = ("conn-apollo", {"Authorization": "Bearer token"})
    mock_delete.return_value = {"success": True}
    result = APOLLO_TOOL_EXECUTORS["apollo.contacts.delete"](_ctx(), {"contact_id": "c1"})
    assert result.success
    mock_delete.assert_called_once_with({"Authorization": "Bearer token"}, "c1")


@patch("app.services.apollo_tools.enforce_rate_limit")
@patch("app.services.apollo_tools.resolve_apollo_connector")
@patch("app.services.apollo_tools.create_label")
def test_apollo_lists_create(mock_create_label, mock_session, _rate):
    mock_session.return_value = ("conn-apollo", {"Authorization": "Bearer token"})
    mock_create_label.return_value = {"label": {"id": "l1", "name": "MSP Prospects"}}
    result = APOLLO_TOOL_EXECUTORS["apollo.lists.create"](
        _ctx(), {"name": "MSP Prospects", "modality": "contacts"}
    )
    assert result.success
    assert result.action == "apollo.lists.create"
    mock_create_label.assert_called_once()
