"""Tests for multi-step chat connector orchestration."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.chat_orchestration_service import (
    ChatOrchestrationService,
    OrchestrationStep,
)
from app.services.conversational_execution_service import ExecutionResult
from app.services.chat_connector_execution_service import ConnectorActionPlan


@pytest.fixture
def orchestration_service():
    service = ChatOrchestrationService()
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


def test_detects_multi_integration_prompt(orchestration_service):
    message = "Find stale HubSpot deals, create follow-up tasks in Monday, and notify Slack"
    assert orchestration_service.is_orchestration_intent(
        message,
        {},
        ["hubspot", "slack"],
    )


def test_wave67_plan_before_tools_is_not_orchestration(orchestration_service):
    """STA-325 — meta 'outline a plan before tools' must not open awaiting_plan_confirm."""
    message = (
        "Using Apollo, list my contact lists and summarize the first few names. "
        "Then outline a short plan before calling tools."
    )
    assert (
        orchestration_service.is_orchestration_intent(
            message,
            {},
            ["apollo", "slack"],
        )
        is False
    )


def test_meta_plan_segment_detection(orchestration_service):
    assert orchestration_service._is_meta_plan_segment(
        "outline a short plan before calling tools"
    )
    assert orchestration_service._is_meta_plan_segment("plan before calling tools")
    assert not orchestration_service._is_meta_plan_segment(
        "create a Slack post summarizing the plan"
    )


@pytest.mark.asyncio
async def test_unrelated_slack_asks_hold_abandon_not_silent_supersede(orchestration_service):
    """Module B — awaiting orch must offer abandon/hold, not silent-clear + None."""
    params = {
        "goal": "Using Apollo, list my contact lists",
        "steps": [],
        "current_step_index": 0,
        "step_results": [],
        "total_steps": 2,
    }
    task_state = {
        "clarified_params": params,
        "current_plan": {"goal": params["goal"]},
        "pending_task": {
            "type": "connector_orchestration",
            "status": "awaiting_plan_confirm",
            "params": params,
        },
    }
    refreshed = {
        **task_state,
        "pending_hold_prompt": True,
        "pending_hold_new_request": "Post a Slack message",
    }
    orchestration_service._state.get_task_state = AsyncMock(
        side_effect=[task_state, refreshed, refreshed]
    )
    orchestration_service._state.update_task_state = AsyncMock()

    result = await orchestration_service.process_turn(
        org_id="org-1",
        user_id="user-1",
        conversation_id="conv-1",
        message=(
            "Post a Slack message to the default channel saying "
            "'gravitre-wave67-spotcheck failure probe — ignore'. Use the Slack connector."
        ),
        classification={"intent": "workflow_execution"},
        task_state=task_state,
        connected_integrations=["apollo", "slack"],
        client=MagicMock(),
    )

    assert result is not None
    assert result.get("stop_pipeline") is True
    msg = str(result.get("message") or "").lower()
    assert "abandon" in msg and "hold" in msg
    # Must not silent-clear before the user chooses.
    patches = [
        c.args[2]
        for c in orchestration_service._state.update_task_state.await_args_list
        if len(c.args) >= 3 and isinstance(c.args[2], dict)
    ]
    assert any(p.get("pending_hold_prompt") is True for p in patches)


def test_should_not_supersede_plan_tweak(orchestration_service):
    params = {
        "goal": "Find HubSpot deals then notify Slack",
        "steps": [],
    }
    task_state = {
        "clarified_params": params,
        "pending_task": {
            "type": "connector_orchestration",
            "status": "awaiting_plan_confirm",
            "params": params,
        },
    }
    assert (
        orchestration_service._should_supersede_pending_orchestration(
            "change step 2 to use #sales instead",
            task_state,
            ["hubspot", "slack"],
        )
        is False
    )


def test_split_segments_for_hubspot_monday_slack(orchestration_service):
    message = "Find stale HubSpot deals, create follow-up tasks in Monday, and notify Slack"
    segments = orchestration_service._split_segments(message)
    assert len(segments) >= 2
    assert any("hubspot" in segment.lower() for segment in segments)
    assert any("slack" in segment.lower() for segment in segments)


@pytest.mark.asyncio
async def test_plan_confirm_for_multi_step(orchestration_service):
    hubspot_plan = ConnectorActionPlan(
        tool_name="hubspot_search_contacts",
        invoke_action="hubspot.contacts.search",
        integration="hubspot",
        kind="read",
        label="Search HubSpot for stale deals",
        args={"query": "stale deals", "limit": 10},
    )
    slack_plan = ConnectorActionPlan(
        tool_name="slack_send_message",
        invoke_action="slack.post_message",
        integration="slack",
        kind="write",
        label="Post to Slack #sales",
        args={"channel": "sales", "message": "Follow-up summary"},
        requires_approval=True,
    )

    async def fake_plan_segment(**kwargs):
        segment = kwargs["segment"].lower()
        if "hubspot" in segment:
            return OrchestrationStep(
                step_id=kwargs["step_id"],
                segment=kwargs["segment"],
                label=hubspot_plan.label,
                kind="read",
                supported=True,
                requires_approval=False,
                plan=hubspot_plan,
            )
        if "monday" in segment:
            return OrchestrationStep(
                step_id=kwargs["step_id"],
                segment=kwargs["segment"],
                label="Monday tasks",
                kind="write",
                supported=False,
                requires_approval=True,
                skip_reason="Monday not available in chat execution yet.",
            )
        if "slack" in segment:
            return OrchestrationStep(
                step_id=kwargs["step_id"],
                segment=kwargs["segment"],
                label=slack_plan.label,
                kind="write",
                supported=True,
                requires_approval=True,
                plan=slack_plan,
            )
        raise AssertionError(f"unexpected segment: {kwargs['segment']}")

    with patch.object(orchestration_service, "_plan_segment", side_effect=fake_plan_segment):
        result = await orchestration_service.process_turn(
            org_id="org-1",
            user_id="user-1",
            conversation_id="conv-1",
            message="Find stale HubSpot deals, create follow-up tasks in Monday, and notify Slack",
            classification={"intent": "workflow_execution"},
            task_state={},
            connected_integrations=["hubspot", "slack"],
            client=MagicMock(),
        )

    assert result is not None
    assert result["dialogue_mode"] == "confirm"
    assert result["pending_task"]["type"] == "connector_orchestration"
    assert "3-step orchestration" in result["message"].lower()


@pytest.mark.asyncio
async def test_plan_confirm_then_start_runs_read_step(orchestration_service):
    steps = [
        OrchestrationStep(
            step_id="step_1",
            segment="Search HubSpot",
            label="Search HubSpot",
            kind="read",
            supported=True,
            requires_approval=False,
            plan=ConnectorActionPlan(
                tool_name="hubspot_search_contacts",
                invoke_action="hubspot.contacts.search",
                integration="hubspot",
                kind="read",
                label="Search HubSpot",
                args={"query": "stale", "limit": 10},
            ),
        ),
        OrchestrationStep(
            step_id="step_2",
            segment="Notify Slack",
            label="Post to Slack",
            kind="write",
            supported=True,
            requires_approval=True,
            plan=ConnectorActionPlan(
                tool_name="slack_send_message",
                invoke_action="slack.post_message",
                integration="slack",
                kind="write",
                label="Post to Slack",
                args={"channel": "sales", "message": "Summary"},
                requires_approval=True,
            ),
        ),
    ]
    params = {
        "goal": "hubspot then slack",
        "steps": [step.to_dict() for step in steps],
        "current_step_index": 0,
        "step_results": [],
        "total_steps": 2,
    }
    task_state = {
        "clarified_params": params,
        "pending_task": {
            "type": "connector_orchestration",
            "status": "awaiting_plan_confirm",
            "params": params,
        },
    }
    orchestration_service._state.get_task_state = AsyncMock(return_value=task_state)
    mock_execute = AsyncMock(
        return_value=ExecutionResult(
            success=True,
            entity_type="connector",
            entity_id="conn-1",
            connector_management_url="/connectors/conn-1",
            integration="hubspot",
            title="Search HubSpot",
            body="Found 2 contacts.",
            task_label="Search HubSpot",
        )
    )
    with patch.object(orchestration_service._connector, "execute_plan", mock_execute):
        result = await orchestration_service.process_turn(
            org_id="org-1",
            user_id="user-1",
            conversation_id="conv-1",
            message="yes",
            classification={"intent": "workflow_execution"},
            task_state=task_state,
            connected_integrations=["hubspot", "slack"],
            client=MagicMock(),
        )

    assert result is not None
    assert result["dialogue_mode"] == "confirm"
    assert "step 2" in result["message"].lower()
    mock_execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_step_confirm_executes_write(orchestration_service):
    write_plan = ConnectorActionPlan(
        tool_name="slack_send_message",
        invoke_action="slack.post_message",
        integration="slack",
        kind="write",
        label="Post to Slack",
        args={"channel": "sales", "message": "Summary"},
        requires_approval=True,
    )
    steps = [
        OrchestrationStep(
            step_id="step_1",
            segment="Search HubSpot",
            label="Search HubSpot",
            kind="read",
            supported=True,
            requires_approval=False,
            plan=ConnectorActionPlan(
                tool_name="hubspot_search_contacts",
                invoke_action="hubspot.contacts.search",
                integration="hubspot",
                kind="read",
                label="Search HubSpot",
                args={"query": "stale", "limit": 10},
            ),
        ),
        OrchestrationStep(
            step_id="step_2",
            segment="Notify Slack",
            label="Post to Slack",
            kind="write",
            supported=True,
            requires_approval=True,
            plan=write_plan,
        ),
    ]
    params = {
        "goal": "hubspot then slack",
        "steps": [step.to_dict() for step in steps],
        "current_step_index": 1,
        "step_results": [{"step_id": "step_1", "label": "Search HubSpot", "success": True, "summary": "Found 2."}],
        "total_steps": 2,
    }
    task_state = {
        "clarified_params": params,
        "pending_task": {
            "type": "connector_orchestration",
            "status": "awaiting_step_confirm",
            "params": params,
            "current_step": steps[1].to_dict(),
        },
    }
    orchestration_service._state.get_task_state = AsyncMock(return_value=task_state)
    mock_execute = AsyncMock(
        return_value=ExecutionResult(
            success=True,
            entity_type="connector",
            entity_id="conn-2",
            connector_management_url="/connectors/conn-2",
            integration="slack",
            title="Post to Slack",
            body="Message posted.",
            task_label="Post to Slack",
        )
    )
    mock_finalize = AsyncMock(
        return_value={
            "stop_pipeline": True,
            "dialogue_mode": "answer",
            "message": "done",
            "execution_result": {
                "success": True,
                "connector_management_url": "/connectors/conn-2",
                "integration": "slack",
            },
            "task_state": task_state,
        }
    )
    with patch.object(orchestration_service._connector, "execute_plan", mock_execute), patch.object(
        orchestration_service,
        "_advance_orchestration",
        mock_finalize,
    ):
        result = await orchestration_service.process_turn(
            org_id="org-1",
            user_id="user-1",
            conversation_id="conv-1",
            message="yes",
            classification={"intent": "workflow_execution"},
            task_state=task_state,
            connected_integrations=["hubspot", "slack"],
            client=MagicMock(),
        )

    assert result is not None
    mock_execute.assert_awaited_once()
    mock_finalize.assert_awaited_once()


def test_sta307_high_intent_prompt_splits_hubspot_then_slack(orchestration_service):
    """STA-307 — planner must not label both steps HubSpot for the example chip."""
    message = "Search HubSpot for high-intent leads and draft a follow-up in Slack for approval"
    # \"gh\" inside high-intent must not false-match github.
    assert "github" not in orchestration_service._mentioned_integrations(message, [])
    segments = orchestration_service._split_segments(message)
    assert len(segments) >= 2
    assert "hubspot" in segments[0].lower()
    assert "slack" in segments[1].lower()
    assert "hubspot" not in segments[1].lower()


@pytest.mark.asyncio
async def test_sta307_disconnected_pair_labels_and_blocks_immediately(orchestration_service):
    """STA-307 regression: two disconnected connectors → correct labels + terminal blocked."""
    message = "Search HubSpot for high-intent leads and draft a follow-up in Slack for approval"
    result = await orchestration_service.process_turn(
        org_id="org-1",
        user_id="user-1",
        conversation_id="conv-sta307",
        message=message,
        classification={"intent": "workflow_execution"},
        task_state={"pending_task": None},
        connected_integrations=["apollo"],  # hubspot + slack absent
        client=MagicMock(),
    )
    assert result is not None
    assert result["dialogue_mode"] == "answer"
    assert "nothing is runnable" in result["message"].lower() or "blocked" in result["message"].lower()
    # Durable pending written via update_task_state (mock get_task_state is static).
    assert orchestration_service._state.update_task_state.await_count >= 1
    patch = orchestration_service._state.update_task_state.await_args.args[2]
    pending = patch["pending_task"]
    assert pending["type"] == "connector_orchestration"
    assert pending["status"] == "blocked"
    steps = pending["params"]["steps"]
    assert len(steps) >= 2
    labels = [str(s.get("label") or "").lower() for s in steps]
    hub_idx = next(i for i, label in enumerate(labels) if "hubspot" in label)
    slack_idx = next(i for i, label in enumerate(labels) if "slack" in label)
    assert hub_idx != slack_idx
    assert all(s.get("supported") is False for s in steps)
    assert result.get("execution_result", {}).get("success") is False
