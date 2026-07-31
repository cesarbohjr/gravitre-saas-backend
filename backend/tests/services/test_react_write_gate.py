"""ReAct write actions respect HITL user permission settings before blocking."""
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
    resolve_user_write_approval_required,
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


def _hitl_client_with_write_policy() -> MagicMock:
    client = MagicMock()

    def table(name: str):
        mock = MagicMock()
        mock.select.return_value = mock
        mock.eq.return_value = mock
        mock.execute.return_value = MagicMock(data=[])
        if name == "hitl_policies":
            mock.execute.return_value = MagicMock(
                data=[
                    {
                        "id": "p-user",
                        "name": "User write",
                        "enabled": True,
                        "scope_type": "user",
                        "subject_user_id": "user-1",
                        "action_kinds": ["write"],
                        "approver_roles": ["admin"],
                        "approver_user_ids": [],
                        "required_approvals": 1,
                    }
                ]
            )
        return mock

    client.table.side_effect = table
    return client


def test_apollo_lists_create_is_write_action():
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


def test_platform_write_tools_are_write_actions():
    from app.services.react_write_gate import PLATFORM_WRITE_TOOLS
    from app.services.tool_registry import get_tool_registry

    registry = get_tool_registry()
    expected = {
        "assistant_create_workflow": "assistant.create_workflow",
        "assistant_execute_workflow": "assistant.execute_workflow",
        "assistant_run_agent_task": "assistant.run_agent_task",
    }
    assert PLATFORM_WRITE_TOOLS == frozenset(expected)
    for tool, action in expected.items():
        requires, invoke, integration, label = tool_requires_user_write_approval(tool, registry)
        assert requires is True, tool
        assert invoke == action
        assert integration == "platform"
        assert label
        assert block_react_write_execution(tool, {"goal": "x", "query": "x", "task": "x"}, registry) is None


def test_platform_write_tools_block_when_hitl_requires_approval():
    from app.services.react_write_gate import PLATFORM_WRITE_TOOLS
    from app.services.tool_registry import get_tool_registry

    registry = get_tool_registry()
    client = _hitl_client_with_write_policy()
    for tool in PLATFORM_WRITE_TOOLS:
        blocked = block_react_write_execution(
            tool,
            {"goal": "x", "query": "x", "task": "x"},
            registry,
            client=client,
            org_id="org-1",
            user_id="user-1",
        )
        assert blocked is not None, tool
        assert blocked["pending_approval"] is True
        assert blocked["error_code"] == WRITE_APPROVAL_REQUIRED


def test_assistant_read_tools_remain_ungated():
    from app.services.tool_registry import get_tool_registry

    registry = get_tool_registry()
    for tool in (
        "assistant_connector_status",
        "assistant_workflow_runs",
        "assistant_analytics",
        "assistant_dependency_impact",
    ):
        requires, *_ = tool_requires_user_write_approval(tool, registry)
        assert requires is False, tool
        assert block_react_write_execution(tool, {}, registry) is None


def test_block_react_write_auto_passes_without_hitl_policy():
    from app.services.tool_registry import get_tool_registry

    registry = get_tool_registry()
    blocked = block_react_write_execution(
        "apollo_lists_create",
        {"name": "MSP Prospects", "modality": "contacts"},
        registry,
    )
    assert blocked is None


def test_block_react_write_blocks_when_hitl_requires_approval():
    from app.services.tool_registry import get_tool_registry

    registry = get_tool_registry()
    blocked = block_react_write_execution(
        "apollo_lists_create",
        {"name": "MSP Prospects", "modality": "contacts"},
        registry,
        client=_hitl_client_with_write_policy(),
        org_id="org-1",
        user_id="user-1",
    )
    assert blocked is not None
    assert blocked["pending_approval"] is True
    assert blocked["success"] is False
    assert blocked["error_code"] == WRITE_APPROVAL_REQUIRED
    assert blocked["args"]["name"] == "MSP Prospects"
    assert "approval_id" not in blocked["args"]


@pytest.mark.asyncio
async def test_react_engine_auto_runs_write_without_hitl_policy(tool_ctx: ToolContext):
    from app.services.tool_registry import get_tool_registry

    registry = get_tool_registry()
    registry.execute_tool = AsyncMock(return_value={"success": True, "result": {"id": "list-1"}})  # type: ignore[method-assign]
    engine = ReActEngine(settings=SimpleNamespace(disable_ai=False), registry=registry)

    result = await engine._execute_tool_call(
        tool_ctx,
        "apollo_lists_create",
        {"name": "MSP Prospects"},
        allowed_tool_names={"apollo_lists_create"},
    )

    assert result["success"] is True
    registry.execute_tool.assert_awaited_once()


@pytest.mark.asyncio
async def test_react_engine_blocks_write_when_hitl_requires_approval(tool_ctx: ToolContext):
    from app.services.tool_registry import get_tool_registry

    tool_ctx = ToolContext(
        settings=SimpleNamespace(disable_connectors=False),
        client=_hitl_client_with_write_policy(),
        org_id="org-1",
        actor_id="user-1",
    )
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
    ), patch(
        "app.services.connector_parameter_inference.infer_missing_parameters",
        side_effect=lambda plan, _ctx: plan,
    ):
        turn = await materialize_react_write_approval_turn(
            settings=SimpleNamespace(),
            org_id="org-1",
            conversation_id="conv-1",
            client=MagicMock(),
            react_result=react,
            message='Create an Apollo contact list named "MSP Prospects".',
        )

    assert turn is not None
    assert turn["dialogue_mode"] == "confirm"
    assert "MSP Prospects" in turn["message"]
    assert turn["stop_pipeline"] is True
    state.update_task_state.assert_awaited_once()
    saved = state.update_task_state.await_args.args[2]
    assert saved["pending_task"]["status"] == "awaiting_confirm"
    assert saved["pending_task"]["params"]["invoke_action"] == "apollo.lists.create"


@pytest.mark.asyncio
async def test_materialize_react_incomplete_gmail_send_awaits_params():
    react = SimpleNamespace(
        tool_calls=[
            {
                "tool": "gmail_messages_send",
                "args": {"to": "stephaniekhan2002@gmail.com"},
                "result": {
                    "success": False,
                    "pending_approval": True,
                    "error_code": WRITE_APPROVAL_REQUIRED,
                    "action": "gmail.messages.send",
                    "integration": "gmail",
                    "label": "Send email",
                    "args": {"to": "stephaniekhan2002@gmail.com"},
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
                "status": "awaiting_params",
                "params": {"invoke_action": "gmail.messages.send"},
            }
        }
    )
    with patch(
        "app.services.conversation_state_service.get_conversation_state_service",
        return_value=state,
    ), patch(
        "app.services.connector_parameter_inference.infer_missing_parameters",
        side_effect=lambda plan, _ctx: plan,
    ):
        turn = await materialize_react_write_approval_turn(
            settings=SimpleNamespace(),
            org_id="org-1",
            conversation_id="conv-1",
            client=MagicMock(),
            react_result=react,
            message="send an email to stephanie",
        )

    assert turn is not None
    assert turn["dialogue_mode"] == "clarify"
    assert "reply yes" not in (turn["message"] or "").lower()
    saved = state.update_task_state.await_args.args[2]
    assert saved["pending_task"]["status"] == "awaiting_params"


@pytest.mark.asyncio
async def test_materialize_platform_create_workflow_pending_type():
    from app.services.react_write_gate import materialize_react_write_approval_turn

    react = SimpleNamespace(
        tool_calls=[
            {
                "tool": "assistant_create_workflow",
                "args": {"goal": "Sync HubSpot to Slack", "name": "HS Slack"},
                "result": {
                    "success": False,
                    "pending_approval": True,
                    "error_code": WRITE_APPROVAL_REQUIRED,
                    "action": "assistant.create_workflow",
                    "integration": "platform",
                    "label": "Create workflow",
                    "args": {"goal": "Sync HubSpot to Slack", "name": "HS Slack"},
                },
            }
        ]
    )
    state = MagicMock()
    state.update_task_state = AsyncMock()
    state.get_task_state = AsyncMock(
        return_value={
            "pending_task": {
                "type": "create_workflow",
                "status": "awaiting_confirm",
                "params": {"workflow_goal": "Sync HubSpot to Slack"},
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
            message="Create a workflow that syncs HubSpot to Slack",
        )

    assert turn is not None
    assert turn["dialogue_mode"] == "confirm"
    assert "Sync HubSpot to Slack" in turn["message"]
    saved = state.update_task_state.await_args.args[2]
    assert saved["pending_task"]["type"] == "create_workflow"
    assert saved["pending_task"]["status"] == "awaiting_confirm"
    assert saved["clarified_params"]["workflow_goal"] == "Sync HubSpot to Slack"
    assert saved["clarified_params"]["invoke_action"] == "assistant.create_workflow"


@pytest.mark.asyncio
async def test_materialize_platform_execute_workflow_uses_distinct_pending_type():
    from app.services.react_write_gate import materialize_react_write_approval_turn

    react = SimpleNamespace(
        tool_calls=[
            {
                "tool": "assistant_execute_workflow",
                "args": {"query": "Lead nurture"},
                "result": {
                    "success": False,
                    "pending_approval": True,
                    "error_code": WRITE_APPROVAL_REQUIRED,
                    "action": "assistant.execute_workflow",
                    "integration": "platform",
                    "label": "Execute workflow",
                    "args": {"query": "Lead nurture"},
                },
            }
        ]
    )
    state = MagicMock()
    state.update_task_state = AsyncMock()
    state.get_task_state = AsyncMock(
        return_value={
            "pending_task": {
                "type": "execute_workflow",
                "status": "awaiting_confirm",
                "params": {"workflow_id": "wf-1", "workflow_name": "Lead nurture"},
            }
        }
    )
    with patch(
        "app.services.conversation_state_service.get_conversation_state_service",
        return_value=state,
    ), patch(
        "app.services.react_write_gate._resolve_workflow_for_approval",
        return_value={
            "id": "wf-1",
            "name": "Lead nurture",
            "goal": "Nurture uncertain leads",
        },
    ):
        turn = await materialize_react_write_approval_turn(
            settings=SimpleNamespace(),
            org_id="org-1",
            conversation_id="conv-1",
            client=MagicMock(),
            react_result=react,
            message="Execute Lead nurture now",
        )

    assert turn is not None
    assert turn["dialogue_mode"] == "confirm"
    assert "execute" in turn["message"].lower()
    assert "Lead nurture" in turn["message"]
    assert "create a draft" not in turn["message"].lower()
    saved = state.update_task_state.await_args.args[2]
    assert saved["pending_task"]["type"] == "execute_workflow"
    assert saved["clarified_params"]["workflow_id"] == "wf-1"
    assert saved["clarified_params"]["invoke_action"] == "assistant.execute_workflow"


@pytest.mark.asyncio
async def test_react_write_chain_gate_then_execute_plan_with_synthetic_agent():
    """Contract: ReAct blocks write when HITL requires approval; approved plan executes via execute_plan.

    Live twin: scripts/smoke-react-write-live.py (daily in connector-verified-writes-live.yml).
    """
    from app.services.tool_registry import get_tool_registry

    tool_ctx = ToolContext(
        settings=SimpleNamespace(disable_connectors=False),
        client=_hitl_client_with_write_policy(),
        org_id="org-1",
        actor_id="user-1",
        agent_id="synthetic-default",
    )
    registry = get_tool_registry()
    registry.execute_tool = AsyncMock()  # type: ignore[method-assign]
    engine = ReActEngine(settings=SimpleNamespace(disable_ai=False), registry=registry)

    blocked = await engine._execute_tool_call(
        tool_ctx,
        "apollo_lists_create",
        {"name": "gravitre-react-gate-probe-ci", "modality": "contacts"},
        allowed_tool_names={"apollo_lists_create"},
    )
    assert blocked["error_code"] == WRITE_APPROVAL_REQUIRED
    registry.execute_tool.assert_not_called()

    react = SimpleNamespace(
        tool_calls=[
            {
                "tool": "apollo_lists_create",
                "args": {"name": "gravitre-react-gate-probe-ci", "modality": "contacts"},
                "result": blocked,
            }
        ]
    )
    pending = pending_write_from_react(react)
    plan = plan_from_react_write(pending, registry)
    assert plan is not None
    assert plan.invoke_action == "apollo.lists.create"
    assert plan.requires_approval is True

    exec_result = SimpleNamespace(
        success=True,
        error_code=None,
        entity_id="30f734a2-dbdb-45aa-9112-19c6d604d451",
        result_url="https://app.apollo.io/#/lists/ci",
        body="Created contact list",
        integration="apollo",
        task_label="Create contact list",
    )
    svc = MagicMock()
    svc.execute_plan = AsyncMock(return_value=exec_result)
    with patch(
        "app.services.chat_connector_execution_service.get_chat_connector_execution_service",
        return_value=svc,
    ):
        from app.services.chat_connector_execution_service import get_chat_connector_execution_service

        result = await get_chat_connector_execution_service(SimpleNamespace()).execute_plan(
            org_id="org-1",
            user_id="user-1",
            conversation_id="conv-1",
            plan=plan,
            client=MagicMock(),
            classification={"intent": "connector_action", "requires_approval": True},
            environment_name="production",
        )

    assert result.success is True
    assert result.error_code is None
    svc.execute_plan.assert_awaited_once()
    assert svc.execute_plan.await_args.kwargs["plan"].invoke_action == "apollo.lists.create"
