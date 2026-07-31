"""Wave 1 — structured ReAct tool_calls skip NL chat_action_mapper."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.chat_connector_models import ConnectorActionPlan
from app.services.react_write_gate import (
    first_structured_connector_plan_from_react,
    plan_from_react_tool_call,
)


def test_plan_from_react_tool_call_preserves_apollo_args():
    from app.services.tool_registry import get_tool_registry

    plan = plan_from_react_tool_call(
        "apollo_lists_create",
        {"name": "MSP Prospects", "modality": "contacts"},
        get_tool_registry(),
    )
    assert plan is not None
    assert plan.invoke_action == "apollo.lists.create"
    assert plan.integration == "apollo"
    assert plan.args["name"] == "MSP Prospects"
    assert plan.requires_approval is False
    assert plan.approval_reason is None


def test_first_structured_plan_from_failed_react_call():
    from app.services.tool_registry import get_tool_registry

    react = SimpleNamespace(
        tool_calls=[
            {
                "tool": "apollo_lists_create",
                "args": {"name": "MSP Prospects", "modality": "contacts"},
                "result": {"success": False, "error": "permission crash"},
            }
        ]
    )
    plan = first_structured_connector_plan_from_react(react, get_tool_registry())
    assert plan is not None
    assert plan.invoke_action == "apollo.lists.create"
    assert plan.args["name"] == "MSP Prospects"


@pytest.mark.asyncio
async def test_fallback_uses_structured_plan_not_nl_mapper():
    from app.services.connector_chat_routing import run_connector_fallback_turn

    structured = ConnectorActionPlan(
        tool_name="apollo_lists_create",
        invoke_action="apollo.lists.create",
        integration="apollo",
        kind="write",
        label="Create Apollo contact list",
        args={"name": "MSP Prospects", "modality": "contacts"},
        requires_approval=True,
    )
    react = SimpleNamespace(
        tool_calls=[
            {
                "tool": "apollo_lists_create",
                "args": {"name": "MSP Prospects", "modality": "contacts"},
                "result": {"success": False},
            }
        ]
    )
    process_turn = AsyncMock(
        return_value={
            "stop_pipeline": True,
            "dialogue_mode": "confirm",
            "message": "approve?",
        }
    )
    connector = MagicMock(process_turn=process_turn)
    with patch(
        "app.services.chat_orchestration_service.ChatOrchestrationService.is_orchestration_intent",
        return_value=False,
    ), patch(
        "app.services.chat_orchestration_service.get_chat_orchestration_service",
        return_value=MagicMock(),
    ), patch(
        "app.services.chat_connector_execution_service.get_chat_connector_execution_service",
        return_value=connector,
    ), patch(
        "app.services.react_write_gate.first_structured_connector_plan_from_react",
        return_value=structured,
    ):
        turn = await run_connector_fallback_turn(
            settings=MagicMock(),
            org_id="org-1",
            user_id="user-1",
            conversation_id="conv-1",
            message="can you create a segment in Apollo for MSPs?",
            classification={},
            task_state={},
            connected_integrations=["apollo"],
            client=MagicMock(),
            react_result=react,
        )

    assert turn is not None
    assert process_turn.await_count == 1
    assert process_turn.await_args.kwargs["structured_plan"] is structured


def test_plan_action_prefers_structured_over_mapper():
    from app.services.chat_connector_execution_service import ChatConnectorExecutionService

    service = ChatConnectorExecutionService(settings=MagicMock())
    structured = ConnectorActionPlan(
        tool_name="apollo_lists_create",
        invoke_action="apollo.lists.create",
        integration="apollo",
        kind="write",
        label="Create list",
        args={"name": "From ReAct"},
        requires_approval=True,
    )
    with patch(
        "app.services.chat_connector_execution_service.get_chat_action_mapper"
    ) as mapper:
        plan = service.plan_action(
            "create a segment in Apollo for MSPs",
            connected_integrations=["apollo"],
            task_state={},
            structured_plan=structured,
        )
        mapper.assert_not_called()
    assert plan is structured
    assert plan.args["name"] == "From ReAct"
