"""Generative task coordinator over ExecutionCore / handoff patterns."""
from __future__ import annotations

from typing import Any

from app.config import Settings, get_settings
from app.operators.agent_prompts import infer_task_persona_key


SUPPORTED_TASKS = frozenset(
    {
        "create_plan",
        "generate_asset",
        "draft_communication",
        "create_workflow_template",
    }
)


class GenerativeAgentCoordinator:
    """
    Routes generative tasks through PLANNER + department specialist personas.
    Outputs are returned for human review — never auto-executed as writes.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    async def execute_generative_task(
        self,
        org_id: str,
        task_type: str,
        context: dict[str, Any],
        department: str | None = None,
    ) -> dict[str, Any]:
        normalized = task_type.strip().lower()
        if normalized not in SUPPORTED_TASKS:
            return {
                "status": "unsupported_task",
                "task_type": task_type,
                "supported": sorted(SUPPORTED_TASKS),
            }
        persona_key = infer_task_persona_key(
            f"{department or ''} {context.get('goal') or context.get('prompt') or task_type}"
        )
        goal = str(context.get("goal") or context.get("prompt") or normalized)
        draft = await self._generate_review_draft(normalized, goal, department)
        return {
            "status": "ok",
            "task_type": normalized,
            "persona": persona_key,
            "department": department,
            "context": context,
            "draft": draft,
            "requiresHumanReview": True,
            "approval_required": True,
            "message": "Draft generated for human review before any write action.",
        }

    async def _generate_review_draft(
        self,
        task_type: str,
        goal: str,
        department: str | None,
    ) -> str:
        try:
            from app.services.model_router import ModelRouter, TaskType

            router = ModelRouter(self.settings)
            prompt = (
                f"Create a concise {task_type.replace('_', ' ')} draft for review only. "
                f"Department: {department or 'general'}. Goal: {goal}. "
                "Do not claim anything was executed."
            )
            response = await router.complete(
                TaskType.CONTENT_GENERATION,
                prompt,
                org_id=org_id,
            )
            text = str(getattr(response, "content", "") or "").strip()
            if text:
                return text[:4000]
        except Exception:  # noqa: BLE001
            pass
        return f"Review-ready {task_type.replace('_', ' ')} outline for: {goal[:500]}"


_generative_agent_coordinator: GenerativeAgentCoordinator | None = None


def get_generative_agent_coordinator(settings: Settings | None = None) -> GenerativeAgentCoordinator:
    global _generative_agent_coordinator
    if _generative_agent_coordinator is None or settings is not None:
        _generative_agent_coordinator = GenerativeAgentCoordinator(settings)
    return _generative_agent_coordinator
