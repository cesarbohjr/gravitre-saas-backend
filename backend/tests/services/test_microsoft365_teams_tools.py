"""Microsoft 365 Teams + SharePoint tool executors."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.services.microsoft365_teams_tools import MICROSOFT365_TEAMS_SHAREPOINT_TOOLS
from app.services.tool_service import list_registered_actions
from app.services.tool_types import ToolContext


def _ctx() -> ToolContext:
    return ToolContext(
        settings=SimpleNamespace(disable_connectors=False),
        client=MagicMock(),
        org_id="org-1",
        actor_id="user-1",
        connector_id="conn-m365",
        environment_name="production",
    )


def test_m365_teams_sharepoint_registered():
    for action in (
        "microsoft365.teams.list",
        "microsoft365.sharepoint.sites.list",
        "microsoft365.sharepoint.files.delete",
    ):
        assert action in list_registered_actions()


@patch("app.services.microsoft365_teams_tools.enforce_rate_limit")
@patch("app.services.microsoft365_teams_tools.resolve_microsoft365_access_token")
@patch("app.services.microsoft365_teams_tools.get_connector")
@patch("app.services.microsoft365_teams_tools.list_joined_teams")
def test_teams_list(mock_list, mock_conn, mock_token, _rate):
    mock_conn.return_value = {"id": "conn-m365"}
    mock_token.return_value = "token"
    mock_list.return_value = {"value": [{"id": "t1"}]}
    result = MICROSOFT365_TEAMS_SHAREPOINT_TOOLS["microsoft365.teams.list"](_ctx(), {})
    assert result.success


@patch("app.services.microsoft365_teams_tools.enforce_rate_limit")
@patch("app.services.microsoft365_teams_tools.resolve_microsoft365_access_token")
@patch("app.services.microsoft365_teams_tools.get_connector")
@patch("app.services.microsoft365_teams_tools.search_sharepoint_sites")
def test_sharepoint_sites_list(mock_search, mock_conn, mock_token, _rate):
    mock_conn.return_value = {"id": "conn-m365"}
    mock_token.return_value = "token"
    mock_search.return_value = {"value": []}
    result = MICROSOFT365_TEAMS_SHAREPOINT_TOOLS["microsoft365.sharepoint.sites.list"](
        _ctx(), {"query": "marketing"}
    )
    assert result.success


def test_microsoft_teams_legacy_alias():
    assert "microsoft_teams.teams.list" in MICROSOFT365_TEAMS_SHAREPOINT_TOOLS
    assert MICROSOFT365_TEAMS_SHAREPOINT_TOOLS["microsoft_teams.teams.list"] is MICROSOFT365_TEAMS_SHAREPOINT_TOOLS[
        "microsoft365.teams.list"
    ]
