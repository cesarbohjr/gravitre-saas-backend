"""Clay tool executors."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.services.clay_tools import CLAY_TOOL_EXECUTORS
from app.services.tool_service import list_registered_actions
from app.services.tool_types import ToolContext


def _ctx() -> ToolContext:
    return ToolContext(
        settings=SimpleNamespace(disable_connectors=False),
        client=MagicMock(),
        org_id="org-1",
        actor_id="user-1",
        connector_id="conn-clay",
        environment_name="production",
    )


def test_clay_tools_registered():
    for action in CLAY_TOOL_EXECUTORS:
        assert action in list_registered_actions()


@patch("app.services.clay_tools.enforce_rate_limit")
@patch("app.services.clay_tools.resolve_clay_connector")
@patch("app.services.clay_tools.enrich_person")
def test_clay_people_enrich(mock_enrich, mock_session, _rate):
    mock_session.return_value = ("conn-clay", "key", {})
    mock_enrich.return_value = {"name": "Jane Doe"}
    result = CLAY_TOOL_EXECUTORS["clay.people.enrich"](_ctx(), {"email": "jane@acme.com"})
    assert result.success
    mock_enrich.assert_called_once()


@patch("app.services.clay_tools.enforce_rate_limit")
@patch("app.services.clay_tools.resolve_clay_connector")
@patch("app.services.clay_tools.request_enrichment")
def test_clay_leads_push(mock_push, mock_session, _rate):
    mock_session.return_value = ("conn-clay", "key", {"webhook_url": "https://app.clay.com/api/v1/webhooks/x"})
    mock_push.return_value = {"records_sent": 1}
    result = CLAY_TOOL_EXECUTORS["clay.leads.push"](_ctx(), {"records": [{"email": "a@b.com"}]})
    assert result.success
    mock_push.assert_called_once()
