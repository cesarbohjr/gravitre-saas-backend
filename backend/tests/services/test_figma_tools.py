"""Figma tool executors."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.services.figma_tools import FIGMA_TOOL_EXECUTORS
from app.services.tool_service import list_registered_actions
from app.services.tool_types import ToolContext


def _ctx() -> ToolContext:
    return ToolContext(
        settings=SimpleNamespace(disable_connectors=False),
        client=MagicMock(),
        org_id="org-1",
        actor_id="user-1",
        connector_id="conn-figma",
        environment_name="production",
    )


def test_figma_tools_registered():
    for action in FIGMA_TOOL_EXECUTORS:
        assert action in list_registered_actions()


@patch("app.services.figma_tools.enforce_rate_limit")
@patch("app.services.figma_tools.ensure_figma_session")
@patch("app.services.figma_tools.get_file_meta")
def test_figma_files_meta(mock_meta, mock_session, _rate):
    mock_session.return_value = ("conn-figma", "token")
    mock_meta.return_value = {"name": "Landing page", "file_key": "abc123"}
    result = FIGMA_TOOL_EXECUTORS["figma.files.meta"](_ctx(), {"file_key": "abc123"})
    assert result.success
    mock_meta.assert_called_once_with("token", "abc123")


@patch("app.services.figma_tools.enforce_rate_limit")
@patch("app.services.figma_tools.ensure_figma_session")
@patch("app.services.figma_tools.get_me")
def test_figma_users_me(mock_me, mock_session, _rate):
    mock_session.return_value = ("conn-figma", "token")
    mock_me.return_value = {"id": "u1", "email": "a@example.com"}
    result = FIGMA_TOOL_EXECUTORS["figma.users.me"](_ctx(), {})
    assert result.success
