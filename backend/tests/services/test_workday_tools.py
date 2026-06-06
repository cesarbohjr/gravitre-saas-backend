from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.services.workday_tools import WORKDAY_TOOL_EXECUTORS
from app.services.tool_types import ToolContext


def test_workday_tool_executors_registered():
    assert set(WORKDAY_TOOL_EXECUTORS.keys()) == {
        "workday.workers.get",
        "workday.orgunits.list",
        "workday.timeoff.balance.get",
        "workday.positions.list",
    }


def test_workday_workers_get_success():
    settings = SimpleNamespace(disable_connectors=False, connector_secrets_encryption_key="k" * 32)
    tool_ctx = ToolContext(
        settings=settings,
        client=MagicMock(),
        org_id="org-1",
        actor_id="user-1",
        agent_id="agent-hr",
        environment_name="production",
    )
    conn = {"id": "wd-conn", "type": "workday", "status": "active", "environment": "production"}
    executor = WORKDAY_TOOL_EXECUTORS["workday.workers.get"]
    with patch("app.services.workday_tools.get_connector_by_type", return_value=conn):
        with patch("app.services.workday_tools.enforce_rate_limit"):
            with patch(
                "app.services.workday_tools.ensure_workday_session",
                return_value=(
                    "access-token",
                    "impl.wd12.myworkday.com",
                    "acme",
                    "https://impl.wd12.myworkday.com/ccx/api/v1/acme",
                    None,
                ),
            ):
                with patch(
                    "app.services.workday_tools.get_worker",
                    return_value={"id": "w1", "email": "jane@example.com"},
                ):
                    result = executor(tool_ctx, {"email": "jane@example.com"})
    assert result.success is True
    assert result.data["worker"]["id"] == "w1"
