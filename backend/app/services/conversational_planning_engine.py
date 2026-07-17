"""Strategic conversational planning — goals, risks, dependencies, approvals."""
from __future__ import annotations

import re
from typing import Any

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.services.chat_connector_models import LIST_CREATE_INTENT
from app.services.decision_intelligence_service import get_decision_intelligence_service
from app.services.reasoning_planner_service import get_reasoning_planner_service

logger = get_logger(__name__)

# Concrete single-action connector writes already have a governed path
# (ReAct write gate / chat connector awaiting_confirm). Advisory strategic
# scaffolding for these intents dead-ends: create_plan writes current_plan
# with "Clarify → Gather → Draft → Execute after approval" steps, ReAct never
# calls the write tool, and pending_task stays null.
_DIRECT_CONNECTOR_WRITE_INTENT = re.compile(
    r"(?:"
    r"\b(?:create|add|update|delete|remove)\s+(?:a\s+|an\s+|the\s+)?(?:hubspot\s+|salesforce\s+|apollo\s+)?"
    r"(?:contact|deal|company|ticket|issue|page|event|task|note)\b"
    r"|\b(?:send|post)\s+(?:a\s+|an\s+|the\s+)?(?:slack\s+)?(?:message|email|dm)\b"
    r"|\b(?:invite|add)\s+(?:\w+\s+){0,4}(?:to|into)\s+(?:a\s+|the\s+)?(?:channel|slack|list)\b"
    r")",
    re.I,
)

# Multi-step advisory planning — keep specific phrases; bare "plan"/"strategy"
# false-trigger concrete writes ("please plan the steps before executing").
_STRATEGIC_PLAN_PHRASES = (
    "improve",
    "increase",
    "reduce",
    "optimize",
    "strategic plan",
    "make a plan",
    "draft a plan",
    "build a plan",
    "create a plan",
    "planning roadmap",
    "how can we",
    "what should we",
    "roadmap",
    "prioritize",
)


def is_direct_connector_write_intent(query: str) -> bool:
    """True when the query is a concrete connector write, not multi-step strategy."""
    text = (query or "").strip()
    if not text:
        return False
    if LIST_CREATE_INTENT.search(text):
        return True
    return bool(_DIRECT_CONNECTOR_WRITE_INTENT.search(text))


class ConversationalPlanningEngine:
    """Structured strategic plans over ReasoningPlannerService + decision intelligence."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._planner = get_reasoning_planner_service(self.settings)
        self._decision = get_decision_intelligence_service(self.settings)

    async def should_plan(self, classification: dict[str, Any], query: str) -> bool:
        # Shape (b): do not detour governed writes into advisory scaffolding.
        if is_direct_connector_write_intent(query):
            return False
        intent = str(classification.get("intent") or "")
        if classification.get("requires_action") and intent in {"workflow_execution", "optimization"}:
            return True
        lowered = query.lower()
        return any(phrase in lowered for phrase in _STRATEGIC_PLAN_PHRASES)

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
