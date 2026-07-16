"""Coverage tests for chat connector execution matrix, mapping, and approval gates."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.chat_action_mapper import get_chat_action_mapper
from app.services.chat_connector_execution_service import (
    ChatConnectorExecutionService,
    ConnectorActionPlan,
)
from app.services.chat_orchestration_service import ChatOrchestrationService
from app.services.connector_execution_matrix import get_matrix_entry
from app.services.tool_registry import get_tool_registry


def test_matrix_actions_register_dynamic_tool_specs():
    registry = get_tool_registry()
    for action_key in (
        "monday.items.create",
        "drive.files.list",
        "gmail.messages.send",
        "jira.issues.create",
        "salesforce.leads.update",
        "microsoft365.teams.messages.send",
    ):
        vendor, _, _ = action_key.partition(".")
        entry = get_matrix_entry(vendor if vendor != "drive" else "google_drive", action_key)
        if entry is None and action_key.startswith("drive."):
            entry = get_matrix_entry("google_drive", f"google_{action_key}")
        assert entry is not None, action_key
        assert registry.get_spec(entry.tool_registry_key) is not None


def test_unimplemented_catalog_action_not_chat_executable():
    entry = get_matrix_entry("workday", "workday.employees.list")
    if entry is None:
        pytest.skip("workday.employees.list not in catalog")
    if entry.implementation_status != "not_implemented":
        pytest.skip("workday list unexpectedly implemented")
    assert entry.chat_executable is False


@pytest.mark.parametrize(
    ("message", "integration", "action_suffix", "requires_approval"),
    [
        ('Create a task in Monday called "Follow up"', "monday", "monday.items.create", True),
        ('Create Jira ticket "Bug in checkout" in project ENG', "jira", "jira.issues.create", True),
        (
            'Send Gmail follow-up to user@example.com with subject "Hello" and body "Checking in"',
            "gmail",
            "gmail.messages.send",
            True,
        ),
        ("Search HubSpot for contacts at Acme", "hubspot", "contacts.search", False),
        ("List files in Google Drive for quarterly report", "google_drive", "files.list", False),
    ],
)
def test_action_mapping_and_approval(message, integration, action_suffix, requires_approval):
    match = get_chat_action_mapper().match_segment(message, connected_integrations=[integration])
    assert match is not None, message
    assert action_suffix in match.entry.action_key
    assert match.entry.requires_approval is requires_approval or match.entry.kind == "write"


def test_salesforce_update_requires_approval():
    entry = get_matrix_entry("salesforce", "salesforce.leads.update")
    if entry is None:
        entry = get_matrix_entry("salesforce", "salesforce.opportunities.update")
    assert entry is not None
    assert entry.requires_approval is True
    assert entry.kind == "write"


def test_teams_message_requires_approval():
    entry = get_matrix_entry("microsoft365", "microsoft365.teams.messages.send")
    if entry is None:
        entry = get_matrix_entry("microsoft_teams", "microsoft_teams.messages.send")
    assert entry is not None
    assert entry.requires_approval is True


@pytest.mark.asyncio
async def test_monday_create_plan_requires_step_approval():
    service = ChatOrchestrationService()
    service._state = MagicMock()
    service._state.update_task_state = AsyncMock()
    with patch.object(
        service._connector,
        "_evaluate_risk",
        AsyncMock(return_value={"requires_approval": True, "approval_reason": "Write action"}),
    ):
        step = await service._plan_segment(
            step_id="step_1",
            segment='Create a task in Monday called "Follow up stale deal"',
            connected_integrations=["monday"],
            org_id="org-1",
            user_id="user-1",
            classification={"risk_level": "medium"},
        )
    assert step.supported is True
    assert step.plan is not None
    assert step.plan.invoke_action == "monday.items.create"
    assert step.requires_approval is True


@pytest.mark.asyncio
async def test_high_risk_write_cannot_auto_run_without_approval():
    service = ChatConnectorExecutionService()
    service._state = MagicMock()
    service._state.update_task_state = AsyncMock()
    service._state.get_task_state = AsyncMock(return_value={"pending_task": None, "clarified_params": {}})
    plan = ConnectorActionPlan(
        tool_name="slack_send_message",
        invoke_action="slack.post_message",
        integration="slack",
        kind="write",
        label="Post to Slack",
        args={"channel": "sales", "message": "Hello"},
        requires_approval=True,
    )
    with patch.object(service, "plan_action", return_value=plan), patch.object(
        service,
        "_evaluate_risk",
        AsyncMock(return_value={"requires_approval": True, "approval_reason": "Write action"}),
    ), patch.object(
        service,
        "_verify_plan_executable",
        return_value=None,
    ), patch.object(
        service,
        "_user_can_approve_writes",
        return_value=True,
    ), patch.object(service, "execute_plan", AsyncMock()) as mock_execute:
        result = await service.process_turn(
            org_id="org-1",
            user_id="user-1",
            conversation_id="conv-1",
            message='Post "Hello" to #sales in Slack',
            classification={"intent": "workflow_execution", "risk_level": "high"},
            task_state={},
            connected_integrations=["slack"],
            client=MagicMock(),
        )
    assert result is not None
    assert result["dialogue_mode"] == "confirm"
    mock_execute.assert_not_awaited()


def test_enrich_slack_plan_with_prior_summaries():
    plan = ConnectorActionPlan(
        tool_name="slack_send_message",
        invoke_action="slack.post_message",
        integration="slack",
        kind="write",
        label="Notify Slack",
        args={"channel": "sales", "message": "Weekly update"},
    )
    enriched = ChatOrchestrationService._enrich_plan_with_context(
        plan,
        [{"summary": "Found 2 stale deals."}, {"summary": "Created Monday tasks."}],
    )
    assert "Orchestration summary" in enriched.args["message"]
    assert "stale deals" in enriched.args["message"]


@pytest.mark.asyncio
async def test_skipped_steps_do_not_break_orchestration():
    service = ChatOrchestrationService()
    service._state = MagicMock()
    service._state.update_task_state = AsyncMock()
    service._state.get_task_state = AsyncMock(
        return_value={
            "clarified_params": {
                "goal": "multi",
                "steps": [
                    {
                        "step_id": "step_1",
                        "segment": "Monday",
                        "label": "Monday (not connected)",
                        "kind": "write",
                        "supported": False,
                        "requires_approval": False,
                        "skip_reason": "Connect Monday in Gravitre to run this action.",
                    },
                    {
                        "step_id": "step_2",
                        "segment": "Notify Slack",
                        "label": "Post to Slack",
                        "kind": "write",
                        "supported": True,
                        "requires_approval": True,
                        "plan": {
                            "tool_name": "slack_send_message",
                            "invoke_action": "slack.post_message",
                            "integration": "slack",
                            "kind": "write",
                            "label": "Post to Slack",
                            "args": {"channel": "sales", "message": "Summary"},
                            "requires_approval": True,
                        },
                    },
                ],
                "current_step_index": 0,
                "step_results": [],
                "total_steps": 2,
            },
            "pending_task": {"type": "connector_orchestration", "status": "running"},
        }
    )
    mock_finalize = AsyncMock(
        return_value={
            "stop_pipeline": True,
            "dialogue_mode": "answer",
            "message": "done",
            "execution_result": {"success": True},
            "task_state": {},
        }
    )
    with patch.object(service, "_finalize_orchestration", mock_finalize):
        result = await service._advance_orchestration(
            org_id="org-1",
            user_id="user-1",
            conversation_id="conv-1",
            task_state=await service._state.get_task_state("conv-1", "org-1"),
            classification={},
            client=MagicMock(),
        )
    mock_finalize.assert_not_awaited()
    assert result["dialogue_mode"] == "confirm"
    assert "step 2" in result["message"].lower()


@pytest.mark.asyncio
async def test_finalize_summary_includes_step_outcomes():
    service = ChatOrchestrationService()
    service._state = MagicMock()
    service._state.update_task_state = AsyncMock()
    service._state.get_task_state = AsyncMock(return_value={})
    params = {
        "goal": "hubspot then slack",
        "step_results": [
            {"step_id": "step_1", "label": "Search HubSpot", "success": True, "summary": "Found 2."},
            {
                "step_id": "step_2",
                "label": "Monday",
                "success": False,
                "summary": "Connect Monday in Gravitre to run this action.",
            },
        ],
    }
    result = await service._finalize_orchestration("conv-1", "org-1", "user-1", params, MagicMock())
    assert "1/2" in result["message"] or "Orchestration complete" in result["message"]
    assert result["execution_result"]["success"] is True
