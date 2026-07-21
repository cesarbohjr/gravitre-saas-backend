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
    ), patch.object(
        connector_service,
        "_verify_plan_executable",
        return_value=None,
    ), patch.object(
        connector_service,
        "_user_can_approve_writes",
        return_value=True,
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
    assert "approve" in result["message"].lower()
    assert result["pending_task"]["type"] == "connector_action"


@pytest.mark.asyncio
async def test_write_action_queues_for_non_approver(connector_service):
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
    ), patch.object(
        connector_service,
        "_verify_plan_executable",
        return_value=None,
    ), patch.object(
        connector_service,
        "_user_can_approve_writes",
        return_value=False,
    ), patch.object(
        connector_service,
        "_queue_chat_write_for_admins",
        return_value="approval-row-1",
    ) as mock_queue:
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
    assert result["dialogue_mode"] == "awaiting_approval"
    assert "sent for approval" in result["message"].lower()
    assert result["pending_task"]["status"] == "awaiting_admin_approval"
    assert result["pending_task"]["params"]["approval_id"] == "approval-row-1"
    mock_queue.assert_called_once()


def test_plan_slack_followup_uses_staged_channel(connector_service):
    plan = connector_service.plan_action(
        "Sure, say hi everyone at Gravitre",
        connected_integrations=["slack"],
        task_state={
            "clarified_params": {"slack_channel": "general", "intent": "slack_send"},
            "pending_task": {
                "type": "connector_action",
                "status": "awaiting_params",
                "params": {
                    "tool_name": "slack_send_message",
                    "invoke_action": "slack.post_message",
                    "integration": "slack",
                    "kind": "write",
                    "channel": "general",
                    "args": {"channel": "general"},
                },
            },
        },
    )
    assert plan is not None
    assert plan.args["channel"].lower() == "general"
    assert "hi everyone" in plan.args["message"].lower()


@pytest.mark.asyncio
async def test_read_action_executes_immediately(connector_service):
    mock_execution = ExecutionResult(
        success=True,
        entity_type="connector",
        entity_id="conn-1",
        connector_management_url="/connectors/conn-1",
        integration="hubspot",
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
        "_verify_plan_executable",
        return_value=None,
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
        connector_management_url="/connectors/conn-1",
        integration="slack",
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
        "_verify_plan_executable",
        return_value=None,
    ), patch.object(
        connector_service,
        "execute_plan",
        mock_execute := AsyncMock(return_value=mock_execution),
    ), patch.object(
        connector_service,
        "_user_can_approve_writes",
        return_value=True,
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


@pytest.mark.asyncio
async def test_asana_not_connected_returns_operator_blocker(connector_service):
    with patch.object(
        connector_service,
        "_live_connected_integrations",
        return_value=["apollo"],
    ), patch(
        "app.services.chat_connector_execution_service.find_integration_availability",
        return_value=None,
    ), patch.object(
        connector_service,
        "plan_action",
        return_value=None,
    ):
        result = await connector_service.process_turn(
            org_id="org-1",
            user_id="user-1",
            conversation_id="conv-1",
            message="Create a task in Asana for Sarah to review the landing page by Friday",
            classification={"intent": "workflow_execution", "risk_level": "medium"},
            task_state={},
            connected_integrations=["apollo"],
            client=MagicMock(),
        )

    assert result is not None
    assert result["stop_pipeline"] is True
    assert "isn't ready" in result["message"] or "can't run" in result["message"].lower()
    assert "Asana" in result["message"]
    assert "Connect Asana" in result["message"] or "Missing connector" in result["message"]


@pytest.mark.asyncio
async def test_apollo_list_create_plans_action(connector_service):
    plan = ConnectorActionPlan(
        tool_name="apollo_lists_create",
        invoke_action="apollo.lists.create",
        integration="apollo",
        kind="write",
        label="Create Apollo contact list",
        args={"name": "MSP Prospects", "modality": "contacts"},
        requires_approval=True,
    )
    with patch.object(
        connector_service,
        "_live_connected_integrations",
        return_value=["apollo"],
    ), patch.object(
        connector_service,
        "plan_action",
        return_value=plan,
    ), patch.object(
        connector_service,
        "_verify_plan_executable",
        return_value=None,
    ), patch.object(
        connector_service,
        "_evaluate_risk",
        AsyncMock(return_value={"requires_approval": True}),
    ), patch.object(
        connector_service,
        "_user_can_approve_writes",
        return_value=True,
    ), patch(
        "app.services.connector_action_workflows.resolve_assignee_disambiguation",
        AsyncMock(return_value=None),
    ):
        result = await connector_service.process_turn(
            org_id="org-1",
            user_id="user-1",
            conversation_id="conv-1",
            message="Create a contact list in Apollo for MSP prospects",
            classification={"intent": "workflow_execution", "risk_level": "medium"},
            task_state={},
            connected_integrations=["apollo"],
            client=MagicMock(),
        )

    assert result is not None
    assert result["dialogue_mode"] == "confirm"
    assert "MSP Prospects" in result["message"] or "Approve" in result["message"]


@pytest.mark.asyncio
async def test_list_create_ignores_react_structured_read_plan(connector_service):
    """ReAct lists.list must not shadow Apollo list-create write staging."""
    read_plan = ConnectorActionPlan(
        tool_name="apollo_lists_list",
        invoke_action="apollo.lists.list",
        integration="apollo",
        kind="read",
        label="List contact lists",
        args={"limit": 10},
        requires_approval=False,
    )
    write_plan = ConnectorActionPlan(
        tool_name="apollo_lists_create",
        invoke_action="apollo.lists.create",
        integration="apollo",
        kind="write",
        label="Create contact list",
        args={"name": "gravitre-planforce", "modality": "contacts"},
        requires_approval=True,
    )

    def _plan_action(message, *, connected_integrations, task_state, structured_plan=None):
        if structured_plan is not None:
            return structured_plan
        return write_plan

    with patch.object(
        connector_service,
        "_live_connected_integrations",
        return_value=["apollo"],
    ), patch.object(
        connector_service,
        "plan_action",
        side_effect=_plan_action,
    ), patch(
        "app.services.chat_connector_execution_service.find_integration_availability",
        return_value={"execution_available": True},
    ), patch.object(
        connector_service,
        "_build_unresolved_turn",
        return_value={
            "stop_pipeline": True,
            "dialogue_mode": "confirm",
            "message": "Approve create list",
            "task_state": {
                "pending_task": {
                    "type": "connector_action",
                    "status": "awaiting_confirm",
                    "params": {
                        **connector_service.plan_to_dict(write_plan),
                        "status": "awaiting_confirm",
                        "source": "apollo_list_create_autoplan",
                    },
                }
            },
            "pending_task": {
                "type": "connector_action",
                "status": "awaiting_confirm",
                "params": {
                    **connector_service.plan_to_dict(write_plan),
                    "status": "awaiting_confirm",
                    "source": "apollo_list_create_autoplan",
                },
            },
            "persist_pending_task": False,
        },
    ) as build_unresolved:
        result = await connector_service.process_turn(
            org_id="org-1",
            user_id="user-1",
            conversation_id="conv-1",
            message=(
                "Create an Apollo contact list named exactly 'gravitre-planforce'. "
                "Please plan the steps before executing."
            ),
            classification={"intent": "workflow_execution", "risk_level": "medium"},
            task_state={},
            connected_integrations=["apollo"],
            client=MagicMock(),
            structured_plan=read_plan,
        )

    assert build_unresolved.called, "structured read plan must be cleared so autoplan runs"
    assert result is not None
    assert result.get("stop_pipeline") is True
    pending = result.get("pending_task") or {}
    assert pending.get("status") == "awaiting_confirm"
    assert "lists.create" in str((pending.get("params") or {}).get("invoke_action") or "")


@pytest.mark.asyncio
async def test_hubspot_token_expired_returns_reconnect_message(connector_service):
    with patch(
        "app.services.chat_connector_execution_service.find_integration_availability",
        return_value={
            "execution_available": False,
            "blocking_reason": "token_expired",
            "recovery_action": "HubSpot is configured, but authentication has expired. Reconnect HubSpot.",
        },
    ), patch.object(
        connector_service,
        "plan_action",
        return_value=None,
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
    assert "authentication has expired" in result["message"].lower()
    assert result["stop_pipeline"] is True


@pytest.mark.asyncio
async def test_hubspot_missing_scope_returns_precise_message(connector_service):
    with patch.object(
        connector_service,
        "plan_action",
        return_value=ConnectorActionPlan(
            tool_name="hubspot_search_contacts",
            invoke_action="hubspot.contacts.search",
            integration="hubspot",
            kind="read",
            label="Search HubSpot contacts",
            args={"query": "Acme", "limit": 10},
            requires_approval=False,
        ),
    ), patch.object(
        connector_service,
        "_verify_plan_executable",
        return_value=(
            "HubSpot is connected, but hubspot contacts search is not executable because "
            "required OAuth scopes are missing."
        ),
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
    assert "scopes are missing" in result["message"].lower()
    assert result["stop_pipeline"] is True


@pytest.mark.asyncio
async def test_hubspot_unsupported_action_returns_precise_message(connector_service):
    with patch.object(
        connector_service,
        "plan_action",
        return_value=ConnectorActionPlan(
            tool_name="hubspot_search_contacts",
            invoke_action="hubspot.contacts.search",
            integration="hubspot",
            kind="read",
            label="Search HubSpot contacts",
            args={"query": "Acme", "limit": 10},
            requires_approval=False,
        ),
    ), patch.object(
        connector_service,
        "_verify_plan_executable",
        return_value=(
            "HubSpot is connected, but hubspot contacts search is not executable because "
            "the action is not supported yet."
        ),
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
    assert "not executable" in result["message"].lower()
    assert result["stop_pipeline"] is True


def test_summarize_apollo_list_create_includes_name_and_id(connector_service):
    plan = ConnectorActionPlan(
        tool_name="apollo_lists_create",
        invoke_action="apollo.lists.create",
        integration="apollo",
        kind="write",
        label="Create Apollo contact list",
        args={"name": "MSP Prospects", "modality": "contacts"},
        requires_approval=True,
    )
    summary = connector_service._summarize_result(
        plan,
        {"label": {"id": "list-123", "name": "MSP Prospects"}},
        {"success": True},
    )
    assert 'MSP Prospects' in summary
    assert "list-123" in summary


@pytest.mark.asyncio
async def test_execute_plan_apollo_list_create_sets_apollo_result_url(connector_service):
    plan = ConnectorActionPlan(
        tool_name="apollo_lists_create",
        invoke_action="apollo.lists.create",
        integration="apollo",
        kind="write",
        label="Create Apollo contact list",
        args={"name": "MSP Prospects", "modality": "contacts"},
        requires_approval=True,
    )
    with patch.object(
        connector_service,
        "_registry",
        MagicMock(
            execute_tool=AsyncMock(
                return_value={
                    "success": True,
                    "connector_id": "conn-apollo",
                    "result": {"label": {"id": "list-123", "name": "MSP Prospects"}},
                }
            )
        ),
    ), patch.object(connector_service, "_record_outcomes", AsyncMock()), patch(
        "app.workflows.repository.create_run",
        return_value={"id": "run-test-1"},
    ), patch(
        "app.services.notification_emitter.emit_notification"
    ) as notify:
        result = await connector_service.execute_plan(
            org_id="org-1",
            user_id="user-1",
            conversation_id="conv-1",
            plan=plan,
            client=MagicMock(),
            classification={},
        )

    assert result.success is True
    assert result.result_url == "/ai?conversation=conv-1"
    assert result.external_url == "https://app.apollo.io/#/lists/list-123"
    assert result.connector_management_url == "/connectors/conn-apollo"
    assert result.integration == "apollo"
    assert "MSP Prospects" in result.body
    assert "list-123" in result.body
    notify.assert_called_once()
    assert notify.call_args.kwargs["entity_ref"]["result_url"] == result.result_url


@pytest.mark.asyncio
async def test_execute_plan_write_without_body_or_url_fails_verifiability_gate(connector_service):
    plan = ConnectorActionPlan(
        tool_name="apollo_lists_create",
        invoke_action="apollo.lists.create",
        integration="apollo",
        kind="write",
        label="Create Apollo contact list",
        args={"name": "Empty"},
        requires_approval=True,
    )
    with patch.object(
        connector_service,
        "_registry",
        MagicMock(
            execute_tool=AsyncMock(
                return_value={
                    "success": True,
                    "connector_id": "conn-apollo",
                    "result": {},
                }
            )
        ),
    ), patch.object(
        connector_service,
        "_summarize_result",
        return_value="",
    ), patch.object(connector_service, "_record_outcomes", AsyncMock()), patch(
        "app.services.chat_connector_execution_service.emit_notification"
    ) as notify:
        result = await connector_service.execute_plan(
            org_id="org-1",
            user_id="user-1",
            conversation_id="conv-1",
            plan=plan,
            client=MagicMock(),
            classification={},
        )

    assert result.success is False
    assert "verifiable" in result.body.lower() or "missing body" in result.body.lower()
    notify.assert_not_called()
