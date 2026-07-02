"""Multi-turn task planning with persistent conversation state."""
from __future__ import annotations

from typing import Any

from app.config import Settings, get_settings
from app.services.conversation_state_service import get_conversation_state_service
from app.services.decision_intelligence_service import get_decision_intelligence_service


class ReasoningPlannerService:
    """
    Multi-turn task planning — advisory only, never auto-executes.
    Extends DecisionIntelligenceService.scaffold_decision_plan().
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._state = get_conversation_state_service(self.settings)
        self._decision = get_decision_intelligence_service(self.settings)

    async def create_plan(
        self,
        org_id: str,
        user_id: str,
        conversation_id: str,
        goal: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        _ = user_id
        raw_plan = await self._decision.scaffold_decision_plan(org_id, goal)
        structured_plan = self._structure_plan(raw_plan, context)
        await self._state.update_task_state(
            conversation_id,
            org_id,
            {
                "current_plan": structured_plan,
                "pending_steps": structured_plan.get("steps") or [],
                "completed_steps": [],
            },
        )
        structured_plan["requires_confirmation"] = True
        structured_plan["advisory_only"] = True
        return structured_plan

    async def advance_plan(
        self,
        conversation_id: str,
        org_id: str,
        completed_step_id: str,
    ) -> dict[str, Any]:
        state = await self._state.get_task_state(conversation_id, org_id)
        plan = state.get("current_plan") or {}
        steps = list(plan.get("steps") or [])
        completed = list(state.get("completed_steps") or [])
        pending = list(state.get("pending_steps") or [])

        step = next((s for s in steps if s.get("step_id") == completed_step_id), None)
        if not step:
            return {"status": "error", "message": f"Unknown step {completed_step_id}"}

        if step.get("dependencies"):
            missing = [
                dep
                for dep in step["dependencies"]
                if dep not in {s.get("step_id") for s in completed}
            ]
            if missing:
                return {
                    "status": "blocked",
                    "message": f"Complete dependencies first: {', '.join(missing)}",
                    "missing_dependencies": missing,
                }

        if completed_step_id not in completed:
            completed.append(step)
        pending = [s for s in pending if s.get("step_id") != completed_step_id]
        next_step = pending[0] if pending else None

        await self._state.update_task_state(
            conversation_id,
            org_id,
            {"completed_steps": completed, "pending_steps": pending},
        )
        return {
            "status": "ok",
            "completed_step": step,
            "next_step": next_step,
            "remaining": len(pending),
        }

    async def revise_plan(
        self,
        conversation_id: str,
        org_id: str,
        revision_reason: str,
        goal: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        state = await self._state.get_task_state(conversation_id, org_id)
        completed_ids = {s.get("step_id") for s in (state.get("completed_steps") or [])}
        raw_plan = await self._decision.scaffold_decision_plan(org_id, goal)
        revised = self._structure_plan(raw_plan, context)
        revised_steps = [
            step
            for step in revised.get("steps") or []
            if step.get("step_id") not in completed_ids
        ]
        revised["steps"] = list(state.get("completed_steps") or []) + revised_steps
        revised["revision_reason"] = revision_reason
        await self._state.update_task_state(
            conversation_id,
            org_id,
            {
                "current_plan": revised,
                "pending_steps": revised_steps,
            },
        )
        return revised

    def _structure_plan(self, raw_plan: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        _ = context
        raw_steps = raw_plan.get("planSteps") or raw_plan.get("steps") or []
        steps = []
        for idx, description in enumerate(raw_steps):
            step_id = f"step_{idx + 1}"
            steps.append(
                {
                    "step_id": step_id,
                    "description": str(description),
                    "dependencies": [f"step_{idx}"] if idx > 0 else [],
                    "requires_approval": idx >= 2,
                    "estimated_complexity": "medium" if idx > 0 else "low",
                    "connector_requirements": [],
                }
            )
        return {
            "goal": raw_plan.get("goal"),
            "status": raw_plan.get("status") or "draft",
            "requires_human_review": bool(raw_plan.get("requiresHumanReview", True)),
            "steps": steps,
        }


_reasoning_planner_service: ReasoningPlannerService | None = None


def get_reasoning_planner_service(settings: Settings | None = None) -> ReasoningPlannerService:
    global _reasoning_planner_service
    if _reasoning_planner_service is None or settings is not None:
        _reasoning_planner_service = ReasoningPlannerService(settings)
    return _reasoning_planner_service
