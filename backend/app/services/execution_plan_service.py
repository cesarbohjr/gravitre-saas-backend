"""Phase C — typed ExecutionPlan SoT reconciled across planner, ReAct, orchestration."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal
from uuid import uuid4

StepKind = Literal["read", "write", "clarify", "compose"]
StepStatus = Literal["pending", "running", "completed", "failed", "skipped"]
PlanTerminal = Literal[
    "pending",
    "completed",
    "failed",
    "blocked",
    "clarification_required",
    "partial",
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


@dataclass(frozen=True)
class ExecutionObservation:
    step_id: str
    connector_id: str
    success: bool
    summary: str
    structured: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "connector_id": self.connector_id,
            "success": self.success,
            "summary": self.summary,
            "structured": dict(self.structured),
            "error": self.error,
        }


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

    def as_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "summary": self.summary,
            "source": self.source,
            "capability_id": self.capability_id,
            "terminal_status": self.terminal_status,
            "replan_budget": self.replan_budget,
            "replans_used": self.replans_used,
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
            summary=str(raw.get("summary") or ""),
            steps=steps,
            source=str(raw.get("source") or "task_state"),
            capability_id=raw.get("capability_id"),
            terminal_status=raw.get("terminal_status") or "pending",
            replan_budget=int(raw.get("replan_budget") or 1),
            replans_used=int(raw.get("replans_used") or 0),
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


def reconcile_execution_plan(
    *,
    message: str,
    task_state: dict[str, Any] | None,
    capability_id: str | None = None,
    connected_integrations: list[str] | None = None,
) -> ExecutionPlan:
    """Single plan SoT — prefer durable task_state, then capability cross-source plans."""
    state = task_state if isinstance(task_state, dict) else {}
    existing = ExecutionPlan.from_dict(state.get("execution_plan"))
    if existing is not None and existing.terminal_status == "pending" and existing.steps:
        return existing

    pending = state.get("pending_task")
    if isinstance(pending, dict) and pending.get("status") not in {
        None,
        "completed",
        "failed",
        "cancelled",
    }:
        return ExecutionPlan(
            plan_id=str(uuid4()),
            summary=str(pending.get("action") or "Pending connector action"),
            steps=_steps_from_pending_task(pending),
            source="pending_task",
            capability_id=capability_id,
        )

    current_plan = state.get("current_plan")
    if isinstance(current_plan, dict) and (current_plan.get("steps") or current_plan.get("summary")):
        return ExecutionPlan(
            plan_id=str(uuid4()),
            summary=str(current_plan.get("summary") or message[:240]),
            steps=_steps_from_current_plan(current_plan),
            source=str(current_plan.get("source") or "current_plan"),
            capability_id=capability_id,
        )

    from app.services.cognitive_execution_replanner import build_cross_source_analytics_plan

    cross = build_cross_source_analytics_plan(
        message,
        capability_id=capability_id,
        connected_integrations=connected_integrations,
    )
    if cross is not None:
        return cross

    text = (message or "").strip()
    return ExecutionPlan(
        plan_id=str(uuid4()),
        summary=text[:240] if text else "Respond to user",
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
    )


def execution_plan_patch(plan: ExecutionPlan) -> dict[str, Any]:
    return {"execution_plan": plan.as_dict()}


def observations_patch(observations: list[ExecutionObservation]) -> dict[str, Any]:
    return {"execution_observations": [o.as_dict() for o in observations]}
