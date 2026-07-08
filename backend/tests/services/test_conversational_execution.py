"""Tests for post-dialogue conversational execution."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.conversational_execution_service import (
    ConversationalExecutionService,
    ExecutionResult,
)


@pytest.fixture
def execution_service():
    service = ConversationalExecutionService()
    service._state = MagicMock()
    service._state.update_task_state = AsyncMock()
    service._state.get_task_state = AsyncMock(
        return_value={
            "clarified_params": {},
            "pending_task": None,
            "completed_steps": [],
        }
    )
    return service


@pytest.mark.asyncio
async def test_extracts_agent_name_and_purpose_from_single_reply(execution_service):
    updates = execution_service.extract_param_updates(
        "Sales Bot for outbound email",
        "create_agent",
        {},
    )
    assert updates["agent_name"] == "Sales Bot"
    assert "email" in updates["agent_purpose"].lower()


@pytest.mark.asyncio
async def test_confirmation_triggers_execute(execution_service):
    execution_service._state.get_task_state = AsyncMock(
        return_value={
            "clarified_params": {
                "agent_name": "Sales Bot",
                "agent_purpose": "outbound email",
            },
            "pending_task": {"type": "create_agent", "status": "awaiting_confirm"},
        }
    )
    mock_result = ExecutionResult(
        success=True,
        entity_type="agent",
        entity_id="agent-1",
        result_url="/agents/agent-1",
        title="Sales Bot",
        body="Created agent",
        notification_type="agent_created",
        task_label="Created agent Sales Bot",
    )

    with patch.object(execution_service, "execute_task", AsyncMock(return_value=mock_result)):
        result = await execution_service.process_turn(
            org_id="org-1",
            user_id="user-1",
            conversation_id="conv-1",
            message="yes",
            understanding={"conversational_create": True},
            classification={"intent": "workflow_planning"},
            task_state={
                "clarified_params": {
                    "agent_name": "Sales Bot",
                    "agent_purpose": "outbound email",
                },
                "pending_task": {"type": "create_agent", "status": "awaiting_confirm"},
            },
            client=MagicMock(),
        )

    assert result is not None
    assert result["stop_pipeline"] is True
    assert result["execution_result"]["entity_id"] == "agent-1"


@pytest.mark.asyncio
async def test_ready_params_return_confirm_without_execute(execution_service):
    result = await execution_service.process_turn(
        org_id="org-1",
        user_id="user-1",
        conversation_id="conv-1",
        message="Sales Bot for support triage",
        understanding={"conversational_create": True},
        classification={"intent": "workflow_planning"},
        task_state={"clarified_params": {}},
        client=MagicMock(),
    )
    assert result is not None
    assert result["dialogue_mode"] == "confirm"
    assert "yes" in result["message"].lower()
