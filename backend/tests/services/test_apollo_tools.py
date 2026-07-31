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
@patch("app.services.apollo_tools.search_people")
def test_apollo_people_search_plan_limit_is_permission_denied(mock_search, mock_session, _rate):
    from app.connectors.apollo_api import ApolloAPIError
    from app.services.tool_types import ToolPermissionDeniedError

    mock_session.return_value = ("conn-apollo", {"Authorization": "Bearer token"})
    mock_search.side_effect = ApolloAPIError(
        "Apollo API 403: /mixed_people/api_search — not accessible with this access token on a free plan. Please upgrade your plan.",
        status_code=403,
        details={"error": "api/v1/mixed_people/api_search is not accessible with this access token on a free plan"},
    )
    try:
        APOLLO_TOOL_EXECUTORS["apollo.people.search"](_ctx(), {"person_titles": ["CEO"]})
        assert False, "expected ToolPermissionDeniedError"
    except ToolPermissionDeniedError as exc:
        assert exc.code == "permission_denied"
        assert "free plan" in str(exc).lower() or "upgrade" in str(exc).lower()
        assert (exc.details or {}).get("reason") == "apollo_plan_limit"


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


@patch("app.services.apollo_tools.enforce_rate_limit")
@patch("app.services.apollo_tools.resolve_apollo_connector")
@patch("app.services.apollo_tools.add_entity_ids_to_label_names")
def test_apollo_lists_add(mock_add, mock_session, _rate):
    mock_session.return_value = ("conn-apollo", {"Authorization": "Bearer token"})
    mock_add.return_value = {"ok": True}
    result = APOLLO_TOOL_EXECUTORS["apollo.lists.add"](
        _ctx(),
        {
            "entity_ids": ["c1", "c2"],
            "label_names": ["MSP Prospects"],
            "modality": "contacts",
        },
    )
    assert result.success
    assert result.action == "apollo.lists.add"
    mock_add.assert_called_once_with(
        {"Authorization": "Bearer token"},
        entity_ids=["c1", "c2"],
        label_names=["MSP Prospects"],
        modality="contacts",
    )


@patch("app.services.apollo_tools.enforce_rate_limit")
@patch("app.services.apollo_tools.resolve_apollo_connector")
@patch("app.services.apollo_tools.list_labels")
@patch("app.services.apollo_tools.search_contacts")
def test_apollo_contacts_search_resolves_list_name(mock_search, mock_labels, mock_session, _rate):
    mock_session.return_value = ("conn-apollo", {"Authorization": "Bearer token"})
    mock_labels.return_value = {
        "labels": [{"id": "lab-msp", "name": "MSP Prospects", "modality": "contacts"}]
    }
    mock_search.return_value = {"contacts": [{"id": "c1"}], "pagination": {"page": 1}}
    result = APOLLO_TOOL_EXECUTORS["apollo.contacts.search"](
        _ctx(), {"list_name": "MSP Prospects", "per_page": 10}
    )
    assert result.success
    assert result.action == "apollo.contacts.search"
    assert result.data["contact_count"] == 1
    mock_search.assert_called_once_with(
        {"Authorization": "Bearer token"},
        payload={"contact_label_ids": ["lab-msp"], "per_page": 10},
    )


@patch("app.services.apollo_tools.enforce_rate_limit")
@patch("app.services.apollo_tools.resolve_apollo_connector")
@patch("app.services.apollo_tools.match_person")
def test_apollo_people_match(mock_match, mock_session, _rate):
    mock_session.return_value = ("conn-apollo", {"Authorization": "Bearer token"})
    mock_match.return_value = {"person": {"id": "p1", "name": "Tim Zheng"}}
    result = APOLLO_TOOL_EXECUTORS["apollo.people.match"](
        _ctx(), {"email": "tim@apollo.io", "domain": "apollo.io"}
    )
    assert result.success
    assert result.action == "apollo.people.match"
    assert result.data["result_url"] == "https://app.apollo.io/#/people/p1"
    mock_match.assert_called_once()


@patch("app.services.apollo_tools.enforce_rate_limit")
@patch("app.services.apollo_tools.resolve_apollo_connector")
@patch("app.services.apollo_tools.enrich_organization")
def test_apollo_organizations_enrich(mock_enrich, mock_session, _rate):
    mock_session.return_value = ("conn-apollo", {"Authorization": "Bearer token"})
    mock_enrich.return_value = {"organization": {"id": "o1", "name": "Apollo"}}
    result = APOLLO_TOOL_EXECUTORS["apollo.organizations.enrich"](_ctx(), {"domain": "apollo.io"})
    assert result.success
    assert result.action == "apollo.organizations.enrich"
    assert result.data["result_url"] == "https://app.apollo.io/#/organizations/o1"
    mock_enrich.assert_called_once()
