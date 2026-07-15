"""People Data Labs tool executors (BYO)."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.intelligence_packs.shared.auth_mode import AuthMode, get_auth_mode
from app.services.pdl_tools import PDL_TOOL_EXECUTORS
from app.services.tool_service import list_registered_actions
from app.services.tool_types import ToolContext


def _ctx() -> ToolContext:
    return ToolContext(
        settings=SimpleNamespace(disable_connectors=False),
        client=MagicMock(),
        org_id="org-1",
        actor_id="user-1",
        connector_id="conn-pdl",
        environment_name="production",
    )


def test_pdl_is_byo_required():
    assert get_auth_mode("pdl") == AuthMode.BYO_REQUIRED


def test_pdl_tools_registered():
    for action in PDL_TOOL_EXECUTORS:
        assert action in list_registered_actions()


@patch("app.services.pdl_tools.enforce_rate_limit")
@patch("app.services.pdl_tools.resolve_pdl_connector")
@patch("app.services.pdl_tools.company_enrich")
def test_pdl_company_enrich(mock_api, mock_session, _rate):
    mock_session.return_value = ("conn-pdl", "key")
    mock_api.return_value = {"data": {"name": "Acme"}, "result_url": "https://dashboard.peopledatalabs.com/"}
    result = PDL_TOOL_EXECUTORS["pdl.company.enrich"](_ctx(), {"website": "acme.com"})
    assert result.success
    mock_api.assert_called_once()
