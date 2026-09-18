"""Phase C/E5 — typed ExecutionPlan SoT reconciled across planner, ReAct, orchestration."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal
from uuid import uuid4

from app.services.conversational_execution_service import CONFIRM_PATTERN

StepKind = Literal[
    "read",
    "write",
    "clarify",
    "compose",
    "workflow",
    "agent_delegation",
    "hypothesis",
    "evidence",
]
StepStatus = Literal["pending", "running", "completed", "failed", "skipped"]
PlanTerminal = Literal[
    "pending",
    "running",
    "completed",
    "failed",
    "blocked",
    "cancelled",
    "clarification_required",
    "partial",
    "waiting_for_approval",
]


@dataclass(frozen=True)
class ExecutionStep:
    step_id: str
    title: str
    kind: StepKind
    connector_id: str | None = None
    capability_id: str | None = None
    action_key: str | None = None
    status: StepStatus = "pending"
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionObservation:
    step_id: str
    connector_id: str
    success: bool
    summary: str
    structured: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    observation_id: str | None = None
    plan_id: str | None = None
    source: str | None = None
    capability_id: str | None = None
    resource: str | None = None
    latency_ms: int | None = None
    started_at: str | None = None
    completed_at: str | None = None

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "step_id": self.step_id,
            "connector_id": self.connector_id,
            "success": self.success,
            "summary": self.summary,
            "structured": dict(self.structured),
            "error": self.error,
        }
        if self.observation_id:
            payload["observation_id"] = self.observation_id
        if self.plan_id:
            payload["plan_id"] = self.plan_id
        if self.source:
            payload["source"] = self.source
        if self.capability_id:
            payload["capability_id"] = self.capability_id
        if self.resource:
            payload["resource"] = self.resource
        if self.latency_ms is not None:
            payload["latency_ms"] = self.latency_ms
        if self.started_at:
            payload["started_at"] = self.started_at
        if self.completed_at:
            payload["completed_at"] = self.completed_at
        return payload


@dataclass
class ExecutionPlan:
    plan_id: str
    summary: str
    steps: list[ExecutionStep]
    source: str
    capability_id: str | None = None
    terminal_status: PlanTerminal = "pending"
    replan_budget: int = 1
    replans_used: int = 0
    turn_id: str | None = None
    conversation_id: str | None = None
    objective: str | None = None
    revision: int = 1
    parent_plan_id: str | None = None
    parent_step_id: str | None = None
    continuation_of_plan_id: str | None = None
    pending_action_id: str | None = None
    execution_strategy: str | None = None
    replan_reason: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "summary": self.summary,
            "objective": self.objective or self.summary,
            "source": self.source,
            "capability_id": self.capability_id,
            "terminal_status": self.terminal_status,
            "replan_budget": self.replan_budget,
            "replans_used": self.replans_used,
            "turn_id": self.turn_id,
            "conversation_id": self.conversation_id,
            "revision": self.revision,
            "parent_plan_id": self.parent_plan_id,
            "parent_step_id": self.parent_step_id,
            "continuation_of_plan_id": self.continuation_of_plan_id,
            "pending_action_id": self.pending_action_id,
            "execution_strategy": self.execution_strategy,
            "replan_reason": self.replan_reason,
            "steps": [
                {
                    "step_id": s.step_id,
                    "title": s.title,
                    "kind": s.kind,
                    "connector_id": s.connector_id,
                    "capability_id": s.capability_id,
                    "action_key": s.action_key,
                    "status": s.status,
                    "meta": dict(s.meta),
                }
                for s in self.steps
            ],
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> ExecutionPlan | None:
        if not isinstance(raw, dict):
            return None
        steps_raw = raw.get("steps")
        if not isinstance(steps_raw, list):
            return None
        steps: list[ExecutionStep] = []
        for row in steps_raw:
            if not isinstance(row, dict):
                continue
            steps.append(
                ExecutionStep(
                    step_id=str(row.get("step_id") or uuid4()),
                    title=str(row.get("title") or ""),
                    kind=row.get("kind") or "read",
                    connector_id=row.get("connector_id"),
                    capability_id=row.get("capability_id"),
                    action_key=row.get("action_key"),
                    status=row.get("status") or "pending",
                    meta=dict(row.get("meta") or {}),
                )
            )
        return cls(
            plan_id=str(raw.get("plan_id") or uuid4()),
            summary=str(raw.get("summary") or raw.get("objective") or ""),
            steps=steps,
            source=str(raw.get("source") or "task_state"),
            capability_id=raw.get("capability_id"),
            terminal_status=raw.get("terminal_status") or "pending",
            replan_budget=int(raw.get("replan_budget") or 1),
            replans_used=int(raw.get("replans_used") or 0),
            turn_id=raw.get("turn_id"),
            conversation_id=raw.get("conversation_id"),
            objective=raw.get("objective"),
            revision=int(raw.get("revision") or 1),
            parent_plan_id=raw.get("parent_plan_id"),
            parent_step_id=raw.get("parent_step_id"),
            continuation_of_plan_id=raw.get("continuation_of_plan_id"),
            pending_action_id=raw.get("pending_action_id"),
            execution_strategy=raw.get("execution_strategy"),
            replan_reason=raw.get("replan_reason"),
        )


def _steps_from_current_plan(current_plan: dict[str, Any]) -> list[ExecutionStep]:
    steps: list[ExecutionStep] = []
    for idx, row in enumerate(current_plan.get("steps") or []):
        if not isinstance(row, dict):
            continue
        steps.append(
            ExecutionStep(
                step_id=str(row.get("step_id") or f"plan_{idx}"),
                title=str(row.get("title") or row.get("description") or f"Step {idx + 1}"),
                kind="read" if "confirm" not in str(row.get("title") or "").lower() else "clarify",
                status=str(row.get("status") or "pending"),  # type: ignore[arg-type]
                meta={"legacy_plan": True},
            )
        )
    return steps


def _steps_from_pending_task(pending: dict[str, Any]) -> list[ExecutionStep]:
    action = str(pending.get("action") or pending.get("tool") or "pending_action")
    return [
        ExecutionStep(
            step_id="pending_primary",
            title=action,
            kind="write" if pending.get("requires_approval") else "read",
            connector_id=str(pending.get("connector_id") or "") or None,
            action_key=action,
            status="pending",
            meta={"pending_status": pending.get("status")},
        )
    ]


def _is_confirm_utterance(message: str) -> bool:
    text = (message or "").strip()
    if not text:
        return False
    return bool(CONFIRM_PATTERN.match(text) or text.lower() in {"yes", "y", "ok", "okay", "confirm"})


def _plan_id_from_state(state: dict[str, Any]) -> str | None:
    existing = ExecutionPlan.from_dict(state.get("execution_plan"))
    if existing is not None:
        return existing.plan_id
    offered = state.get("offered_action")
    if isinstance(offered, dict) and offered.get("execution_plan_id"):
        return str(offered["execution_plan_id"])
    pending_action = state.get("pending_action")
    if isinstance(pending_action, dict) and pending_action.get("plan_id"):
        return str(pending_action["plan_id"])
    pending = state.get("pending_task")
    if isinstance(pending, dict) and pending.get("execution_plan_id"):
        return str(pending["execution_plan_id"])
    current_plan = state.get("current_plan")
    if isinstance(current_plan, dict) and current_plan.get("execution_plan_id"):
        return str(current_plan["execution_plan_id"])
    return None


def continue_execution_plan(
    plan: ExecutionPlan,
    *,
    message: str | None = None,
    turn_id: str | None = None,
    follow_up: bool = False,
) -> ExecutionPlan:
    """Mark plan continuation without minting a new plan_id."""
    plan.continuation_of_plan_id = plan.plan_id
    if follow_up:
        plan.revision = int(plan.revision or 1) + 1
        plan.replan_reason = "follow_up"
        plan.terminal_status = "pending"
        if message:
            plan.summary = str(message)[:240]
    else:
        plan.terminal_status = "running"
        if message:
            plan.summary = plan.summary or message[:240]
    if turn_id:
        plan.turn_id = turn_id
    return plan


def replan_execution_plan(
    plan: ExecutionPlan,
    *,
    new_steps: list[ExecutionStep],
    reason: str,
    evidence: dict[str, Any] | None = None,
) -> ExecutionPlan:
    """Explicit replan — same logical plan_id, revision increment, lineage preserved."""
    return ExecutionPlan(
        plan_id=plan.plan_id,
        summary=plan.summary,
        objective=plan.objective or plan.summary,
        steps=new_steps,
        source=f"replan:{plan.source}",
        capability_id=plan.capability_id,
        terminal_status="pending",
        replan_budget=plan.replan_budget,
        replans_used=plan.replans_used + 1,
        turn_id=plan.turn_id,
        conversation_id=plan.conversation_id,
        revision=int(plan.revision) + 1,
        parent_plan_id=plan.parent_plan_id or plan.plan_id,
        parent_step_id=plan.parent_step_id,
        continuation_of_plan_id=plan.plan_id,
        execution_strategy=plan.execution_strategy,
        replan_reason=reason,
    )


def reconcile_execution_plan(
    *,
    message: str,
    task_state: dict[str, Any] | None,
    capability_id: str | None = None,
    connected_integrations: list[str] | None = None,
    turn_id: str | None = None,
    conversation_id: str | None = None,
) -> ExecutionPlan:
    """Single plan SoT — prefer durable task_state, then capability cross-source plans."""
    state = task_state if isinstance(task_state, dict) else {}
    text = (message or "").strip()

    existing = ExecutionPlan.from_dict(state.get("execution_plan"))
    from app.services.task_continuity import decide_task_continuity, is_restart_utterance

    if existing is not None and existing.steps:
        restart = is_restart_utterance(text, state)
        if existing.terminal_status in {"pending", "running", "waiting_for_approval"} and not restart:
            if turn_id:
                existing.turn_id = turn_id
            if conversation_id:
                existing.conversation_id = conversation_id
            if _is_confirm_utterance(text):
                return continue_execution_plan(existing, message=text, turn_id=turn_id)
            return existing
        if existing.terminal_status in {"completed", "partial", "blocked"} and not restart:
            if decide_task_continuity(text, state) == "continue":
                if conversation_id:
                    existing.conversation_id = conversation_id
                return continue_execution_plan(
                    existing,
                    message=text,
                    turn_id=turn_id,
                    follow_up=True,
                )

    offered = state.get("offered_action")
    if isinstance(offered, dict) and offered.get("execution_plan_id"):
        from app.services.execution_plan_adapters import execution_plan_from_offered_action

        plan = execution_plan_from_offered_action(
            offered,
            plan_id=str(offered["execution_plan_id"]),
        )
        if turn_id:
            plan.turn_id = turn_id
        if conversation_id:
            plan.conversation_id = conversation_id
        plan.pending_action_id = offered.get("pending_action_id")
        if _is_confirm_utterance(text):
            return continue_execution_plan(plan, message=text, turn_id=turn_id)
        return plan

    if isinstance(offered, dict) and offered.get("status") in {
        "awaiting_user_confirmation",
        "awaiting_confirm",
        "confirmed",
        "executing",
    }:
        from app.services.execution_plan_adapters import execution_plan_from_offered_action

        plan_id = str(offered.get("execution_plan_id") or _plan_id_from_state(state) or uuid4())
        plan = execution_plan_from_offered_action(offered, plan_id=plan_id)
        if turn_id:
            plan.turn_id = turn_id
        if conversation_id:
            plan.conversation_id = conversation_id
        if _is_confirm_utterance(text):
            return continue_execution_plan(plan, message=text, turn_id=turn_id)
        return plan

    pending_action = state.get("pending_action")
    if isinstance(pending_action, dict) and pending_action.get("plan_id"):
        linked = ExecutionPlan.from_dict(state.get("execution_plan"))
        if linked is not None and linked.plan_id == str(pending_action["plan_id"]):
            if _is_confirm_utterance(text):
                return continue_execution_plan(linked, message=text, turn_id=turn_id)
            return linked

    pending = state.get("pending_task")
    if isinstance(pending, dict) and pending.get("status") not in {
        None,
        "completed",
        "failed",
        "cancelled",
    }:
        linked_id = str(pending.get("execution_plan_id") or "")
        if existing is not None and linked_id and existing.plan_id == linked_id:
            if _is_confirm_utterance(text):
                return continue_execution_plan(existing, message=text, turn_id=turn_id)
            return existing
        from app.services.execution_plan_authority import is_legacy_ingress_only

        if is_legacy_ingress_only(pending, canonical=existing):
            from app.services.execution_plan_adapters import bridge_pending_task_with_plan

            plan, _pa, _proj = bridge_pending_task_with_plan(pending, existing_plan=existing)
            if turn_id:
                plan.turn_id = turn_id
            if conversation_id:
                plan.conversation_id = conversation_id
            if _is_confirm_utterance(text):
                return continue_execution_plan(plan, message=text, turn_id=turn_id)
            return plan
        if existing is not None:
            if _is_confirm_utterance(text):
                return continue_execution_plan(existing, message=text, turn_id=turn_id)
            return existing

    current_plan = state.get("current_plan")
    from app.services.execution_plan_authority import strategic_plan_only

    if (
        isinstance(current_plan, dict)
        and (current_plan.get("steps") or current_plan.get("summary"))
        and not strategic_plan_only(current_plan)
    ):
        plan_id = str(current_plan.get("execution_plan_id") or _plan_id_from_state(state) or uuid4())
        return ExecutionPlan(
            plan_id=plan_id,
            summary=str(current_plan.get("summary") or current_plan.get("goal") or text[:240]),
            objective=str(current_plan.get("summary") or current_plan.get("goal") or text[:240]),
            steps=_steps_from_current_plan(current_plan),
            source=str(current_plan.get("source") or "current_plan"),
            capability_id=capability_id,
            turn_id=turn_id,
            conversation_id=conversation_id,
        )

    from app.services.cognitive_execution_replanner import build_cross_source_analytics_plan
    from app.services.multi_source_diagnostic import build_multi_source_diagnostic_plan

    diagnostic = build_multi_source_diagnostic_plan(
        message,
        connected_integrations=connected_integrations,
        turn_id=turn_id,
        conversation_id=conversation_id,
    )
    if diagnostic is not None:
        return diagnostic

    cross = build_cross_source_analytics_plan(
        message,
        capability_id=capability_id,
        connected_integrations=connected_integrations,
    )
    if cross is not None:
        if turn_id:
            cross.turn_id = turn_id
        if conversation_id:
            cross.conversation_id = conversation_id
        cross.execution_strategy = "PARALLEL"
        return cross

    return ExecutionPlan(
        plan_id=str(uuid4()),
        summary=text[:240] if text else "Respond to user",
        objective=text[:240] if text else "Respond to user",
        steps=[
            ExecutionStep(
                step_id="compose",
                title="Compose answer",
                kind="compose",
                capability_id=capability_id,
                status="pending",
            )
        ],
        source="default_compose",
        capability_id=capability_id,
        execution_strategy="ANSWER_ONLY",
        turn_id=turn_id,
        conversation_id=conversation_id,
    )


def execution_plan_patch(plan: ExecutionPlan) -> dict[str, Any]:
    return {"execution_plan": plan.as_dict()}


def observations_patch(observations: list[ExecutionObservation]) -> dict[str, Any]:
    return {"execution_observations": [o.as_dict() for o in observations]}


def mark_plan_terminal(plan: ExecutionPlan, terminal: PlanTerminal) -> ExecutionPlan:
    plan.terminal_status = terminal
    return plan


def detect_stalled_plan(
    plan: ExecutionPlan,
    *,
    pending_action: dict[str, Any] | None = None,
    has_active_execution: bool = False,
    has_scheduled_continuation: bool = False,
    has_active_workflow: bool = False,
    has_active_agent_child: bool = False,
    has_react_execution: bool = False,
) -> str | None:
    """Return STALLED / INVALID_RUNTIME_STATE when RUNNING with no live work."""
    if plan.terminal_status not in {"running", "pending"}:
        return None
    if has_active_execution or has_scheduled_continuation or has_active_workflow:
        return None
    if has_active_agent_child or has_react_execution:
        return None
    if any(s.status == "running" for s in plan.steps):
        return None
    if isinstance(pending_action, dict) and pending_action.get("status") in {
        "awaiting_user",
        "awaiting_user_confirmation",
    }:
        return None
    if plan.terminal_status == "waiting_for_approval":
        return None
    if plan.terminal_status == "running":
        return "STALLED"
    return None


def apply_observations_to_plan(
    plan: ExecutionPlan,
    observations: list[ExecutionObservation],
) -> ExecutionPlan:
    """Associate step observations and derive terminal status when possible."""
    obs_by_step = {o.step_id: o for o in observations}
    updated_steps: list[ExecutionStep] = []
    any_failed = False
    all_done = True
    for step in plan.steps:
        obs = obs_by_step.get(step.step_id)
        if obs is None:
            if step.kind not in {"compose", "hypothesis"}:
                all_done = False
            updated_steps.append(step)
            continue
        obs.plan_id = obs.plan_id or plan.plan_id
        status: StepStatus = "completed" if obs.success else "failed"
        if not obs.success:
            any_failed = True
        updated_steps.append(
            ExecutionStep(
                step_id=step.step_id,
                title=step.title,
                kind=step.kind,
                connector_id=step.connector_id,
                capability_id=step.capability_id,
                action_key=step.action_key,
                status=status,
                meta={**step.meta, "observation_summary": obs.summary},
            )
        )
    plan.steps = updated_steps
    if all_done and not any_failed:
        plan.terminal_status = "completed"
    elif any_failed and observations:
        plan.terminal_status = "partial" if any(o.success for o in observations) else "failed"
    return plan
