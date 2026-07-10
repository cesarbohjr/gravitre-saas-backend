"""Permanent regression: apollo.lists.create must reach Apollo under ReAct-first chat.

Live failure (2026-07-10): ReAct called apollo_lists_create with ToolContext.agent_id=
\"synthetic-default\". assert_agent_tool_permission queried agent_tool_permissions
(UUID column) and crashed before invoke_tool audited or called Apollo. Chat reported
a generic \"connector execution error\" while connector health stayed green.

Governed chat path (no agent_id) still worked on 2026-07-07 (tool.invoke.completed).
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.services.agent_tool_permissions import assert_agent_tool_permission
from app.services.apollo_tools import APOLLO_TOOL_EXECUTORS
from app.services.tool_service import invoke_tool
from app.services.tool_types import ToolContext


def _ctx(*, agent_id: str | None) -> ToolContext:
    return ToolContext(
        settings=SimpleNamespace(
            disable_connectors=False,
            private_connector_runtime_enabled=False,
        ),
        client=MagicMock(),
        org_id="11111111-1111-1111-1111-111111111111",
        actor_id="user-1",
        agent_id=agent_id,
        environment_name="production",
    )


def test_synthetic_default_permission_check_does_not_query_uuid_table():
    client = MagicMock()

    def _boom(*_a, **_k):
        raise AssertionError("must not query agent_tool_permissions for synthetic agents")

    client.table.side_effect = _boom
    ctx = ToolContext(
        settings=SimpleNamespace(disable_connectors=False, private_connector_runtime_enabled=False),
        client=client,
        org_id="11111111-1111-1111-1111-111111111111",
        actor_id="user-1",
        agent_id="synthetic-default",
        environment_name="production",
    )
    assert_agent_tool_permission(ctx, "apollo.lists.create", None, "apollo")
    client.table.assert_not_called()


@patch("app.services.tool_service._write_tool_audit")
@patch("app.services.apollo_tools.enforce_rate_limit")
@patch("app.services.apollo_tools.resolve_apollo_connector")
@patch("app.services.apollo_tools.create_label")
def test_invoke_tool_apollo_lists_create_with_synthetic_agent_reaches_apollo(
    mock_create_label,
    mock_session,
    _rate,
    mock_audit,
):
    mock_session.return_value = ("30f734a2-dbdb-45aa-9112-19c6d604d451", {"Authorization": "Bearer tok"})
    mock_create_label.return_value = {"label": {"id": "l1", "name": "MSP Prospects"}}

    result = invoke_tool(
        _ctx(agent_id="synthetic-default"),
        "apollo.lists.create",
        {"name": "MSP Prospects", "modality": "contacts"},
    )

    assert result.success is True
    assert result.action == "apollo.lists.create"
    mock_create_label.assert_called_once()
    assert any(call.args[3] == "tool.invoke.requested" for call in mock_audit.call_args_list)
    assert any(call.args[3] == "tool.invoke.completed" for call in mock_audit.call_args_list)


@pytest.mark.asyncio
async def test_tool_registry_execute_apollo_lists_create_under_synthetic_agent():
    from app.services.tool_registry import ToolRegistry

    registry = ToolRegistry()
    with patch("app.services.tool_registry.invoke_tool") as mock_invoke:
        mock_invoke.return_value = SimpleNamespace(
            success=True,
            data={"label": {"id": "l1", "name": "MSP Prospects"}},
            connector_id="30f734a2-dbdb-45aa-9112-19c6d604d451",
            error_message=None,
            error_code=None,
        )
        observation = await registry.execute_tool(
            ctx=_ctx(agent_id="synthetic-default"),
            tool_name="apollo_lists_create",
            args={"name": "MSP Prospects", "modality": "contacts"},
        )

    assert observation["success"] is True
    assert observation["action"] == "apollo.lists.create"
    mock_invoke.assert_called_once()
    assert mock_invoke.call_args.args[1] == "apollo.lists.create"


def test_apollo_lists_create_executor_still_registered():
    assert "apollo.lists.create" in APOLLO_TOOL_EXECUTORS
