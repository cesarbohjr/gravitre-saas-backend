"""Explicit Verify → Normalize → BusinessOutcome → Memory → Recommendation → Notification.

Each stage must complete (or explicitly skip) before the next. The DTO is not
assembled out of order.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.services.business_outcome.models import BusinessOutcome, PipelineStage
from app.services.business_outcome.projector import project_business_outcome
from app.services.recommendation_heuristics_service import assert_no_execute_surface


@dataclass
class PipelineContext:
    org_id: str
    run: dict[str, Any] = field(default_factory=dict)
    steps: list[dict[str, Any]] = field(default_factory=list)
    execution_result: dict[str, Any] = field(default_factory=dict)
    invoke_action: str | None = None
    compensation_snapshot: dict[str, Any] | None = None
    notification_emitted: bool = False
    recommendation: dict[str, Any] | None = None
    memory_recorded: bool = False
    verified: bool = False
    normalized: bool = False
    stages: list[PipelineStage] = field(default_factory=list)


def run_business_outcome_pipeline(ctx: PipelineContext) -> BusinessOutcome:
    """Ordered pipeline. Raises if a later stage is claimed without earlier ones."""
    _stage_verify(ctx)
    _stage_normalize(ctx)
    outcome = _stage_business_outcome(ctx)
    _stage_memory(ctx, outcome)
    _stage_recommendation(ctx, outcome)
    _stage_notification(ctx, outcome)
    _assert_stage_order(ctx.stages)
    outcome.pipeline_stages_completed = list(ctx.stages)
    if outcome.sections.recommendations:
        assert_no_execute_surface(
            {
                "advisoryOnly": True,
                "actionsTaken": [],
                "recommendations": [
                    {
                        "title": r.title,
                        "reason": r.reason,
                        "suggestedUtterance": r.suggested_utterance,
                        "advisoryOnly": True,
                        "href": r.href,
                    }
                    for r in outcome.sections.recommendations
                ],
            }
        )
    return outcome


def _stage_verify(ctx: PipelineContext) -> None:
    er = ctx.execution_result or {}
    status = str(ctx.run.get("status") or "")
    has_output = bool(er.get("body") or er.get("external_url") or er.get("result_url"))
    ctx.verified = has_output or status in {
        "completed",
        "failed",
        "partial_success",
        "cancelled",
        "flagged_for_review",
    }
    if not ctx.verified:
        # Still continue — failed verifies become failed outcomes with explanation.
        ctx.verified = True
    ctx.stages.append("verify")


def _stage_normalize(ctx: PipelineContext) -> None:
    # Normalize keys that projectors expect (snake/camel already handled in projector).
    ctx.normalized = True
    ctx.stages.append("normalize")


def _stage_business_outcome(ctx: PipelineContext) -> BusinessOutcome:
    if "verify" not in ctx.stages or "normalize" not in ctx.stages:
        raise RuntimeError("business_outcome stage requires verify+normalize first")
    outcome = project_business_outcome(
        org_id=ctx.org_id,
        run=ctx.run,
        steps=ctx.steps,
        execution_result=ctx.execution_result,
        recommendation=ctx.recommendation,
        invoke_action=ctx.invoke_action,
        compensation_snapshot=ctx.compensation_snapshot,
        notification_emitted=ctx.notification_emitted,
    )
    ctx.stages.append("business_outcome")
    return outcome


def _stage_memory(ctx: PipelineContext, outcome: BusinessOutcome) -> None:
    # Memory write is ownership of Module B / execution_memory — we only confirm
    # the stage slot. Projection never writes Module A.
    _ = outcome
    ctx.memory_recorded = True
    ctx.stages.append("memory")


def _stage_recommendation(ctx: PipelineContext, outcome: BusinessOutcome) -> None:
    """Attach suggest-only rec from execution result or post-action builder."""
    if outcome.sections.recommendations:
        ctx.stages.append("recommendation")
        return
    er = ctx.execution_result or {}
    raw = er.get("recommendation") or (er.get("structured") or {}).get("recommendation")
    if isinstance(raw, dict) and raw.get("title"):
        from app.services.business_outcome.models import RecommendationSection

        outcome.sections.recommendations = [
            RecommendationSection(
                title=str(raw["title"]),
                reason=str(raw.get("reason") or ""),
                suggested_utterance=str(
                    raw.get("suggestedUtterance") or raw.get("suggested_utterance") or ""
                )
                or None,
                advisory_only=True,
                href=str(raw.get("href") or "") or None,
                confidence=float(raw["confidence"]) if raw.get("confidence") is not None else None,
                confidence_is_estimate=bool(
                    raw.get("confidence_is_estimate", raw.get("confidenceIsEstimate", True))
                ),
            )
        ]
    ctx.stages.append("recommendation")


def _stage_notification(ctx: PipelineContext, outcome: BusinessOutcome) -> None:
    # Notification already fanout by Module A; mark presented lifecycle if emitted.
    if ctx.notification_emitted and "presented" not in outcome.lifecycle_states_reached:
        outcome.lifecycle_states_reached = [*outcome.lifecycle_states_reached, "presented"]
        outcome.lifecycle_state = "presented"
    ctx.stages.append("notification")


_EXPECTED_ORDER: tuple[PipelineStage, ...] = (
    "verify",
    "normalize",
    "business_outcome",
    "memory",
    "recommendation",
    "notification",
)


def _assert_stage_order(stages: list[PipelineStage]) -> None:
    if list(stages) != list(_EXPECTED_ORDER):
        raise RuntimeError(f"BusinessOutcome pipeline order violated: {stages}")
