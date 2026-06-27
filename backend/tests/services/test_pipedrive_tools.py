from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services.pipedrive_tools import PIPEDRIVE_TOOL_EXECUTORS
from app.services.tool_types import ToolContext


def _ctx() -> ToolContext:
    return ToolContext(
        settings=MagicMock(disable_connectors=False),
        client=MagicMock(),
        org_id="org-1",
        actor_id="user-1",
        connector_id="conn-pd",
    )


@patch("app.services.pipedrive_tools.enforce_rate_limit")
@patch("app.services.pipedrive_tools.ensure_pipedrive_session")
def test_pipedrive_persons_search(mock_session, _rate):
    mock_session.return_value = ("conn-pd", "token", "https://acme.pipedrive.com")
    executor = PIPEDRIVE_TOOL_EXECUTORS["pipedrive.persons.search"]
    with patch(
        "app.services.pipedrive_tools.search_persons",
        return_value={"success": True, "data": {"items": []}},
    ):
        result = executor(_ctx(), {"term": "Jane", "connector_id": "conn-pd"})
    assert result.success is True
    assert result.action == "pipedrive.persons.search"


@patch("app.services.pipedrive_tools.enforce_rate_limit")
@patch("app.services.pipedrive_tools.ensure_pipedrive_session")
def test_pipedrive_deals_update_stage(mock_session, _rate):
    mock_session.return_value = ("conn-pd", "token", "https://acme.pipedrive.com")
    executor = PIPEDRIVE_TOOL_EXECUTORS["pipedrive.deals.update_stage"]
    with patch(
        "app.services.pipedrive_tools.update_deal",
        return_value={"success": True, "data": {"id": 1, "stage_id": 2}},
    ):
        result = executor(_ctx(), {"deal_id": "1", "stage_id": 2, "connector_id": "conn-pd"})
    assert result.success is True
    assert result.action == "pipedrive.deals.update_stage"
