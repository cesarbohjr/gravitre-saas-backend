"""Monday.com tool executors."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.services.monday_tools import MONDAY_TOOL_EXECUTORS
from app.services.tool_service import list_registered_actions
from app.services.tool_types import ToolContext


def _ctx() -> ToolContext:
    return ToolContext(
        settings=SimpleNamespace(disable_connectors=False),
        client=MagicMock(),
        org_id="org-1",
        actor_id="user-1",
        connector_id="conn-monday",
        environment_name="production",
    )


def test_monday_tools_registered():
    for action in MONDAY_TOOL_EXECUTORS:
        assert action in list_registered_actions()


@patch("app.services.monday_tools.enforce_rate_limit")
@patch("app.services.monday_tools.ensure_monday_session")
@patch("app.services.monday_tools.list_boards")
def test_monday_boards_list(mock_list, mock_session, _rate):
    mock_session.return_value = ("conn-monday", "token")
    mock_list.return_value = {"boards": [{"id": "1", "name": "Board"}]}
    result = MONDAY_TOOL_EXECUTORS["monday.boards.list"](_ctx(), {})
    assert result.success
