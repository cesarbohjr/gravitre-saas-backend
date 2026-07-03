"""Strategic conversational planning — goals, risks, dependencies, approvals."""
from __future__ import annotations

from typing import Any

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.services.decision_intelligence_service import get_decision_intelligence_service
from app.services.reasoning_planner_service import get_reasoning_planner_service

logger = get_logger(__name__)


class ConversationalPlanningEngine:
    """Structured strategic plans over ReasoningPlannerService + decision intelligence."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._planner = get_reasoning_planner_service(self.settings)
        self._decision = get_decision_intelligence_service(self.settings)

    async def should_plan(self, classification: dict[str, Any], query: str) -> bool:
        intent = str(classification.get("intent") or "")
        if classification.get("requires_action") and intent in {"workflow_execution", "optimization"}:
            return True
        lowered = query.lower()
        return any(
            phrase in lowered
            for phrase in (
                "improve",
                "increase",
                "reduce",
                "optimize",
                "strategy",
                "plan",
                "how can we",
                "what should we",
                "roadmap",
                "prioritize",
            )
        )

    async def create_plan(
        self,
        org_id: str,
        user_id: str,
        conversation_id: str,
        goal: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        plan = await self._planner.create_plan(org_id, user_id, conversation_id, goal, context)
        risks_payload = await self._decision.recommend_next_action(org_id, goal)
        recommendations = risks_payload.get("recommendations") or []
        plan["risks"] = [
            {
                "title": row.get("title") or row.get("action"),
                "summary": row.get("rationale") or row.get("description"),
                "severity": row.get("estimated_impact") or "medium",
                "confidence": row.get("confidence"),
            }
            for row in recommendations
        ]
        plan["dependencies"] = self._extract_dependencies(plan.get("steps") or [])
        plan["approvals_required"] = [
            step.get("step_id")
            for step in (plan.get("steps") or [])
            if step.get("requires_approval") or step.get("risk_level") in {"high", "critical"}
        ]
        plan["expected_outcomes"] = [
            row.get("estimated_impact")
            for row in recommendations
            if row.get("estimated_impact")
        ]
        plan["confidence"] = (
            round(sum(float(row.get("confidence") or 0.55) for row in recommendations) / len(recommendations), 4)
            if recommendations
            else float(plan.get("confidence") or 0.6)
        )
        plan["goal"] = goal
        return plan

    def format_plan_section(self, plan: dict[str, Any]) -> str:
        if not plan:
            return ""
        lines = [f"Goal: {plan.get('goal') or plan.get('title') or 'Strategic plan'}"]
        steps = plan.get("steps") or []
        if steps:
            lines.append("Steps:")
            for step in steps[:8]:
                lines.append(
                    f"- {step.get('step_id') or step.get('title')}: {step.get('description') or step.get('action') or ''}"
                )
        risks = plan.get("risks") or []
        if risks:
            lines.append("Risks:")
            for risk in risks[:5]:
                lines.append(f"- {risk.get('title')}: {risk.get('summary') or risk.get('severity')}")
        if plan.get("approvals_required"):
            lines.append(f"Approvals required: {', '.join(plan['approvals_required'])}")
        if plan.get("confidence") is not None:
            lines.append(f"Plan confidence: {plan['confidence']}")
        return "\n".join(lines)

    @staticmethod
    def _extract_dependencies(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
        deps: list[dict[str, Any]] = []
        for step in steps:
            step_deps = step.get("dependencies") or []
            if step_deps:
                deps.append({"step_id": step.get("step_id"), "depends_on": step_deps})
        return deps


_engine: ConversationalPlanningEngine | None = None


def get_conversational_planning_engine(settings: Settings | None = None) -> ConversationalPlanningEngine:
    global _engine
    if _engine is None or settings is not None:
        _engine = ConversationalPlanningEngine(settings)
    return _engine
