"""Tests for governed chat connector execution."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.chat_connector_execution_service import (
    ChatConnectorExecutionService,
    ConnectorActionPlan,
)
from app.services.conversational_execution_service import ExecutionResult


@pytest.fixture
def connector_service():
    service = ChatConnectorExecutionService()
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


def test_is_connector_intent_requires_connector_and_verb(connector_service):
    assert connector_service.is_connector_intent("search hubspot for acme contacts", {}) is True
    assert connector_service.is_connector_intent("hello there", {}) is False
    assert connector_service.is_connector_intent(
        "yes",
        {"pending_task": {"type": "connector_action"}},
    )


def test_plan_slack_send_message(connector_service):
    plan = connector_service.plan_action(
        'Post "Weekly update" to #sales in Slack',
        connected_integrations=["slack"],
        task_state={},
    )
    assert plan is not None
    assert plan.tool_name == "slack_send_message"
    assert plan.invoke_action == "slack.post_message"
    assert plan.args["channel"].lower() == "sales"
    assert "Weekly update" in plan.args["message"]


def test_plan_hubspot_search(connector_service):
    plan = connector_service.plan_action(
        "Search HubSpot for contacts at Acme",
        connected_integrations=["hubspot"],
        task_state={},
    )
    assert plan is not None
    assert plan.tool_name == "hubspot_search_contacts"
    assert plan.kind == "read"
    assert "Acme" in str(plan.args.get("query", ""))


@pytest.mark.asyncio
async def test_write_action_returns_confirm(connector_service):
    with patch.object(
        connector_service,
        "plan_action",
        return_value=ConnectorActionPlan(
            tool_name="slack_send_message",
            invoke_action="slack.post_message",
            integration="slack",
            kind="write",
            label="Post to Slack #sales",
            args={"channel": "sales", "message": "Hello"},
            requires_approval=True,
        ),
    ), patch.object(
        connector_service,
        "_evaluate_risk",
        AsyncMock(return_value={"requires_approval": True, "approval_reason": "Write action"}),
    ):
        result = await connector_service.process_turn(
            org_id="org-1",
            user_id="user-1",
            conversation_id="conv-1",
            message='Post "Hello" to #sales in Slack',
            classification={"intent": "workflow_execution", "risk_level": "medium"},
            task_state={},
            connected_integrations=["slack"],
            client=MagicMock(),
        )

    assert result is not None
    assert result["dialogue_mode"] == "confirm"
    assert result["pending_task"]["type"] == "connector_action"
    assert "yes" in result["message"].lower()


@pytest.mark.asyncio
async def test_read_action_executes_immediately(connector_service):
    mock_execution = ExecutionResult(
        success=True,
        entity_type="connector",
        entity_id="conn-1",
        url="/connectors/conn-1",
        title="Search HubSpot",
        body="Found 3 contacts.",
        task_label="Search HubSpot",
    )
    with patch.object(
        connector_service,
        "plan_action",
        return_value=ConnectorActionPlan(
            tool_name="hubspot_search_contacts",
            invoke_action="hubspot.contacts.search",
            integration="hubspot",
            kind="read",
            label="Search HubSpot for Acme",
            args={"query": "Acme", "limit": 10},
            requires_approval=False,
        ),
    ), patch.object(
        connector_service,
        "_evaluate_risk",
        AsyncMock(return_value={"requires_approval": False, "can_proceed_without_approval": True}),
    ), patch.object(
        connector_service,
        "execute_plan",
        mock_execute := AsyncMock(return_value=mock_execution),
    ):
        result = await connector_service.process_turn(
            org_id="org-1",
            user_id="user-1",
            conversation_id="conv-1",
            message="Search HubSpot for Acme contacts",
            classification={"intent": "crm_lookup", "risk_level": "low"},
            task_state={},
            connected_integrations=["hubspot"],
            client=MagicMock(),
        )

    assert result is not None
    assert result["execution_result"]["success"] is True
    mock_execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_confirmation_executes_write_action(connector_service):
    pending_params = {
        "tool_name": "slack_send_message",
        "invoke_action": "slack.post_message",
        "integration": "slack",
        "kind": "write",
        "label": "Post to Slack #sales",
        "args": {"channel": "sales", "message": "Hello"},
        "requires_approval": True,
    }
    connector_service._state.get_task_state = AsyncMock(
        return_value={
            "pending_task": {
                "type": "connector_action",
                "status": "awaiting_confirm",
                "params": pending_params,
            },
            "clarified_params": pending_params,
        }
    )
    mock_execution = ExecutionResult(
        success=True,
        entity_type="connector",
        entity_id="conn-1",
        url="/connectors/conn-1",
        title="Post to Slack #sales",
        body="Message posted.",
        task_label="Post to Slack #sales",
    )
    with patch.object(
        connector_service,
        "_evaluate_risk",
        AsyncMock(return_value={"requires_approval": True}),
    ), patch.object(
        connector_service,
        "execute_plan",
        mock_execute := AsyncMock(return_value=mock_execution),
    ):
        result = await connector_service.process_turn(
            org_id="org-1",
            user_id="user-1",
            conversation_id="conv-1",
            message="yes",
            classification={"intent": "workflow_execution"},
            task_state={
                "pending_task": {
                    "type": "connector_action",
                    "status": "awaiting_confirm",
                    "params": pending_params,
                },
                "clarified_params": pending_params,
            },
            connected_integrations=["slack"],
            client=MagicMock(),
        )

    assert result is not None
    assert result["execution_result"]["success"] is True
    mock_execute.assert_awaited_once()
