"""Governed public-browser interact WRITE on the canonical HMAC path.

EXTEND computer_execution + Playwright. Not a second agent runtime.
API-native HubSpot/Gmail writes stay on ActionSpec connectors.
"""
from __future__ import annotations

import re
from typing import Any
from uuid import uuid4

from app.config import Settings, get_settings
from app.services.conversational_execution_service import CONFIRM_PATTERN
from app.services.execution_plan_service import (
    ExecutionPlan,
    ExecutionStep,
    execution_plan_patch,
    mark_plan_terminal,
    observations_patch,
)
from app.services.read_preflight import PreflightResult
from app.services.tool_types import ToolContext, ToolValidationError

ACTION_KEY = "browser_agent.interact"
_PUBLIC_FORM_URL = "https://httpbin.org/forms/post"
_HUBSPOT = re.compile(r"(?is)\bhubspot\b")
_INTERACT = re.compile(
    r"(?is)(?=.*\bhttpbin\.org\b)(?=.*\b(fill|submit|form|post)\b)"
)
_BARE_API_WRITE = re.compile(r"(?is)\b(create a hubspot|update a hubspot|gmail|send an email)\b")


def match_computer_browser_interact(message: str) -> bool:
    text = message or ""
    if _HUBSPOT.search(text) and not re.search(r"(?is)\bdo not (?:use |open |call )?hubspot\b", text):
        return False
    if _BARE_API_WRITE.search(text):
        return False
    return bool(_INTERACT.search(text))


def computer_interact_pending_params(task_state: dict[str, Any] | None) -> dict[str, Any] | None:
    pending = (task_state or {}).get("pending_task") if isinstance(task_state, dict) else None
    if not isinstance(pending, dict):
        return None
    status = str(pending.get("status") or "").strip()
    if status not in {"awaiting_confirm", "awaiting_admin_approval"}:
        return None
    params = pending.get("params") if isinstance(pending.get("params"), dict) else pending
    invoke = str(params.get("invoke_action") or pending.get("invoke_action") or "").strip()
    if invoke != ACTION_KEY:
        return None
    return params if isinstance(params, dict) else None


def computer_interact_should_compile(message: str, task_state: dict[str, Any] | None) -> bool:
    if match_computer_browser_interact(message or ""):
        return True
    if CONFIRM_PATTERN.match((message or "").strip()) and computer_interact_pending_params(task_state):
        return True
    return False


def _frozen_form_args() -> dict[str, Any]:
    return {
        "url": _PUBLIC_FORM_URL,
        "actions": [
            {"type": "fill", "selector": "input[name='custname']", "value": "Gravitre isolated test"},
            {"type": "fill", "selector": "input[name='custemail']", "value": "isolated@gravitre.test"},
            {"type": "click", "selector": "input[type='submit']"},
        ],
    }


def _proof_from_pending(raw: dict[str, Any] | None) -> PreflightResult | None:
    if not isinstance(raw, dict):
        return None
    status = str(raw.get("status") or "")
    digest = str(raw.get("proof_digest") or "")
    if status != "ready" or not digest:
        return None
    return PreflightResult(
        status="ready",
        plan_id=raw.get("plan_id"),
        step_id=raw.get("step_id"),
        action_key=str(raw.get("action_key") or ACTION_KEY),
        connector_id=str(raw.get("connector_id") or "browser_agent"),
        resource=raw.get("resource") if isinstance(raw.get("resource"), dict) else None,
        compiled_parameters=dict(raw.get("compiled_parameters") or {}),
        org_id=str(raw.get("org_id") or ""),
        spec_revision=str(raw.get("spec_revision") or ""),
        proof_digest=digest,
        capability_id=raw.get("capability_id"),
    )


async def try_computer_browser_interact_turn(
    *,
    message: str,
    org_id: str,
    client: Any,
    settings: Settings | None,
    connected_integrations: list[str] | None,
    task_state: dict[str, Any] | None,
    user_id: str | None = None,
    conversation_id: str | None = None,
) -> dict[str, Any] | None:
    del connected_integrations
    state = dict(task_state or {})
    pending_params = computer_interact_pending_params(state)
    if pending_params and CONFIRM_PATTERN.match((message or "").strip()):
        return await _execute_confirmed_interact(
            org_id=org_id,
            client=client,
            settings=settings,
            task_state=state,
            pending_params=pending_params,
            user_id=user_id,
            conversation_id=conversation_id,
        )
    if not match_computer_browser_interact(message or ""):
        return None
    return _compile_interact(
        message=message or "",
        org_id=org_id,
        client=client,
        settings=settings,
        task_state=state,
        user_id=user_id,
        conversation_id=conversation_id,
    )


def _compile_interact(
    *,
    message: str,
    org_id: str,
    client: Any,
    settings: Settings | None,
    task_state: dict[str, Any],
    user_id: str | None,
    conversation_id: str | None,
) -> dict[str, Any]:
    from app.services.sealed_read_execution import attributable_read_actor_id
    from app.services.write_preflight import compile_write_for_context

    existing = ExecutionPlan.from_dict(task_state.get("execution_plan"))
    plan_id = existing.plan_id if existing is not None else str(uuid4())
    step = ExecutionStep(
        step_id="computer_interact",
        title="Public browser form fill",
        kind="write",
        connector_id="browser_agent",
        action_key=ACTION_KEY,
    )
    plan = ExecutionPlan(
        plan_id=plan_id,
        summary="Fill the public httpbin form after approval",
        objective=message[:240],
        steps=[step],
        source="computer_execution",
        execution_strategy="browser_cdp",
        capability_id="computer.browser.interact",
    )
    actor_id = attributable_read_actor_id(user_id) or "computer-interact"
    ctx = ToolContext(
        settings=settings or get_settings(),
        client=client,
        org_id=org_id,
        actor_id=actor_id,
        environment_name="production",
        cognitive_invoke=True,
        plan_id=plan.plan_id,
        capability_id=plan.capability_id,
        conversation_id=conversation_id,
        step_id=step.step_id,
    )
    proposed = _frozen_form_args()
    proof = compile_write_for_context(
        ctx=ctx,
        invoke_action=ACTION_KEY,
        args=proposed,
        user_message=message,
        connected_integrations=["browser_agent"],
        task_state=task_state,
    )
    if not proof.ok:
        plan = mark_plan_terminal(plan, "blocked")
        return {
            "stop_pipeline": True,
            "dialogue_mode": "answer",
            "message": proof.user_message()
            or "I couldn't compile that public form fill. Nothing was submitted.",
            "task_state": {**task_state, **execution_plan_patch(plan)},
            "workflow_status": "blocked",
            "execution_path": "computer_browser_interact_compile",
            "writes_started": False,
            "provider_reinvoked": False,
        }
    pending_task = {
        "status": "awaiting_confirm",
        "type": "connector_action",
        "invoke_action": ACTION_KEY,
        "kind": "write",
        "params": {
            "invoke_action": ACTION_KEY,
            "integration": "browser_agent",
            "kind": "write",
            "requires_approval": True,
            "args": dict(proof.compiled_parameters),
            "preflight_proof": {
                **proof.as_dict(),
                "org_id": proof.org_id,
                "proof_digest": proof.proof_digest,
                "spec_revision": proof.spec_revision,
            },
        },
    }
    plan = mark_plan_terminal(plan, "awaiting_confirm")
    return {
        "stop_pipeline": True,
        "dialogue_mode": "confirm",
        "message": (
            "I can fill the public httpbin.org form with the isolated test name and email, "
            "then submit it. Nothing has been submitted yet. Say yes to approve."
        ),
        "task_state": {
            **task_state,
            **execution_plan_patch(plan),
            "pending_task": pending_task,
            "pending_action": {
                "status": "awaiting_user_confirmation",
                "action": ACTION_KEY,
                "write_allowed": False,
            },
        },
        "workflow_status": "awaiting_confirm",
        "execution_path": "computer_browser_interact_compile",
        "writes_started": False,
        "provider_reinvoked": False,
        "selected_action": ACTION_KEY,
        "plan_id": plan.plan_id,
    }


async def _execute_confirmed_interact(
    *,
    org_id: str,
    client: Any,
    settings: Settings | None,
    task_state: dict[str, Any],
    pending_params: dict[str, Any],
    user_id: str | None,
    conversation_id: str | None,
) -> dict[str, Any]:
    from app.services.browser_agent_service import browser_agent_interact
    from app.services.computer_execution import observation_from_browser_result
    from app.services.durable_work_session import bind_finished_work, execution_result_from_finished_work
    from app.services.sealed_read_execution import attributable_read_actor_id
    from app.services.write_preflight import enforce_invoke_write_preflight

    proof = _proof_from_pending(pending_params.get("preflight_proof"))
    args = dict(pending_params.get("args") or {})
    if proof is None:
        return {
            "stop_pipeline": True,
            "dialogue_mode": "answer",
            "message": "That browser form fill wasn't compiled before confirmation. Nothing was submitted.",
            "task_state": task_state,
            "workflow_status": "blocked",
            "execution_path": "computer_browser_interact_confirm",
            "writes_started": False,
        }
    actor_id = attributable_read_actor_id(user_id) or "computer-interact"
    ctx = ToolContext(
        settings=settings or get_settings(),
        client=client,
        org_id=org_id,
        actor_id=actor_id,
        environment_name="production",
        cognitive_invoke=True,
        plan_id=proof.plan_id,
        capability_id=proof.capability_id,
        conversation_id=conversation_id,
        step_id=proof.step_id,
        preflight_result=proof,
    )
    try:
        sealed = enforce_invoke_write_preflight(ctx, ACTION_KEY, args)
    except ToolValidationError as exc:
        return {
            "stop_pipeline": True,
            "dialogue_mode": "answer",
            "message": str(exc) or "The compiled form fill no longer matches. Nothing was submitted.",
            "task_state": task_state,
            "workflow_status": "blocked",
            "execution_path": "computer_browser_interact_confirm",
            "writes_started": False,
        }
    url = str(sealed.get("url") or "")
    actions = sealed.get("actions")
    raw = await browser_agent_interact(
        url,
        actions=actions if isinstance(actions, list) else [],
        settings=settings or get_settings(),
        approval_id=str(proof.proof_digest),
        hmac_verified=True,
    )
    plan = ExecutionPlan.from_dict(task_state.get("execution_plan")) or ExecutionPlan(
        plan_id=str(proof.plan_id or uuid4()),
        summary="Public browser form fill",
        source="computer_execution",
        steps=[
            ExecutionStep(
                step_id="computer_interact",
                title="Public browser form fill",
                kind="write",
                action_key=ACTION_KEY,
            )
        ],
    )
    obs = observation_from_browser_result(
        plan=plan,
        result={**raw, "strategy": "browser_cdp", "success": not raw.get("pending_approval")},
        approval_id=str(proof.proof_digest),
    )
    success = bool(obs.success)
    plan = mark_plan_terminal(plan, "completed" if success else "failed")
    summary = (
        f"Submitted the public httpbin form. Current URL: {raw.get('url') or url}."
        if success
        else str(raw.get("message") or "The public form fill did not complete.")
    )
    merged = {
        **task_state,
        **execution_plan_patch(plan),
        **observations_patch([obs]),
        "pending_task": {**dict(task_state.get("pending_task") or {}), "status": "executed"},
        "pending_action": {"status": "executed", "action": ACTION_KEY, "write_allowed": False},
        "computer_browser_evidence": {
            "strategy": "browser_cdp",
            "mode": raw.get("mode"),
            "url": raw.get("url"),
            "steps": raw.get("steps") or [],
        },
    }
    merged = bind_finished_work(merged, body=summary, title="Public browser form result")
    return {
        "stop_pipeline": True,
        "dialogue_mode": "answer",
        "message": summary,
        "task_state": merged,
        "workflow_status": "completed" if success else "failed",
        "execution_path": "computer_browser_interact_confirm",
        "execution_result": execution_result_from_finished_work(merged, body=summary, success=success),
        "writes_started": True,
        "provider_reinvoked": True,
        "plan_id": plan.plan_id,
    }
