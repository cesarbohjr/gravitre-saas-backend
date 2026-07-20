"""Reflection loops — plan → execute → critique → revise coordination.

Advisory only: never re-executes writes. Surfaces revise signals for delivery
and optional planner revise_plan callers.
"""
from __future__ import annotations

from typing import Any


class ReflectionLoopService:
    """Coordinate critic + confidence into a revise/deliver decision."""

    LOW_CONFIDENCE = 0.42

    def evaluate(
        self,
        *,
        critic: dict[str, Any] | None,
        confidence: dict[str, Any] | None,
        tool_results: list[dict[str, Any]] | None = None,
        strategic_plan: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        critic = critic or {}
        confidence = confidence or {}
        raw_score = confidence.get("score")
        score = float(raw_score) if raw_score is not None else 0.55
        issues = list(critic.get("issues") or [])
        passed = bool(critic.get("passed", True))
        failed_tools = [
            row
            for row in (tool_results or [])
            if isinstance(row, dict) and row.get("success") is False
        ]

        should_revise = False
        reasons: list[str] = []
        if not passed:
            should_revise = True
            reasons.append("critic_failed")
        if score < self.LOW_CONFIDENCE:
            should_revise = True
            reasons.append("low_confidence")
        if failed_tools:
            should_revise = True
            reasons.append("tool_failures")
            issues = issues + ["tool_failure"]

        revised_answer = critic.get("revised_answer")
        actions: list[str] = []
        if "low_confidence" in reasons:
            actions.append("retrieve_more")
            actions.append("verify_again")
        if "tool_failures" in reasons:
            actions.append("self_heal_suggest")
        if "critic_failed" in reasons:
            actions.append("revise_answer")
        if strategic_plan and should_revise:
            actions.append("revise_plan")

        return {
            "phase": "critique" if should_revise else "deliver",
            "should_revise": should_revise,
            "should_deliver": not should_revise or bool(revised_answer),
            "reasons": reasons,
            "issues": issues,
            "actions": actions,
            "revised_answer": revised_answer,
            "confidence_score": score,
            "plan_id": (strategic_plan or {}).get("id") if isinstance(strategic_plan, dict) else None,
        }


_reflection_loop: ReflectionLoopService | None = None


def get_reflection_loop_service() -> ReflectionLoopService:
    global _reflection_loop
    if _reflection_loop is None:
        _reflection_loop = ReflectionLoopService()
    return _reflection_loop
