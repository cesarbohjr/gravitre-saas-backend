"""Phase D — single turn_id trace across gateway → resolution → execute → compose."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from app.core.logging import get_logger

logger = get_logger(__name__)

TRACE_STAGES = (
    "gateway",
    "resolution",
    "capability_route",
    "context_compile",
    "execution",
    "react",
    "compose",
    "terminal",
)


@dataclass
class CognitiveTraceStage:
    stage: str
    duration_ms: float = 0.0
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class CognitiveTurnTrace:
    turn_id: str
    conversation_id: str | None = None
    tenant_id: str | None = None
    stages: list[CognitiveTraceStage] = field(default_factory=list)
    linked: dict[str, str] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "turn_id": self.turn_id,
            "conversation_id": self.conversation_id,
            "tenant_id": self.tenant_id,
            "linked": dict(self.linked),
            "stages": [
                {"stage": s.stage, "duration_ms": s.duration_ms, "meta": dict(s.meta)}
                for s in self.stages
            ],
        }


class CognitiveTraceBuilder:
    def __init__(
        self,
        *,
        turn_id: str | None = None,
        conversation_id: str | None = None,
        tenant_id: str | None = None,
    ) -> None:
        self.trace = CognitiveTurnTrace(
            turn_id=turn_id or str(uuid4()),
            conversation_id=conversation_id,
            tenant_id=tenant_id,
        )
        self._started: dict[str, float] = {}

    def mark(self, stage: str, **meta: Any) -> None:
        now = time.perf_counter()
        duration_ms = 0.0
        if stage in self._started:
            duration_ms = (now - self._started.pop(stage)) * 1000.0
        else:
            self._started[stage] = now
        safe_meta = {k: v for k, v in meta.items() if k not in {"token", "secret", "password"}}
        self.trace.stages.append(CognitiveTraceStage(stage=stage, duration_ms=duration_ms, meta=safe_meta))

    def link(self, key: str, turn_id: str | None) -> None:
        if turn_id:
            self.trace.linked[key] = str(turn_id)

    def finish(self) -> CognitiveTurnTrace:
        self.mark("terminal", reason="turn_complete")
        return self.trace

    def emit_log(self) -> None:
        payload = self.trace.as_dict()
        logger.info(
            "cognitive.turn.trace turn_id=%s conversation_id=%s stages=%s linked=%s",
            payload.get("turn_id"),
            payload.get("conversation_id"),
            len(payload.get("stages") or []),
            list((payload.get("linked") or {}).keys()),
        )


def unify_turn_id(task_state: dict[str, Any] | None, *, fallback: str | None = None) -> str:
    """Pick one canonical turn_id from task_state fragments."""
    state = task_state if isinstance(task_state, dict) else {}
    cognitive = state.get("cognitive_turn_trace")
    if isinstance(cognitive, dict) and cognitive.get("turn_id"):
        return str(cognitive["turn_id"])
    resolution = state.get("resolution_trace")
    if isinstance(resolution, dict) and resolution.get("turn_id"):
        return str(resolution["turn_id"])
    kernel_id = state.get("_cognitive_turn_id")
    if kernel_id:
        return str(kernel_id)
    plan = state.get("execution_plan")
    if isinstance(plan, dict) and plan.get("plan_id"):
        return str(plan["plan_id"])
    return fallback or str(uuid4())


def start_cognitive_turn_trace(
    *,
    conversation_id: str | None,
    tenant_id: str | None,
    task_state: dict[str, Any] | None = None,
) -> CognitiveTurnTrace:
    turn_id = unify_turn_id(task_state)
    builder = CognitiveTraceBuilder(
        turn_id=turn_id,
        conversation_id=conversation_id,
        tenant_id=tenant_id,
    )
    builder.mark("gateway", entry="agent_intelligence")
    resolution = (task_state or {}).get("resolution_trace")
    if isinstance(resolution, dict):
        builder.link("resolution_trace", str(resolution.get("turn_id") or turn_id))
    trace = builder.trace
    builder.emit_log()
    return trace


def sync_trace_from_task_state(
    trace: CognitiveTurnTrace,
    task_state: dict[str, Any] | None,
) -> CognitiveTurnTrace:
    """Align linked ids after resolution / execution updates."""
    state = task_state if isinstance(task_state, dict) else {}
    resolution = state.get("resolution_trace")
    if isinstance(resolution, dict):
        trace.linked["resolution_trace"] = str(resolution.get("turn_id") or trace.turn_id)
        if resolution.get("turn_id") and resolution.get("turn_id") != trace.turn_id:
            trace.turn_id = str(resolution.get("turn_id"))
    if state.get("_cognitive_turn_id"):
        trace.linked["cognitive_kernel"] = str(state["_cognitive_turn_id"])
    plan = state.get("execution_plan")
    if isinstance(plan, dict) and plan.get("plan_id"):
        trace.linked["execution_plan"] = str(plan["plan_id"])
        if plan.get("revision") is not None:
            trace.linked["plan_revision"] = str(plan["revision"])
        if plan.get("continuation_of_plan_id"):
            trace.linked["continuation_of_plan_id"] = str(plan["continuation_of_plan_id"])
        if plan.get("parent_plan_id"):
            trace.linked["parent_plan_id"] = str(plan["parent_plan_id"])
        if plan.get("terminal_status"):
            trace.linked["plan_state"] = str(plan["terminal_status"])
        if plan.get("execution_strategy"):
            trace.linked["execution_strategy"] = str(plan["execution_strategy"])
    pending_action = state.get("pending_action")
    if isinstance(pending_action, dict) and pending_action.get("pending_action_id"):
        trace.linked["pending_action_id"] = str(pending_action["pending_action_id"])
    offered = state.get("offered_action")
    if isinstance(offered, dict) and offered.get("execution_plan_id"):
        trace.linked["offered_execution_plan_id"] = str(offered["execution_plan_id"])
    compiled = state.get("compiled_task")
    if isinstance(compiled, dict):
        if compiled.get("turn_id"):
            trace.linked["compiled_task"] = str(compiled["turn_id"])
        if compiled.get("capability_id"):
            trace.linked["compiled_task_capability"] = str(compiled["capability_id"])
        if compiled.get("preflight_status"):
            trace.linked["compiled_task_preflight"] = str(compiled["preflight_status"])
    return trace


def attach_cognitive_turn_trace(task_state: dict[str, Any], trace: CognitiveTurnTrace) -> dict[str, Any]:
    merged = {**task_state, "cognitive_turn_trace": trace.as_dict(), "_cognitive_turn_id": trace.turn_id}
    resolution = merged.get("resolution_trace")
    if isinstance(resolution, dict):
        merged["resolution_trace"] = {**resolution, "turn_id": trace.turn_id}
    return merged
