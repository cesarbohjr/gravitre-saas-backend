from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.execution_dispatch import resolve_executable_connector_plan
from app.services.execution_plan_service import ExecutionPlan, ExecutionStep
from app.services.pending_write_resume import (
    frozen_connector_write_params,
    should_resume_frozen_write,
    should_skip_unified_live_for_compiled_write,
)


def _frozen_hubspot_state() -> dict:
    return {
        "execution_plan": ExecutionPlan(
            plan_id="compose-plan",
            summary="Respond",
            source="default_compose",
            execution_strategy="ANSWER_ONLY",
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
            "_projection": True,
            "_projection_source": "execution_plan",
            "action": "Compose answer",
            "params": {
                "invoke_action": "hubspot.contacts.create",
                "integration": "hubspot",
                "kind": "write",
                "label": "Create contact",
                "args": {"email": "placeholder.isolated@gravitre-smoke.example.com"},
                "requires_approval": True,
            },
        },
    }


def test_compose_plan_does_not_starve_frozen_write_pending() -> None:
    resolved = resolve_executable_connector_plan(_frozen_hubspot_state())
    assert resolved is not None
    assert resolved.invoke_action == "hubspot.contacts.create"
    assert resolved.integration == "hubspot"
    assert resolved.args.get("email") == "placeholder.isolated@gravitre-smoke.example.com"


def test_gmail_write_step_still_wins_over_mutated_pending() -> None:
    plan = ExecutionPlan(
        plan_id="plan-x",
        summary="Send email",
        source="test",
        steps=[
            ExecutionStep(
                step_id="write_email",
                title="Send email",
                kind="write",
                connector_id="gmail",
                action_key="gmail.send",
                meta={"args": {"to": "stephanie@example.com", "subject": "Gravitre test"}},
            )
        ],
    )
    state = {
        "execution_plan": plan.as_dict(),
        "pending_task": {
            "type": "connector_action",
            "status": "awaiting_confirm",
            "params": {
                "integration": "hubspot",
                "invoke_action": "hubspot.contacts.create",
                "args": {"email": "attacker@example.com"},
            },
        },
    }
    resolved = resolve_executable_connector_plan(state)
    assert resolved is not None
    assert resolved.invoke_action == "gmail.send"
    assert resolved.args.get("to") == "stephanie@example.com"


def test_yes_resumes_frozen_write_and_skips_live() -> None:
    state = _frozen_hubspot_state()
    assert should_resume_frozen_write("yes", state) is True
    assert should_skip_unified_live_for_compiled_write("yes", state, ["hubspot"]) is True
    assert frozen_connector_write_params(state)["invoke_action"] == "hubspot.contacts.create"


def test_bare_yes_without_frozen_write_does_not_skip_live() -> None:
    assert should_skip_unified_live_for_compiled_write("yes", {}, ["hubspot"]) is False
    assert should_resume_frozen_write("yes", {"pending_task": {"type": "connector_action"}}) is False


def test_compiled_hubspot_contact_create_skips_live() -> None:
    prompt = (
        'Create a HubSpot contact for placeholder.isolated@gravitre-smoke.example.com '
        'named "Placeholder Isolated Org".'
    )
    assert should_skip_unified_live_for_compiled_write(prompt, {}, ["hubspot"]) is True
    assert should_skip_unified_live_for_compiled_write(prompt, {}, []) is False


def test_multi_connector_orchestration_does_not_skip_live_for_single_write_mapper() -> None:
    prompt = (
        "Search HubSpot for high-intent leads and draft a follow-up in Slack for approval"
    )
    assert should_skip_unified_live_for_compiled_write(
        prompt, {}, ["hubspot", "slack"]
    ) is False


@pytest.mark.asyncio
async def test_resume_frozen_write_calls_process_turn_confirm() -> None:
    from app.services.pending_write_resume import resume_frozen_write_on_confirm

    executed = {
        "stop_pipeline": True,
        "message": "Created the placeholder HubSpot contact.",
        "execution_result": {"success": True},
        "provider_invoked": True,
    }
    with patch(
        "app.services.chat_connector_execution_service.get_chat_connector_execution_service",
    ) as get_svc:
        svc = MagicMock()
        svc.process_turn = AsyncMock(return_value=executed)
        get_svc.return_value = svc
        turn = await resume_frozen_write_on_confirm(
            message="yes",
            task_state=_frozen_hubspot_state(),
            org_id="org-1",
            user_id="user-1",
            conversation_id="conv-1",
            client=object(),
            settings=MagicMock(),
        )
    assert turn == executed
    kwargs = svc.process_turn.await_args.kwargs
    assert kwargs["pending_reply_intent"] == "confirm"


def test_verified_observation_clears_frozen_write_pending() -> None:
    state = _frozen_hubspot_state()
    state["execution_observations"] = [
        {
            "success": True,
            "capability_id": "hubspot.contacts.create",
            "structured": {
                "invoke_action": "hubspot.contacts.create",
                "provider_record_id": "279246127081",
            },
            "summary": "Created HubSpot contact",
        }
    ]
    assert frozen_connector_write_params(state) is None
    assert should_resume_frozen_write("yes", state) is False
