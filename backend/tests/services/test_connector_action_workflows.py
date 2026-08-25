"""Workflow pattern tests for connector action governance."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.chat_connector_execution_service import (
    ChatConnectorExecutionService,
    ConnectorActionPlan,
)
from app.services.chat_orchestration_service import ChatOrchestrationService
from app.services.connector_action_workflows import (
    analyze_list_capability_gaps,
    format_capability_fallback_message,
    format_write_approval_message,
    missing_params_stage_patch,
    scrub_gmail_write_plan,
    validate_connector_plan,
)
from app.services.parameter_ledger import email_slot_looks_corrupted
from app.services.connector_chat_routing import should_run_connector_preflight


def test_preflight_defers_fresh_connector_intent_to_react():
    assert (
        should_run_connector_preflight(
            {},
            message="Create a task in Asana for Sarah to review the landing page by Friday",
        )
        is False
    )
    assert (
        should_run_connector_preflight(
            {"pending_task": {"type": "connector_action"}},
            message="yes",
        )
        is True
    )


def test_multi_step_intent_reaches_orchestration_planner():
    message = "Search Apollo for MSP companies in Canada and create HubSpot contacts"
    connected = ["apollo", "hubspot"]
    assert ChatOrchestrationService.is_orchestration_intent(message, {}, connected) is True


def test_missing_parameters_returns_clarification_not_failure():
    plan = ConnectorActionPlan(
        tool_name="asana_tasks_create",
        invoke_action="asana.tasks.create",
        integration="asana",
        kind="write",
        label="Create Asana task",
        args={"assignee_hint": "Sarah"},
    )
    check = validate_connector_plan(plan, "Create an Asana task for Sarah")
    assert check is not None
    assert check.status == "needs clarification"
    assert "project" in check.missing
    assert "due date" in check.missing
    assert "task title" in check.missing
    assert check.known.get("Assignee") == "Sarah"
    assert "few more details" in check.message.lower()


def test_write_action_approval_message_format():
    plan = ConnectorActionPlan(
        tool_name="asana_tasks_create",
        invoke_action="asana.tasks.create",
        integration="asana",
        kind="write",
        label="Create Asana task",
        args={
            "name": "Review the landing page",
            "assignee_hint": "Sarah",
            "project": "Website",
            "due_on": "2026-07-10",
        },
    )
    message = format_write_approval_message(plan)
    assert "I'll run this in Asana" in message or "Asana" in message
    assert "yes" in message.lower()
    assert "Sarah" in message
    assert "Website" in message


def test_scrub_gmail_repairs_incident_subject_line_hello_and():
    """Replay of 2026-07-27 corrupted send — scrub must neutralize framing residue."""
    assert email_slot_looks_corrupted("subject", "line, hello and")
    assert email_slot_looks_corrupted("body", "of the email say: I'm just testing this")

    dirty = ConnectorActionPlan(
        tool_name="gmail_messages_send",
        invoke_action="gmail.messages.send",
        integration="gmail",
        kind="write",
        label="Send email",
        args={
            "to": "stephaniekhan2002@gmail.com",
            "subject": "line, hello and",
            "body": "of the email say: I'm just testing this",
        },
    )
    cleaned = scrub_gmail_write_plan(dirty)
    assert (cleaned.args or {}).get("to") == "stephaniekhan2002@gmail.com"
    assert (cleaned.args or {}).get("subject") == "hello"
    assert (cleaned.args or {}).get("body") == "I'm just testing this"
    assert not email_slot_looks_corrupted("subject", cleaned.args["subject"])
    assert not email_slot_looks_corrupted("body", cleaned.args["body"])
    # After repair, required fields are present — execute gate must not re-ask.
    assert missing_params_stage_patch(cleaned, "") is None

    # Approval copy must not re-surface the corrupt fragments.
    approval = format_write_approval_message(dirty)
    assert "line, hello and" not in approval
    assert "of the email say" not in approval
    assert "hello" in approval
    assert "just testing this" in approval.lower()

    # Unrepairable residue still blocks (forces awaiting_params, not send).
    unrepairable = ConnectorActionPlan(
        tool_name="gmail_messages_send",
        invoke_action="gmail.messages.send",
        integration="gmail",
        kind="write",
        label="Send email",
        args={
            "to": "stephaniekhan2002@gmail.com",
            "subject": "line",
            "body": "of the email say",
        },
    )
    stripped = scrub_gmail_write_plan(unrepairable)
    assert "subject" not in (stripped.args or {}) or not str(
        (stripped.args or {}).get("subject") or ""
    ).strip()
    assert "body" not in (stripped.args or {}) or not str(
        (stripped.args or {}).get("body") or ""
    ).strip()
    blocked = missing_params_stage_patch(stripped, "")
    assert blocked is not None


def test_apollo_list_approval_message_is_conversational():
    plan = ConnectorActionPlan(
        tool_name="apollo_lists_create",
        invoke_action="apollo.lists.create",
        integration="apollo",
        kind="write",
        label="Create contact list",
        args={"name": "MSP Prospects", "modality": "contacts"},
    )
    message = format_write_approval_message(plan)
    assert "MSP Prospects" in message
    assert "Apollo" in message
    assert "**Planned action:**" not in message
    assert "yes" in message.lower()


def test_write_approval_message_prepends_grace_prefix():
    plan = ConnectorActionPlan(
        tool_name="capability__crm__contact__create",
        invoke_action="hubspot.contacts.create",
        integration="hubspot",
        kind="write",
        label="Create HubSpot contact",
        args={"email": "test@example.com"},
    )
    grace = "I'll create that in your HubSpot (Create HubSpot contact)."
    message = format_write_approval_message(plan, grace_prefix=grace)
    assert message.startswith(grace)
    assert "capability__" not in message.lower()


def test_capability_fallback_for_apollo_list_when_create_unavailable():
    available = [
        "people.search — Search people",
        "organizations.search — Search companies",
        "contacts.create — Create contact",
        "sequences.add — Add to sequence",
    ]
    gaps = analyze_list_capability_gaps("apollo", available)
    assert gaps["create_list"] is False
    assert gaps["search_people"] is True
    assert gaps["add_to_list"] is True

    message = format_capability_fallback_message(
        integration="apollo",
        intent="Create contact list (MSP prospects)",
        missing_action="apollo.lists.create",
        available_actions=available,
    )
    assert "cannot create Apollo lists yet" in message
    assert "Can create list? no" in message
    assert "apollo.lists.create" not in message


def test_capability_gaps_when_apollo_list_create_available():
    available = [
        "people.search — Search people",
        "lists.create — Create contact list",
    ]
    gaps = analyze_list_capability_gaps("apollo", available)
    assert gaps["create_list"] is True


@pytest.mark.asyncio
async def test_disconnected_connector_returns_connect_blocker():
    service = ChatConnectorExecutionService()
    service._state = MagicMock()
    service._state.update_task_state = AsyncMock()
    service._state.get_task_state = AsyncMock(return_value={"pending_task": None})

    with patch.object(service, "_live_connected_integrations", return_value=["apollo"]), patch(
        "app.services.chat_connector_execution_service.find_integration_availability",
        return_value=None,
    ), patch.object(service, "plan_action", return_value=None):
        result = await service.process_turn(
            org_id="org-1",
            user_id="user-1",
            conversation_id="conv-1",
            message="Create an Asana task for Sarah",
            classification={"intent": "workflow_execution"},
            task_state={},
            connected_integrations=["apollo"],
            client=MagicMock(),
        )

    assert result is not None
    assert result["stop_pipeline"] is True
    assert "Missing connector" in result["message"] or "Connect Asana" in result["message"]


@pytest.mark.asyncio
async def test_missing_parameters_turn_returns_clarification():
    service = ChatConnectorExecutionService()
    service._state = MagicMock()
    service._state.update_task_state = AsyncMock()
    service._state.get_task_state = AsyncMock(return_value={"pending_task": None})

    plan = ConnectorActionPlan(
        tool_name="asana_tasks_create",
        invoke_action="asana.tasks.create",
        integration="asana",
        kind="write",
        label="Create Asana task",
        args={"assignee_hint": "Sarah"},
        requires_approval=True,
    )

    with patch.object(service, "_live_connected_integrations", return_value=["asana"]), patch.object(
        service,
        "plan_action",
        return_value=plan,
    ), patch.object(service, "_verify_plan_executable", return_value=None), patch.object(
        service,
        "_evaluate_risk",
        AsyncMock(return_value={"requires_approval": True}),
    ):
        result = await service.process_turn(
            org_id="org-1",
            user_id="user-1",
            conversation_id="conv-1",
            message="Create an Asana task for Sarah",
            classification={"intent": "workflow_execution"},
            task_state={},
            connected_integrations=["asana"],
            client=MagicMock(),
        )

    assert result is not None
    assert result["dialogue_mode"] == "clarify"
    assert result["workflow_status"] == "needs clarification"
    assert "project" in result["message"].lower()


@pytest.mark.asyncio
async def test_ambiguous_assignee_returns_disambiguation():
    service = ChatConnectorExecutionService()
    service._state = MagicMock()
    service._state.update_task_state = AsyncMock()
    service._state.get_task_state = AsyncMock(return_value={"pending_task": None})

    plan = ConnectorActionPlan(
        tool_name="asana_tasks_create",
        invoke_action="asana.tasks.create",
        integration="asana",
        kind="write",
        label="Create Asana task",
        args={
            "name": "Review the landing page",
            "assignee_hint": "Sarah",
            "project": "Website",
            "due_on": "2026-07-10",
        },
        requires_approval=True,
    )

    with patch.object(service, "_live_connected_integrations", return_value=["asana"]), patch.object(
        service,
        "plan_action",
        return_value=plan,
    ), patch.object(service, "_verify_plan_executable", return_value=None), patch(
        "app.services.asana_tools.fetch_asana_users_for_disambiguation",
        return_value=[
            {"gid": "1", "name": "Sarah Lee"},
            {"gid": "2", "name": "Sarah Chen"},
        ],
    ):
        result = await service.process_turn(
            org_id="org-1",
            user_id="user-1",
            conversation_id="conv-1",
            message="Create a task in Asana for Sarah to review the landing page by Friday in Website project",
            classification={"intent": "workflow_execution"},
            task_state={},
            connected_integrations=["asana"],
            client=MagicMock(),
        )

    assert result is not None
    assert result["dialogue_mode"] == "clarify"
    assert result["workflow_status"] == "needs disambiguation"
    assert "Sarah Lee" in result["message"]
    assert "Sarah Chen" in result["message"]


@pytest.mark.asyncio
async def test_write_action_requires_approval_before_execute():
    service = ChatConnectorExecutionService()
    service._state = MagicMock()
    service._state.update_task_state = AsyncMock()
    service._state.get_task_state = AsyncMock(return_value={"pending_task": None})

    plan = ConnectorActionPlan(
        tool_name="asana_tasks_create",
        invoke_action="asana.tasks.create",
        integration="asana",
        kind="write",
        label="Create Asana task",
        args={
            "name": "Review the landing page",
            "assignee_hint": "Sarah",
            "project": "Website",
            "due_on": "2026-07-10",
        },
        requires_approval=True,
    )

    with patch.object(service, "_live_connected_integrations", return_value=["asana"]), patch.object(
        service,
        "plan_action",
        return_value=plan,
    ), patch.object(service, "_verify_plan_executable", return_value=None), patch.object(
        service,
        "_evaluate_risk",
        AsyncMock(return_value={"requires_approval": True}),
    ), patch(
        "app.services.connector_action_workflows.resolve_assignee_disambiguation",
        AsyncMock(return_value=None),
    ), patch.object(
        service,
        "_user_can_approve_writes",
        return_value=True,
    ), patch.object(service, "execute_plan", AsyncMock()) as mock_execute:
        result = await service.process_turn(
            org_id="org-1",
            user_id="user-1",
            conversation_id="conv-1",
            message="Create a task in Asana for Sarah to review the landing page by Friday in Website project",
            classification={"intent": "workflow_execution"},
            task_state={},
            connected_integrations=["asana"],
            client=MagicMock(),
        )

    assert result is not None
    assert result["dialogue_mode"] == "confirm"
    assert "approve" in result["message"].lower()
    mock_execute.assert_not_called()


@pytest.mark.asyncio
async def test_multi_step_orchestration_runs_in_preflight():
    service = ChatOrchestrationService()
    service._state = MagicMock()
    service._state.update_task_state = AsyncMock()
    service._state.get_task_state = AsyncMock(
        return_value={
            "pending_task": {"type": "connector_orchestration", "status": "awaiting_plan_confirm"},
            "clarified_params": {"steps": [{"step_id": "1"}, {"step_id": "2"}]},
        }
    )

    with patch.object(
        service,
        "_build_plan",
        AsyncMock(
            return_value=[
                MagicMock(
                    step_id="1",
                    label="Search Apollo companies",
                    kind="read",
                    supported=True,
                    requires_approval=False,
                    to_dict=lambda: {"step_id": "1"},
                ),
                MagicMock(
                    step_id="2",
                    label="Create HubSpot contacts",
                    kind="write",
                    supported=True,
                    requires_approval=True,
                    to_dict=lambda: {"step_id": "2"},
                ),
            ]
        ),
    ), patch.object(service, "_present_plan_confirm", AsyncMock(return_value={"stop_pipeline": True, "dialogue_mode": "confirm", "message": "orchestration plan"})):
        result = await service.process_turn(
            org_id="org-1",
            user_id="user-1",
            conversation_id="conv-1",
            message="Search Apollo for MSP companies and create HubSpot contacts",
            classification={"intent": "workflow_execution"},
            task_state={},
            connected_integrations=["apollo", "hubspot"],
            client=MagicMock(),
        )

    assert result is not None
    assert result.get("stop_pipeline") is True
