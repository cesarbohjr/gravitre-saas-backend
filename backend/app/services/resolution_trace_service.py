"""Canonical per-turn resolution trace (Phase A instrumentation)."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from app.core.logging import get_logger

logger = get_logger(__name__)

RESOLUTION_STAGES = (
    "turn_received",
    "semantic_resolution_start",
    "semantic_resolution_complete",
    "connector_resolved",
    "resource_resolution_start",
    "resource_resolution_complete",
    "reference_resolution",
    "clarification_decision",
    "resolution_terminal",
)


@dataclass
class ResolutionStageRecord:
    stage: str
    duration_ms: float = 0.0
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class ResolutionTrace:
    turn_id: str
    conversation_id: str | None = None
    tenant_id: str | None = None
    stages: list[ResolutionStageRecord] = field(default_factory=list)
    resolved_connector_id: str | None = None
    resource_id: str | None = None
    candidate_count: int | None = None
    clarification_required: bool | None = None
    resolution_reason: str | None = None
    reference_kind: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "turn_id": self.turn_id,
            "conversation_id": self.conversation_id,
            "tenant_id": self.tenant_id,
            "resolved_connector_id": self.resolved_connector_id,
            "resource_id": self.resource_id,
            "candidate_count": self.candidate_count,
            "clarification_required": self.clarification_required,
            "resolution_reason": self.resolution_reason,
            "reference_kind": self.reference_kind,
            "stages": [
                {"stage": record.stage, "duration_ms": record.duration_ms, "meta": record.meta}
                for record in self.stages
            ],
        }


class ResolutionTraceBuilder:
    def __init__(
        self,
        *,
        conversation_id: str | None = None,
        tenant_id: str | None = None,
        turn_id: str | None = None,
    ) -> None:
        self.trace = ResolutionTrace(
            turn_id=turn_id or str(uuid4()),
            conversation_id=conversation_id,
            tenant_id=tenant_id,
        )
        self._stage_started: dict[str, float] = {}

    def mark(self, stage: str, **meta: Any) -> None:
        now = time.perf_counter()
        duration_ms = 0.0
        if stage.endswith("_complete") or stage in {"connector_resolved", "reference_resolution", "clarification_decision", "resolution_terminal"}:
            start_key = stage.replace("_complete", "_start")
            if start_key in self._stage_started:
                duration_ms = (now - self._stage_started[start_key]) * 1000.0
        else:
            self._stage_started[stage] = now
        safe_meta = {key: value for key, value in meta.items() if key not in {"resource_id", "token", "secret"}}
        self.trace.stages.append(ResolutionStageRecord(stage=stage, duration_ms=duration_ms, meta=safe_meta))

    def set_connector(self, connector_id: str | None) -> None:
        self.trace.resolved_connector_id = connector_id
        self.mark("connector_resolved", connector_id=connector_id)

    def set_resource(self, *, resource_id: str | None, candidate_count: int | None, reason: str | None) -> None:
        self.trace.resource_id = resource_id
        self.trace.candidate_count = candidate_count
        self.trace.resolution_reason = reason
        self.mark(
            "resource_resolution_complete",
            candidate_count=candidate_count,
            resolution_reason=reason,
        )

    def set_clarification(self, required: bool, reason: str | None = None) -> None:
        self.trace.clarification_required = required
        self.mark("clarification_decision", clarification_required=required, reason=reason)

    def set_reference(self, kind: str | None, matched: bool) -> None:
        self.trace.reference_kind = kind
        self.mark("reference_resolution", kind=kind, matched=matched)

    def finish(self, *, terminal_reason: str = "complete") -> ResolutionTrace:
        self.mark("resolution_terminal", reason=terminal_reason)
        return self.trace

    def emit_log(self) -> None:
        payload = self.trace.as_dict()
        logger.info(
            "cognitive.resolution.trace turn_id=%s conversation_id=%s tenant_id=%s connector=%s clarification=%s stages=%s",
            payload.get("turn_id"),
            payload.get("conversation_id"),
            payload.get("tenant_id"),
            payload.get("resolved_connector_id"),
            payload.get("clarification_required"),
            len(payload.get("stages") or []),
        )


def attach_resolution_trace(task_state: dict[str, Any], trace: ResolutionTrace) -> dict[str, Any]:
    return {**task_state, "resolution_trace": trace.as_dict()}
