"""Crash-boundary coverage for one logical action (no second orchestrator)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.action_lifecycle import (
    claim_pending_write,
    composer_truth_headline,
    existing_successful_write,
    persist_uncertain_outcome_patch,
    persist_write_outcome_patch,
    recover_orphaned_executing,
    semantic_stage_from_state,
    write_plan_for_action,
)
from app.services.chat_connector_models import ConnectorActionPlan
from app.services.execution_plan_adapters import enrich_task_state_patch
from app.services.execution_plan_service import ExecutionPlan, ExecutionStep, apply_observations_to_plan
from app.services.execution_plan_service import ExecutionObservation
from app.services.post_action_experience_service import enrich_execution_turn
from app.services.conversational_execution_service import ExecutionResult


def _plan() -> ConnectorActionPlan:
    return ConnectorActionPlan(
        tool_name="hubspot_contacts_create",
        invoke_action="hubspot.contacts.create",
        integration="hubspot",
        kind="write",
        label="HubSpot contact created",
        args={"email": "placeholder.isolated@gravitre-smoke.example.com"},
        requires_approval=True,
    )


def _compose_state() -> dict:
    return {
        "execution_plan": ExecutionPlan(
            plan_id="compose-1",
            summary="Respond",
            source="default_compose",
            terminal_status="running",
            steps=[
                ExecutionStep(
                    step_id="compose",
                    title="Compose answer",
                    kind="compose",
                    status="pending",
                )
            ],
        ).as_dict(),
        "pending_task": {
            "type": "connector_action",
            "status": "awaiting_confirm",
            "params": {
                "invoke_action": "hubspot.contacts.create",
                "integration": "hubspot",
                "kind": "write",
                "args": {"email": "placeholder.isolated@gravitre-smoke.example.com"},
            },
        },
    }


def test_a_claim_before_provider_invoke() -> None:
    outcome, claimed = claim_pending_write(_compose_state()["pending_task"])
    assert outcome == "claimed"
    assert claimed["status"] == "executing"
    assert claimed["execution_claim_id"]


def test_b_observation_persisted_after_invoke() -> None:
    patch = persist_write_outcome_patch(
        task_state=_compose_state(),
        connector_plan=_plan(),
        success=True,
        summary="created",
        structured={"contact": {"id": "278948763624"}, "id": "278948763624"},
        pending_task=_compose_state()["pending_task"],
        verification=None,
    )
    obs = patch["execution_observations"]
    assert obs
    assert obs[-1]["structured"]["provider_record_id"] == "278948763624"
    assert patch["execution_plan"]["terminal_status"] != "running"
    assert patch["pending_task"]["lifecycle"] == "EXECUTED_UNVERIFIED"


def test_c_observation_then_terminalize() -> None:
    plan = write_plan_for_action(_plan(), existing=ExecutionPlan.from_dict(_compose_state()["execution_plan"]))
    obs = ExecutionObservation(
        step_id="connector_primary",
        connector_id="hubspot",
        success=True,
        summary="created",
        structured={"provider_record_id": "1"},
    )
    updated = apply_observations_to_plan(plan, [obs])
    assert updated.steps[0].status == "completed"
    assert updated.terminal_status == "completed"


def test_d_approval_consumed_before_execute() -> None:
    first, claimed = claim_pending_write(_compose_state()["pending_task"])
    assert first == "claimed"
    second, _ = claim_pending_write(claimed)
    assert second == "already_claimed"


def test_e_uncertain_timeout_does_not_complete() -> None:
    patch = persist_uncertain_outcome_patch(
        task_state=_compose_state(),
        connector_plan=_plan(),
        summary="timeout",
        error="timeout",
    )
    assert patch["pending_task"]["status"] == "outcome_uncertain"
    assert patch["action_lifecycle"] == "OUTCOME_UNCERTAIN"
    assert patch["execution_plan"]["terminal_status"] != "completed"


def test_f_duplicate_yes_does_not_reclaim() -> None:
    pending = dict(_compose_state()["pending_task"])
    pending["status"] = "executed"
    outcome, _ = claim_pending_write(pending)
    assert outcome == "already_done"
    session = {
        "connector_session": {
            "stepOutputs": {
                "connector_hubspot.contacts.create": {
                    "invokeAction": "hubspot.contacts.create",
                    "success": True,
                    "structured": {"id": "278948763624"},
                }
            }
        }
    }
    replay = existing_successful_write(session, invoke_action="hubspot.contacts.create")
    assert replay is not None


def test_g_worker_restart_lease_recovery() -> None:
    pending = {
        "status": "executing",
        "execution_claim_id": "claim-1",
        "claimed_at": (datetime.now(timezone.utc) - timedelta(seconds=900)).isoformat(),
    }
    recovered = recover_orphaned_executing(pending, max_age_seconds=600)
    assert recovered is not None
    assert recovered["status"] == "awaiting_reconciliation"
    fresh = {
        "status": "executing",
        "execution_claim_id": "claim-1",
        "claimed_at": datetime.now(timezone.utc).isoformat(),
    }
    assert recover_orphaned_executing(fresh, max_age_seconds=600) is None


def test_h_refresh_resume_maps_lifecycle() -> None:
    state = persist_write_outcome_patch(
        task_state=_compose_state(),
        connector_plan=_plan(),
        success=True,
        summary="created",
        structured={"id": "99"},
        pending_task=_compose_state()["pending_task"],
        verification={"verified": True},
    )
    assert semantic_stage_from_state(state) == "COMPLETED"
    assert state["execution_plan"]["terminal_status"] == "completed"


def test_i_voice_confirm_uses_same_claim() -> None:
    from app.services.conversational_execution_service import CONFIRM_PATTERN

    assert CONFIRM_PATTERN.match("yes")
    assert CONFIRM_PATTERN.match("Yes.")
    outcome, claimed = claim_pending_write(_compose_state()["pending_task"])
    assert outcome == "claimed"
    assert claim_pending_write(claimed)[0] == "already_claimed"


def test_j_multi_step_parent_not_complete_while_required_running() -> None:
    plan = ExecutionPlan(
        plan_id="wf",
        summary="multi",
        source="orchestration",
        terminal_status="running",
        steps=[
            ExecutionStep(step_id="s1", title="write", kind="write", action_key="hubspot.contacts.create"),
            ExecutionStep(step_id="s2", title="write2", kind="write", action_key="hubspot.notes.create"),
        ],
    )
    obs = ExecutionObservation(step_id="s1", connector_id="hubspot", success=True, summary="one")
    updated = apply_observations_to_plan(plan, [obs])
    assert updated.terminal_status != "completed"
    assert updated.steps[1].status == "pending"


def test_compose_plan_cannot_mask_write_observation() -> None:
    patch = persist_write_outcome_patch(
        task_state=_compose_state(),
        connector_plan=_plan(),
        success=True,
        summary="created",
        structured={"id": "278948763624"},
        pending_task=_compose_state()["pending_task"],
    )
    merged = enrich_task_state_patch(patch, current_state=_compose_state())
    assert merged["execution_plan"]["source"] != "default_compose"
    assert merged["execution_observations"]
    assert merged["execution_plan"]["terminal_status"] in {"partial", "completed"}


def test_composer_does_not_say_done_on_unverified_invoke() -> None:
    text = composer_truth_headline(
        success=True,
        verified=False,
        uncertain=False,
        label="HubSpot contact created",
        body="created",
    )
    assert "Done" not in text
    turn = enrich_execution_turn(
        message="",
        execution=ExecutionResult(
            success=True,
            entity_type="connector",
            entity_id="278948763624",
            title="HubSpot contact created",
            body="Contact created.",
            integration="hubspot",
            structured={"id": "278948763624"},
        ),
        plan=_plan(),
        task_state={},
    )
    assert "Done —" not in turn["message"]
    assert "confirming" in turn["message"].lower() or "sent to the provider" in turn["message"].lower()


def test_composer_confirmed_when_verified() -> None:
    turn = enrich_execution_turn(
        message="",
        execution=ExecutionResult(
            success=True,
            entity_type="connector",
            entity_id="278948763624",
            title="HubSpot contact created",
            body="Contact created.",
            integration="hubspot",
            structured={
                "id": "278948763624",
                "verification": {"verified": True},
                "verification_status": "verified",
            },
        ),
        plan=_plan(),
        task_state={},
    )
    assert "confirmed" in turn["message"].lower()


def test_unauthorized_actor_cannot_claim() -> None:
    pending = {
        "status": "awaiting_confirm",
        "actor_id": "user-a",
        "params": {"invoke_action": "hubspot.contacts.create"},
    }
    outcome, _ = claim_pending_write(pending, actor_id="user-b")
    assert outcome == "unauthorized"


def test_stale_completed_cannot_reclaim() -> None:
    outcome, _ = claim_pending_write({"status": "cancelled", "actor_id": "u1"}, actor_id="u1")
    assert outcome == "conflict"


@pytest.mark.asyncio
async def test_cas_second_claim_fails() -> None:
    from app.services.conversation_state_service import ConversationStateService

    svc = ConversationStateService.__new__(ConversationStateService)
    state = {
        "pending_task": {
            "status": "awaiting_confirm",
            "actor_id": "u1",
            "type": "connector_action",
        }
    }

    class _Rpc:
        def __init__(self) -> None:
            self.calls = 0

        def rpc(self, *args, **kwargs):
            self.calls += 1
            chain = MagicMock()
            if self.calls == 1:
                chain.execute.return_value = MagicMock(data={"pending_task": {"status": "executing"}})
            else:
                chain.execute.return_value = MagicMock(data=None)
            return chain

        def table(self, *args, **kwargs):
            raise AssertionError("filtered update should not run when rpc returns")

    db = _Rpc()
    svc._client = lambda client=None: db
    svc.get_task_state = AsyncMock(return_value=state)
    first = await svc.compare_and_set_pending_status(
        "c1",
        "o1",
        expected_status="awaiting_confirm",
        updates={"pending_task": {"status": "executing", "execution_claim_id": "a", "claimed_at": "t"}},
        actor_id="u1",
    )
    second = await svc.compare_and_set_pending_status(
        "c1",
        "o1",
        expected_status="awaiting_confirm",
        updates={"pending_task": {"status": "executing", "execution_claim_id": "b", "claimed_at": "t"}},
        actor_id="u1",
    )
    assert first is True
    assert second is False
    assert db.calls == 2


@pytest.mark.asyncio
async def test_duplicate_confirm_skips_second_invoke() -> None:
    from app.services.chat_connector_execution_service import ChatConnectorExecutionService

    svc = ChatConnectorExecutionService.__new__(ChatConnectorExecutionService)
    svc._registry = MagicMock()
    svc._registry.execute_invoke_action = AsyncMock(side_effect=AssertionError("must not invoke"))
    svc.settings = MagicMock()
    state = {
        "pending_task": {
            "type": "connector_action",
            "status": "executed",
            "params": {"invoke_action": "hubspot.contacts.create"},
        },
        "connector_session": {
            "stepOutputs": {
                "x": {
                    "invokeAction": "hubspot.contacts.create",
                    "success": True,
                    "summary": "already",
                    "structured": {"id": "1"},
                }
            }
        },
    }
    result = await svc._replay_existing_write_result(
        state,
        plan=_plan(),
        conversation_id="c1",
        org_id="o1",
        user_id="u1",
        client=None,
        own_terminal_outcome=False,
        classification={},
    )
    assert result is not None
    assert result.structured.get("replayed") is True
    svc._registry.execute_invoke_action.assert_not_called()
