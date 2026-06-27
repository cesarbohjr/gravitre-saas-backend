"""ClickUp tool executors."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.services.clickup_tools import CLICKUP_TOOL_EXECUTORS
from app.services.tool_service import list_registered_actions
from app.services.tool_types import ToolContext


def _ctx() -> ToolContext:
    return ToolContext(
        settings=SimpleNamespace(disable_connectors=False),
        client=MagicMock(),
        org_id="org-1",
        actor_id="user-1",
        connector_id="conn-cu",
        environment_name="production",
    )


def test_clickup_tools_registered():
    for action in CLICKUP_TOOL_EXECUTORS:
        assert action in list_registered_actions()


@patch("app.services.clickup_tools.enforce_rate_limit")
@patch("app.services.clickup_tools.ensure_clickup_session")
@patch("app.services.clickup_tools.get_task")
def test_clickup_tasks_get(mock_get, mock_session, _rate):
    mock_session.return_value = ("conn-cu", "token")
    mock_get.return_value = {"id": "task-1", "name": "Demo"}
    result = CLICKUP_TOOL_EXECUTORS["clickup.tasks.get"](_ctx(), {"task_id": "task-1"})
    assert result.success
    mock_get.assert_called_once_with("token", "task-1")


@patch("app.services.clickup_tools.enforce_rate_limit")
@patch("app.services.clickup_tools.ensure_clickup_session")
@patch("app.services.clickup_tools.list_spaces")
def test_clickup_spaces_list(mock_list, mock_session, _rate):
    mock_session.return_value = ("conn-cu", "token")
    mock_list.return_value = {"spaces": [{"id": "space-1"}]}
    result = CLICKUP_TOOL_EXECUTORS["clickup.spaces.list"](_ctx(), {})
    assert result.success
    assert result.data["spaces"][0]["id"] == "space-1"
