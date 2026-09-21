"""3.0-D durable work sessions — EXTEND E5 ExecutionPlan, not a second runtime.

Maps plan terminals onto the 3.0 session machine, checkpoints before WRITE
(intent + approval + inputs + expected result, no secrets), and resumes the
same ``plan_id``. Compatible with ``pending_task`` / ``waiting_for_approval``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from app.core.safe_dict import safe_normalize_stored_dict
from app.services.execution_plan_service import ExecutionPlan, PlanTerminal

SessionPhase = Literal[
    "CREATED",
    "UNDERSTANDING",
    "PLANNING",
    "WORKING",
    "WAITING_USER",
    "WAITING_APPROVAL",
    "WAITING_EXTERNAL",
    "REPAIRING",
    "VERIFYING",
    "COMPLETED",
    "PARTIAL",
    "FAILED",
    "CANCELLED",
]

CHECKPOINT_KEY = "durable_checkpoint"
SESSION_KEY = "durable_session"
DELIVERABLE_KEY = "durable_deliverable"

_SECRET_FRAGMENTS = (
    "secret",
    "token",
    "password",
    "passwd",
    "api_key",
    "apikey",
    "authorization",
    "auth_header",
    "refresh_token",
    "access_token",
    "private_key",
    "credential",
    "hmac",
    "bearer",
)

_PLAN_TO_PHASE: dict[str, SessionPhase] = {
    "pending": "PLANNING",
    "running": "WORKING",
    "waiting_for_approval": "WAITING_APPROVAL",
    "clarification_required": "WAITING_USER",
    "blocked": "WAITING_EXTERNAL",
    "cancelled": "CANCELLED",
    "completed": "COMPLETED",
    "partial": "PARTIAL",
    "failed": "FAILED",
}

_PHASE_TO_PLAN: dict[SessionPhase, PlanTerminal] = {
    "CREATED": "pending",
    "UNDERSTANDING": "pending",
    "PLANNING": "pending",
    "WORKING": "running",
    "WAITING_USER": "clarification_required",
    "WAITING_APPROVAL": "waiting_for_approval",
    "WAITING_EXTERNAL": "blocked",
    "REPAIRING": "running",
    "VERIFYING": "running",
    "COMPLETED": "completed",
    "PARTIAL": "partial",
    "FAILED": "failed",
    "CANCELLED": "cancelled",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _key_looks_secret(key: str) -> bool:
    lowered = str(key or "").strip().lower().replace("-", "_")
    return any(frag in lowered for frag in _SECRET_FRAGMENTS)


def strip_secrets(value: Any) -> Any:
    """Drop secret-looking keys. Never persist tokens/HMAC material in checkpoints."""
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for key, inner in value.items():
            if _key_looks_secret(str(key)):
                continue
            cleaned[str(key)] = strip_secrets(inner)
        return cleaned
    if isinstance(value, list):
        return [strip_secrets(item) for item in value]
    return value


def session_phase_from_plan(plan: ExecutionPlan | None) -> SessionPhase:
    if plan is None:
        return "CREATED"
    return _PLAN_TO_PHASE.get(plan.terminal_status, "WORKING")


def plan_terminal_from_phase(phase: SessionPhase) -> PlanTerminal:
    return _PHASE_TO_PLAN[phase]


def session_phase_from_task_state(task_state: dict[str, Any] | None) -> SessionPhase:
    state = task_state if isinstance(task_state, dict) else {}
    pending = state.get("pending_task") if isinstance(state.get("pending_task"), dict) else {}
    pending_status = str(pending.get("status") or "").strip().lower()
    if pending_status in {"awaiting_confirm", "awaiting_user_confirmation", "awaiting_approval"}:
        return "WAITING_APPROVAL"
    if pending_status in {"awaiting_user", "needs_input"}:
        return "WAITING_USER"
    stored = safe_normalize_stored_dict(state.get(SESSION_KEY))
    stored_phase = str(stored.get("phase") or "").strip().upper()
    if stored_phase in _PHASE_TO_PLAN:
        return stored_phase  # type: ignore[return-value]
    plan = ExecutionPlan.from_dict(state.get("execution_plan"))
    return session_phase_from_plan(plan)


@dataclass
class DeliverableContract:
    diagnosis: str = ""
    evidence: list[str] = field(default_factory=list)
    causes: list[str] = field(default_factory=list)
    uncertainties: list[str] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)
    required: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "diagnosis": self.diagnosis,
            "evidence": list(self.evidence),
            "causes": list(self.causes),
            "uncertainties": list(self.uncertainties),
            "actions": list(self.actions),
            "required": self.required,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> DeliverableContract:
        payload = raw if isinstance(raw, dict) else {}
        evidence = payload.get("evidence")
        causes = payload.get("causes")
        uncertainties = payload.get("uncertainties")
        actions = payload.get("actions")
        return cls(
            diagnosis=str(payload.get("diagnosis") or ""),
            evidence=[str(x) for x in evidence] if isinstance(evidence, list) else [],
            causes=[str(x) for x in causes] if isinstance(causes, list) else [],
            uncertainties=[str(x) for x in uncertainties] if isinstance(uncertainties, list) else [],
            actions=[str(x) for x in actions] if isinstance(actions, list) else [],
            required=bool(payload.get("required")),
        )


@dataclass
class DurableCheckpoint:
    checkpoint_id: str
    plan_id: str
    phase: SessionPhase
    intent: str
    approval_id: str | None
    inputs: dict[str, Any]
    expected_result: str
    context_refs: list[str] = field(default_factory=list)
    resource_identities: list[str] = field(default_factory=list)
    artifact_refs: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=_now_iso)

    def as_dict(self) -> dict[str, Any]:
        return strip_secrets(
            {
                "checkpoint_id": self.checkpoint_id,
                "plan_id": self.plan_id,
                "phase": self.phase,
                "intent": self.intent,
                "approval_id": self.approval_id,
                "inputs": dict(self.inputs),
                "expected_result": self.expected_result,
                "context_refs": list(self.context_refs),
                "resource_identities": list(self.resource_identities),
                "artifact_refs": list(self.artifact_refs),
                "created_at": self.created_at,
            }
        )

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> DurableCheckpoint | None:
        if not isinstance(raw, dict) or not raw.get("plan_id"):
            return None
        phase = str(raw.get("phase") or "WAITING_APPROVAL").strip().upper()
        if phase not in _PHASE_TO_PLAN:
            phase = "WAITING_APPROVAL"
        inputs = strip_secrets(safe_normalize_stored_dict(raw.get("inputs")))
        refs = raw.get("context_refs")
        resources = raw.get("resource_identities")
        artifacts = raw.get("artifact_refs")
        return cls(
            checkpoint_id=str(raw.get("checkpoint_id") or uuid4()),
            plan_id=str(raw["plan_id"]),
            phase=phase,  # type: ignore[arg-type]
            intent=str(raw.get("intent") or ""),
            approval_id=str(raw["approval_id"]) if raw.get("approval_id") else None,
            inputs=inputs if isinstance(inputs, dict) else {},
            expected_result=str(raw.get("expected_result") or ""),
            context_refs=[str(x) for x in refs] if isinstance(refs, list) else [],
            resource_identities=[str(x) for x in resources] if isinstance(resources, list) else [],
            artifact_refs=[str(x) for x in artifacts] if isinstance(artifacts, list) else [],
            created_at=str(raw.get("created_at") or _now_iso()),
        )


def checkpoint_before_write(
    *,
    plan: ExecutionPlan | None,
    intent: str,
    inputs: dict[str, Any] | None,
    expected_result: str = "",
    approval_id: str | None = None,
    pending_task: dict[str, Any] | None = None,
    context_refs: list[str] | None = None,
    resource_identities: list[str] | None = None,
    artifact_refs: list[str] | None = None,
) -> DurableCheckpoint:
    """Persist WRITE intent before state-changing work. Never speculative WRITE."""
    plan_id = ""
    if plan is not None:
        plan_id = plan.plan_id
    if not plan_id and isinstance(pending_task, dict):
        plan_id = str(pending_task.get("execution_plan_id") or pending_task.get("plan_id") or "")
    if not plan_id:
        plan_id = str(uuid4())
    pending = pending_task if isinstance(pending_task, dict) else {}
    resolved_approval = approval_id or (
        str(pending.get("approval_id") or pending.get("pending_action_id") or "") or None
    )
    return DurableCheckpoint(
        checkpoint_id=str(uuid4()),
        plan_id=plan_id,
        phase="WAITING_APPROVAL",
        intent=str(intent or "")[:500],
        approval_id=resolved_approval,
        inputs=strip_secrets(dict(inputs or {})),
        expected_result=str(expected_result or "")[:500],
        context_refs=list(context_refs or []),
        resource_identities=list(resource_identities or []),
        artifact_refs=list(artifact_refs or []),
    )


def attach_write_checkpoint(
    task_state: dict[str, Any],
    *,
    tool_name: str,
    action: str | None,
    args: dict[str, Any] | None,
    expected_result: str = "",
    approval_id: str | None = None,
) -> DurableCheckpoint:
    """Stamp task_state with a WRITE checkpoint and WAITING_APPROVAL session phase."""
    plan = ExecutionPlan.from_dict(task_state.get("execution_plan"))
    pending = task_state.get("pending_task") if isinstance(task_state.get("pending_task"), dict) else None
    checkpoint = checkpoint_before_write(
        plan=plan,
        intent=f"{tool_name}:{action or ''}".strip(":"),
        inputs=args,
        expected_result=expected_result,
        approval_id=approval_id,
        pending_task=pending,
        resource_identities=[str(action)] if action else [],
    )
    if plan is not None:
        plan.terminal_status = "waiting_for_approval"
        if checkpoint.plan_id and plan.plan_id != checkpoint.plan_id:
            checkpoint = DurableCheckpoint(
                checkpoint_id=checkpoint.checkpoint_id,
                plan_id=plan.plan_id,
                phase=checkpoint.phase,
                intent=checkpoint.intent,
                approval_id=checkpoint.approval_id,
                inputs=checkpoint.inputs,
                expected_result=checkpoint.expected_result,
                context_refs=checkpoint.context_refs,
                resource_identities=checkpoint.resource_identities,
                artifact_refs=checkpoint.artifact_refs,
                created_at=checkpoint.created_at,
            )
        task_state["execution_plan"] = plan.as_dict()
    task_state[CHECKPOINT_KEY] = checkpoint.as_dict()
    task_state[SESSION_KEY] = {
        "phase": "WAITING_APPROVAL",
        "plan_id": checkpoint.plan_id,
        "updated_at": _now_iso(),
        "runtime": "e5_execution_plan",
    }
    return checkpoint


def persist_write_approval_patch(
    task_state: dict[str, Any] | None,
    *,
    pending_task: dict[str, Any],
    tool_name: str,
    action: str | None = None,
    args: dict[str, Any] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Stamp WRITE checkpoint onto a conversation task_state patch (unified + ReAct)."""
    live = dict(task_state or {})
    live["pending_task"] = pending_task
    pending_params = pending_task.get("params") if isinstance(pending_task.get("params"), dict) else {}
    resolved_args = args if isinstance(args, dict) else safe_normalize_stored_dict(
        pending_params.get("args")
    )
    attach_write_checkpoint(
        live,
        tool_name=tool_name,
        action=action or str(pending_params.get("invoke_action") or "") or None,
        args=resolved_args if isinstance(resolved_args, dict) else {},
    )
    patch: dict[str, Any] = {"pending_task": pending_task}
    if extra:
        patch.update(extra)
    for key in (CHECKPOINT_KEY, SESSION_KEY, "execution_plan"):
        if live.get(key) is not None:
            patch[key] = live[key]
    return patch


def load_checkpoint(task_state: dict[str, Any] | None) -> DurableCheckpoint | None:
    state = task_state if isinstance(task_state, dict) else {}
    return DurableCheckpoint.from_dict(safe_normalize_stored_dict(state.get(CHECKPOINT_KEY)))


def resume_from_checkpoint(
    task_state: dict[str, Any],
    *,
    continue_work: bool = True,
) -> ExecutionPlan | None:
    """Crash/interrupt resume: same plan_id, continue or leave WAITING_*."""
    checkpoint = load_checkpoint(task_state)
    plan = ExecutionPlan.from_dict(task_state.get("execution_plan"))
    if checkpoint is None and plan is None:
        return None
    plan_id = checkpoint.plan_id if checkpoint else (plan.plan_id if plan else "")
    if plan is None:
        plan = ExecutionPlan(
            plan_id=plan_id,
            summary=checkpoint.intent if checkpoint else "",
            steps=[],
            source="durable_checkpoint",
            terminal_status="waiting_for_approval",
        )
    if plan.plan_id != plan_id:
        plan.plan_id = plan_id
    plan.continuation_of_plan_id = plan.plan_id
    if continue_work:
        pending = task_state.get("pending_task") if isinstance(task_state.get("pending_task"), dict) else {}
        still_waiting = str(pending.get("status") or "").strip().lower() in {
            "awaiting_confirm",
            "awaiting_user_confirmation",
            "awaiting_approval",
        }
        plan.terminal_status = "waiting_for_approval" if still_waiting else "running"
        phase: SessionPhase = "WAITING_APPROVAL" if still_waiting else "WORKING"
    else:
        plan.terminal_status = plan_terminal_from_phase(checkpoint.phase if checkpoint else "WAITING_APPROVAL")
        phase = checkpoint.phase if checkpoint else "WAITING_APPROVAL"
    task_state["execution_plan"] = plan.as_dict()
    task_state[SESSION_KEY] = {
        "phase": phase,
        "plan_id": plan.plan_id,
        "updated_at": _now_iso(),
        "runtime": "e5_execution_plan",
        "resumed_from": checkpoint.checkpoint_id if checkpoint else None,
    }
    return plan


def stop_reason(
    *,
    success: bool = False,
    failed: bool = False,
    iterations_used: int = 0,
    iteration_budget: int | None = None,
    tools_used: int = 0,
    tool_budget: int | None = None,
    elapsed_ms: int | None = None,
    time_budget_ms: int | None = None,
    escalate: bool = False,
) -> str | None:
    if success:
        return "success"
    if failed:
        return "failure"
    if escalate:
        return "escalation"
    if iteration_budget is not None and iterations_used >= iteration_budget:
        return "iteration_budget"
    if tool_budget is not None and tools_used >= tool_budget:
        return "tool_budget"
    if time_budget_ms is not None and elapsed_ms is not None and elapsed_ms >= time_budget_ms:
        return "time_budget"
    return None


def verify_before_complete(
    *,
    plan: ExecutionPlan,
    observations: list[dict[str, Any]] | None = None,
    deliverable: DeliverableContract | None = None,
    write_verified: bool | None = None,
    blockers: list[str] | None = None,
) -> tuple[bool, str]:
    """COMPLETE only after sections/evidence/tool success/write verification."""
    if blockers:
        return False, "blockers_present"
    obs = observations or []
    if plan.steps:
        write_steps = [s for s in plan.steps if s.kind == "write"]
        if write_steps and write_verified is False:
            return False, "write_unverified"
        if obs and not any(bool(row.get("success")) for row in obs if isinstance(row, dict)):
            return False, "no_successful_observation"
    if deliverable is not None and deliverable.required:
        if not str(deliverable.diagnosis or "").strip():
            return False, "deliverable_diagnosis_missing"
        if not deliverable.evidence:
            return False, "deliverable_evidence_missing"
    return True, "ok"


def apply_session_complete(
    task_state: dict[str, Any],
    *,
    observations: list[dict[str, Any]] | None = None,
    write_verified: bool | None = None,
    blockers: list[str] | None = None,
) -> SessionPhase:
    plan = ExecutionPlan.from_dict(task_state.get("execution_plan"))
    if plan is None:
        task_state[SESSION_KEY] = {"phase": "FAILED", "runtime": "e5_execution_plan"}
        return "FAILED"
    deliverable = DeliverableContract.from_dict(
        safe_normalize_stored_dict(task_state.get(DELIVERABLE_KEY))
    )
    ok, reason = verify_before_complete(
        plan=plan,
        observations=observations,
        deliverable=deliverable if deliverable.required else None,
        write_verified=write_verified,
        blockers=blockers,
    )
    if not ok:
        phase: SessionPhase = "PARTIAL" if reason == "blockers_present" else "VERIFYING"
        plan.terminal_status = "partial" if phase == "PARTIAL" else "running"
        task_state["execution_plan"] = plan.as_dict()
        task_state[SESSION_KEY] = {
            "phase": phase,
            "plan_id": plan.plan_id,
            "verify_reason": reason,
            "runtime": "e5_execution_plan",
        }
        return phase
    plan.terminal_status = "completed"
    task_state["execution_plan"] = plan.as_dict()
    task_state[SESSION_KEY] = {
        "phase": "COMPLETED",
        "plan_id": plan.plan_id,
        "runtime": "e5_execution_plan",
    }
    return "COMPLETED"
