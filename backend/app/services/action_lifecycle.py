"""Single logical-action lifecycle mapped onto existing ExecutionPlan / PendingAction.

Semantic stages reuse persisted enums; this module does not add a second state store.
Guarantees borrowed from HITL pause/resume, Stripe-style keys (when the provider
supports them), Temporal-style reconcile-before-retry, and outbox-style persist of
the Observation independently from the HTTP provider call.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from app.core.safe_dict import safe_normalize_stored_dict
from app.services.chat_connector_models import ConnectorActionPlan
from app.services.execution_plan_adapters import execution_plan_from_connector_action
from app.services.execution_plan_service import (
    ExecutionObservation,
    ExecutionPlan,
    apply_observations_to_plan,
    execution_plan_patch,
    observations_patch,
)

SemanticStage = Literal[
    "PREPARED",
    "AWAITING_APPROVAL",
    "APPROVED",
    "EXECUTING",
    "EXECUTED_UNVERIFIED",
    "VERIFIED",
    "COMPLETED",
    "REJECTED",
    "CANCELLED",
    "FAILED",
    "OUTCOME_UNCERTAIN",
    "AWAITING_RECONCILIATION",
]

_AWAITING = frozenset({"awaiting_confirm", "awaiting_admin_approval", "awaiting_user"})
_CLAIMED = frozenset({"executing", "claimed"})
_DONE = frozenset({"executed", "completed", "verified"})


def semantic_stage_from_state(task_state: dict[str, Any] | None) -> SemanticStage:
    state = task_state if isinstance(task_state, dict) else {}
    pending = state.get("pending_task") if isinstance(state.get("pending_task"), dict) else {}
    status = str(pending.get("status") or "").strip().lower()
    plan = ExecutionPlan.from_dict(state.get("execution_plan"))
    terminal = str(plan.terminal_status if plan else "")
    if status in {"rejected", "declined"} or terminal == "cancelled":
        return "REJECTED" if status in {"rejected", "declined"} else "CANCELLED"
    if status == "cancelled":
        return "CANCELLED"
    if status == "failed" or terminal == "failed":
        return "FAILED"
    if status == "outcome_uncertain":
        return "OUTCOME_UNCERTAIN"
    if status == "awaiting_reconciliation":
        return "AWAITING_RECONCILIATION"
    if status in _AWAITING or terminal == "waiting_for_approval":
        return "AWAITING_APPROVAL"
    if status in _CLAIMED:
        return "EXECUTING"
    obs = _latest_observation(state)
    structured = obs.get("structured") if isinstance(obs, dict) and isinstance(obs.get("structured"), dict) else {}
    verified = bool(
        isinstance(obs, dict)
        and (
            obs.get("verification_status") == "verified"
            or structured.get("verification_status") == "verified"
            or (isinstance(structured.get("verification"), dict) and structured["verification"].get("verified"))
        )
    )
    if status in _DONE or terminal == "completed":
        if verified:
            return "COMPLETED"
        if obs:
            return "VERIFIED" if verified else "EXECUTED_UNVERIFIED"
        return "EXECUTED_UNVERIFIED"
    if terminal == "running":
        return "EXECUTING"
    return "PREPARED"


def _latest_observation(state: dict[str, Any]) -> dict[str, Any] | None:
    rows = state.get("execution_observations")
    if not isinstance(rows, list) or not rows:
        return None
    last = rows[-1]
    return last if isinstance(last, dict) else None


def provider_record_id(structured: dict[str, Any] | None) -> str | None:
    from app.services.entity_get_verify import extract_entity_id

    data = structured if isinstance(structured, dict) else {}
    return (
        extract_entity_id(data)
        or extract_entity_id(data.get("contact") if isinstance(data.get("contact"), dict) else None)
        or str(data.get("id") or "").strip()
        or None
    )


def logical_action_id(
    *,
    org_id: str,
    conversation_id: str,
    invoke_action: str,
    pending_action_id: str | None,
    args: dict[str, Any] | None,
) -> str:
    import hashlib
    import json

    payload = {
        "org_id": org_id,
        "conversation_id": conversation_id,
        "invoke_action": invoke_action,
        "pending_action_id": pending_action_id or "",
        "args": safe_normalize_stored_dict(args),
    }
    raw = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def existing_successful_write(
    task_state: dict[str, Any] | None,
    *,
    invoke_action: str,
) -> dict[str, Any] | None:
    """Replay-safe: connector_session step output already recorded a success."""
    state = task_state if isinstance(task_state, dict) else {}
    session = state.get("connector_session") if isinstance(state.get("connector_session"), dict) else {}
    outputs = session.get("stepOutputs") or session.get("step_outputs") or {}
    if isinstance(outputs, dict):
        for row in outputs.values():
            if not isinstance(row, dict):
                continue
            action = str(row.get("invokeAction") or row.get("invoke_action") or "")
            if action == invoke_action and row.get("success") is True:
                return row
    obs = _latest_observation(state)
    if obs and str(obs.get("action_key") or "") == invoke_action and obs.get("success"):
        return obs
    pending = state.get("pending_task") if isinstance(state.get("pending_task"), dict) else {}
    if str(pending.get("status") or "") in _DONE and isinstance(pending.get("result"), dict):
        return pending["result"]
    return None


def claim_pending_write(pending: dict[str, Any] | None) -> tuple[str, dict[str, Any]]:
    """Atomically-intended claim. Returns claimed | already_done | conflict."""
    blob = dict(pending) if isinstance(pending, dict) else {}
    status = str(blob.get("status") or "").strip().lower()
    if status in _DONE:
        return "already_done", blob
    if status in _CLAIMED and blob.get("execution_claim_id"):
        return "already_claimed", blob
    if status not in _AWAITING and status != "awaiting_user":
        return "conflict", blob
    claim_id = str(uuid4())
    blob["status"] = "executing"
    blob["execution_claim_id"] = claim_id
    blob["claimed_at"] = datetime.now(timezone.utc).isoformat()
    return "claimed", blob


def observation_from_write(
    *,
    plan: ConnectorActionPlan,
    execution_plan: ExecutionPlan,
    success: bool,
    summary: str,
    structured: dict[str, Any],
    verification: dict[str, Any] | None,
    error: str | None = None,
) -> ExecutionObservation:
    step = next(
        (s for s in execution_plan.steps if s.action_key == plan.invoke_action or s.kind == "write"),
        execution_plan.steps[0] if execution_plan.steps else None,
    )
    step_id = step.step_id if step else "connector_primary"
    record_id = provider_record_id(structured)
    verify_status = "unverified"
    if verification and verification.get("verified"):
        verify_status = "verified"
    elif verification and verification.get("follow_up_attempted"):
        verify_status = "verification_pending"
    now = datetime.now(timezone.utc).isoformat()
    return ExecutionObservation(
        observation_id=str(uuid4()),
        step_id=step_id,
        connector_id=plan.integration,
        success=success,
        summary=summary,
        structured={
            **dict(structured or {}),
            "provider_record_id": record_id,
            "invoke_action": plan.invoke_action,
            "verification_status": verify_status,
            "verification": dict(verification or {}),
        },
        error=error,
        plan_id=execution_plan.plan_id,
        source="connector_execute_plan",
        capability_id=plan.invoke_action,
        resource=record_id,
        completed_at=now,
    )


def write_plan_for_action(
    plan: ConnectorActionPlan,
    *,
    existing: ExecutionPlan | None,
) -> ExecutionPlan:
    if existing is not None:
        write_steps = [
            s
            for s in existing.steps
            if s.kind in {"write", "read", "workflow"} and (s.action_key or s.kind == "write")
        ]
        if write_steps or existing.source not in {"default_compose", "compose"}:
            if any(s.action_key == plan.invoke_action or s.kind == "write" for s in existing.steps):
                return existing
    built = execution_plan_from_connector_action(
        plan,
        plan_id=existing.plan_id if existing else None,
        source="connector_write",
    )
    if existing is not None:
        built.parent_plan_id = existing.plan_id
        built.conversation_id = existing.conversation_id
        built.turn_id = existing.turn_id
        built.revision = int(existing.revision or 1) + 1
    return built


def persist_uncertain_outcome_patch(
    *,
    task_state: dict[str, Any] | None,
    connector_plan: ConnectorActionPlan,
    summary: str,
    error: str | None = None,
) -> dict[str, Any]:
    state = task_state if isinstance(task_state, dict) else {}
    existing = ExecutionPlan.from_dict(state.get("execution_plan"))
    exec_plan = write_plan_for_action(connector_plan, existing=existing)
    exec_plan.terminal_status = "blocked"
    pending = dict(state.get("pending_task") or {})
    pending["type"] = "connector_action"
    pending["status"] = "outcome_uncertain"
    pending["lifecycle"] = "OUTCOME_UNCERTAIN"
    pending["params"] = {
        **(pending.get("params") if isinstance(pending.get("params"), dict) else {}),
        "invoke_action": connector_plan.invoke_action,
        "integration": connector_plan.integration,
        "kind": connector_plan.kind,
        "args": dict(connector_plan.args or {}),
    }
    obs = observation_from_write(
        plan=connector_plan,
        execution_plan=exec_plan,
        success=False,
        summary=summary,
        structured={"outcome": "uncertain"},
        verification=None,
        error=error,
    )
    obs.structured["verification_status"] = "uncertain"
    return {
        **execution_plan_patch(exec_plan),
        **observations_patch([obs]),
        "pending_task": pending,
        "action_lifecycle": "OUTCOME_UNCERTAIN",
    }


def recover_orphaned_executing(
    pending: dict[str, Any] | None,
    *,
    max_age_seconds: int = 600,
    now: datetime | None = None,
) -> dict[str, Any] | None:
    """Bounded recovery: executing without a result after the lease expires."""
    blob = dict(pending) if isinstance(pending, dict) else {}
    if str(blob.get("status") or "") not in _CLAIMED:
        return None
    claimed_at = str(blob.get("claimed_at") or "")
    try:
        started = datetime.fromisoformat(claimed_at.replace("Z", "+00:00"))
    except ValueError:
        started = None
    clock = now or datetime.now(timezone.utc)
    if started is not None and (clock - started).total_seconds() < max_age_seconds:
        return None
    blob["status"] = "awaiting_reconciliation"
    blob["lifecycle"] = "AWAITING_RECONCILIATION"
    return blob


def persist_write_outcome_patch(
    *,
    task_state: dict[str, Any] | None,
    connector_plan: ConnectorActionPlan,
    success: bool,
    summary: str,
    structured: dict[str, Any],
    pending_task: dict[str, Any] | None,
    verification: dict[str, Any] | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    state = task_state if isinstance(task_state, dict) else {}
    existing = ExecutionPlan.from_dict(state.get("execution_plan"))
    exec_plan = write_plan_for_action(connector_plan, existing=existing)
    obs = observation_from_write(
        plan=connector_plan,
        execution_plan=exec_plan,
        success=success,
        summary=summary,
        structured=structured,
        verification=verification,
        error=error,
    )
    exec_plan = apply_observations_to_plan(exec_plan, [obs])
    if success and verification and verification.get("verified"):
        exec_plan.terminal_status = "completed"
    elif success:
        exec_plan.terminal_status = "partial"
    pending = dict(pending_task or state.get("pending_task") or {})
    pending["type"] = "connector_action"
    if success and verification and verification.get("verified"):
        pending["status"] = "executed"
        pending["lifecycle"] = "COMPLETED"
    elif success:
        pending["status"] = "executed"
        pending["lifecycle"] = "EXECUTED_UNVERIFIED"
    else:
        pending["status"] = "failed"
        pending["lifecycle"] = "FAILED"
    pending["params"] = {
        **(pending.get("params") if isinstance(pending.get("params"), dict) else {}),
        "invoke_action": connector_plan.invoke_action,
        "integration": connector_plan.integration,
        "kind": connector_plan.kind,
        "args": dict(connector_plan.args or {}),
        "provider_record_id": provider_record_id(structured),
    }
    pending_action = state.get("pending_action") if isinstance(state.get("pending_action"), dict) else {}
    if pending_action:
        pending_action = {
            **pending_action,
            "status": "confirmed" if success else "cancelled",
            "step_id": obs.step_id,
            "plan_id": exec_plan.plan_id,
        }
    prior_obs = [
        row
        for row in (state.get("execution_observations") or [])
        if isinstance(row, dict) and str(row.get("step_id") or "") != obs.step_id
    ]
    patch = {
        **execution_plan_patch(exec_plan),
        "execution_observations": prior_obs + [obs.as_dict()],
        "pending_task": pending,
        "action_lifecycle": semantic_stage_from_state(
            {**state, "execution_plan": exec_plan.as_dict(), "execution_observations": [obs.as_dict()], "pending_task": pending}
        ),
    }
    if pending_action:
        patch["pending_action"] = pending_action
    return patch


def composer_truth_headline(
    *,
    success: bool,
    verified: bool,
    uncertain: bool,
    label: str,
    body: str,
) -> str:
    title = (label or "that action").strip()
    detail = (body or "").strip()
    if uncertain:
        return (
            f"I attempted **{title}**, but the provider result is not confirmed yet. "
            f"I have not marked it complete.{(' ' + detail) if detail else ''}"
        ).strip()
    if not success:
        return f"I couldn't complete **{title}**. {detail}".strip()
    if not verified:
        return (
            f"**{title}** was sent to the provider. I'm confirming the record before treating it as complete."
            + (f" {detail}" if detail else "")
        ).strip()
    return f"**{title}** is confirmed.\n\n{detail}".strip()
