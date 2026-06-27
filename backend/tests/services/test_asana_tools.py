"""Asana tool executors."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.services.asana_tools import ASANA_TOOL_EXECUTORS
from app.services.tool_service import list_registered_actions
from app.services.tool_types import ToolContext


def _ctx() -> ToolContext:
    return ToolContext(
        settings=SimpleNamespace(disable_connectors=False),
        client=MagicMock(),
        org_id="org-1",
        actor_id="user-1",
        connector_id="conn-asana",
        environment_name="production",
    )


def test_asana_tools_registered():
    for action in ASANA_TOOL_EXECUTORS:
        assert action in list_registered_actions()


@patch("app.services.asana_tools.enforce_rate_limit")
@patch("app.services.asana_tools.ensure_asana_session")
@patch("app.services.asana_tools.get_task")
def test_asana_tasks_get(mock_get, mock_session, _rate):
    mock_session.return_value = ("conn-asana", "token")
    mock_get.return_value = {"gid": "123", "name": "Task"}
    result = ASANA_TOOL_EXECUTORS["asana.tasks.get"](_ctx(), {"task_id": "123"})
    assert result.success
