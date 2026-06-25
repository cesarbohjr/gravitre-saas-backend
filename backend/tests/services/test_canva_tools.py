"""Canva tool executors."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.services.canva_tools import CANVA_TOOL_EXECUTORS
from app.services.tool_service import list_registered_actions
from app.services.tool_types import ToolContext


def _ctx() -> ToolContext:
    return ToolContext(
        settings=SimpleNamespace(disable_connectors=False),
        client=MagicMock(),
        org_id="org-1",
        actor_id="user-1",
        connector_id="conn-canva",
        environment_name="production",
    )


def test_canva_tools_registered():
    for action in CANVA_TOOL_EXECUTORS:
        assert action in list_registered_actions()


@patch("app.services.canva_tools.enforce_rate_limit")
@patch("app.services.canva_tools.ensure_canva_session")
@patch("app.services.canva_tools.list_designs")
def test_canva_designs_list(mock_list, mock_session, _rate):
    mock_session.return_value = ("conn-canva", "token")
    mock_list.return_value = {"items": [{"id": "D1", "title": "Poster"}]}
    result = CANVA_TOOL_EXECUTORS["canva.designs.list"](_ctx(), {})
    assert result.success
    assert result.data["items"][0]["id"] == "D1"


@patch("app.services.canva_tools.enforce_rate_limit")
@patch("app.services.canva_tools.ensure_canva_session")
@patch("app.services.canva_tools.get_export")
def test_canva_exports_get(mock_get, mock_session, _rate):
    mock_session.return_value = ("conn-canva", "token")
    mock_get.return_value = {"job": {"id": "E1", "status": "success"}}
    result = CANVA_TOOL_EXECUTORS["canva.exports.get"](_ctx(), {"export_id": "E1"})
    assert result.success
    mock_get.assert_called_once_with("token", "E1")
