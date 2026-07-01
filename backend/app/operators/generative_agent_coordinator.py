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
        return {
            "status": "ok",
            "task_type": normalized,
            "persona": persona_key,
            "department": department,
            "context": context,
            "requiresHumanReview": True,
            "message": "Generative scaffold returned for review; use ExecutionCore/handoff to execute.",
        }


_generative_agent_coordinator: GenerativeAgentCoordinator | None = None


def get_generative_agent_coordinator(settings: Settings | None = None) -> GenerativeAgentCoordinator:
    global _generative_agent_coordinator
    if _generative_agent_coordinator is None or settings is not None:
        _generative_agent_coordinator = GenerativeAgentCoordinator(settings)
    return _generative_agent_coordinator
