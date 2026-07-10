"""ReAct write actions must not execute without format_write_approval_message gate."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.operators.react_engine import ReActEngine
from app.services.connector_action_workflows import format_write_approval_message
from app.services.react_write_gate import (
    WRITE_APPROVAL_REQUIRED,
    block_react_write_execution,
    materialize_react_write_approval_turn,
    pending_write_from_react,
    plan_from_react_write,
    tool_requires_user_write_approval,
)
from app.services.tool_types import ToolContext


@pytest.fixture
def tool_ctx() -> ToolContext:
    return ToolContext(
        settings=SimpleNamespace(disable_connectors=False),
        client=MagicMock(),
        org_id="org-1",
        actor_id="user-1",
    )


def test_apollo_lists_create_requires_write_approval():
    from app.services.tool_registry import get_tool_registry

    registry = get_tool_registry()
    requires, action, integration, label = tool_requires_user_write_approval(
        "apollo_lists_create", registry
    )
    assert requires is True
    assert action == "apollo.lists.create"
    assert integration == "apollo"
    assert "list" in label.lower() or "contact" in label.lower()


def test_apollo_lists_list_is_read_not_gated():
    from app.services.tool_registry import get_tool_registry

    registry = get_tool_registry()
    requires, action, _, _ = tool_requires_user_write_approval("apollo_lists_list", registry)
    assert requires is False
    assert action == "apollo.lists.list"


def test_block_react_write_does_not_call_through():
    from app.services.tool_registry import get_tool_registry

    registry = get_tool_registry()
    blocked = block_react_write_execution(
        "apollo_lists_create",
        {"name": "MSP Prospects", "modality": "contacts"},
        registry,
    )
    assert blocked is not None
    assert blocked["pending_approval"] is True
    assert blocked["success"] is False
    assert blocked["error_code"] == WRITE_APPROVAL_REQUIRED
    assert blocked["args"]["name"] == "MSP Prospects"
    assert "approval_id" not in blocked["args"]


@pytest.mark.asyncio
async def test_react_engine_blocks_write_before_registry(tool_ctx: ToolContext):
    from app.services.tool_registry import get_tool_registry

    registry = get_tool_registry()
    registry.execute_tool = AsyncMock()  # type: ignore[method-assign]
    engine = ReActEngine(settings=SimpleNamespace(disable_ai=False), registry=registry)

    result = await engine._execute_tool_call(
        tool_ctx,
        "apollo_lists_create",
        {"name": "MSP Prospects"},
        allowed_tool_names={"apollo_lists_create"},
    )

    assert result["pending_approval"] is True
    assert result["error_code"] == WRITE_APPROVAL_REQUIRED
    registry.execute_tool.assert_not_called()


@pytest.mark.asyncio
async def test_react_engine_allows_read_tools(tool_ctx: ToolContext):
    from app.services.tool_registry import get_tool_registry

    registry = get_tool_registry()
    registry.execute_tool = AsyncMock(return_value={"success": True, "result": {"labels": []}})  # type: ignore[method-assign]
    engine = ReActEngine(settings=SimpleNamespace(disable_ai=False), registry=registry)

    result = await engine._execute_tool_call(
        tool_ctx,
        "apollo_lists_list",
        {},
        allowed_tool_names={"apollo_lists_list"},
    )

    assert result["success"] is True
    registry.execute_tool.assert_awaited_once()


def test_pending_write_from_react_extracts_blocked_call():
    react = SimpleNamespace(
        tool_calls=[
            {
                "tool": "assistant_connector_status",
                "result": {"success": True},
            },
            {
                "tool": "apollo_lists_create",
                "args": {"name": "MSP Prospects"},
                "result": {
                    "success": False,
                    "pending_approval": True,
                    "error_code": WRITE_APPROVAL_REQUIRED,
                    "action": "apollo.lists.create",
                    "integration": "apollo",
                    "label": "Create contact list",
                    "args": {"name": "MSP Prospects"},
                },
            },
        ]
    )
    pending = pending_write_from_react(react)
    assert pending is not None
    plan = plan_from_react_write(pending)
    assert plan is not None
    assert plan.invoke_action == "apollo.lists.create"
    assert plan.requires_approval is True
    message = format_write_approval_message(plan)
    assert "MSP Prospects" in message
    assert "yes" in message.lower()


@pytest.mark.asyncio
async def test_materialize_react_write_approval_persists_awaiting_confirm():
    react = SimpleNamespace(
        tool_calls=[
            {
                "tool": "apollo_lists_create",
                "args": {"name": "MSP Prospects", "modality": "contacts"},
                "result": {
                    "success": False,
                    "pending_approval": True,
                    "error_code": WRITE_APPROVAL_REQUIRED,
                    "action": "apollo.lists.create",
                    "integration": "apollo",
                    "label": "Create contact list",
                    "args": {"name": "MSP Prospects", "modality": "contacts"},
                },
            }
        ]
    )
    state = MagicMock()
    state.update_task_state = AsyncMock()
    state.get_task_state = AsyncMock(
        return_value={
            "pending_task": {
                "type": "connector_action",
                "status": "awaiting_confirm",
                "params": {"invoke_action": "apollo.lists.create"},
            }
        }
    )
    with patch(
        "app.services.conversation_state_service.get_conversation_state_service",
        return_value=state,
    ):
        turn = await materialize_react_write_approval_turn(
            settings=SimpleNamespace(),
            org_id="org-1",
            conversation_id="conv-1",
            client=MagicMock(),
            react_result=react,
        )

    assert turn is not None
    assert turn["dialogue_mode"] == "confirm"
    assert "MSP Prospects" in turn["message"]
    assert turn["stop_pipeline"] is True
    state.update_task_state.assert_awaited_once()
    saved = state.update_task_state.await_args.args[2]
    assert saved["pending_task"]["status"] == "awaiting_confirm"
    assert saved["pending_task"]["params"]["invoke_action"] == "apollo.lists.create"
