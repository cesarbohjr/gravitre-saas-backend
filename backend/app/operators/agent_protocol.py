"""Formal agent-to-agent handoff protocol over existing handoff_service patterns."""
from __future__ import annotations

from typing import Any

from app.services.handoff_service import build_handoff_briefing


class AgentHandoffProtocol:
    """
    Standardizes agent-to-agent context passing with explicit scope and receipts.
    Wraps build_handoff_briefing — does not replace handoff_service.
    """

    def create_handoff_briefing(
        self,
        from_agent: str,
        to_agent: str,
        task_context: dict[str, Any],
        outputs_so_far: dict[str, Any],
        next_task: str,
    ) -> dict[str, Any]:
        parameters: dict[str, Any] = dict(task_context)
        if not isinstance(parameters.get("decision"), dict):
            parameters["decision"] = {
                "summary": str(task_context.get("summary") or next_task),
                "confidence": task_context.get("confidence"),
            }
        briefing = build_handoff_briefing(
            parameters=parameters,
            source_output=outputs_so_far,
        )
        return {
            "from": from_agent,
            "to": to_agent,
            "task": next_task,
            "context_provided": task_context,
            "outputs_available": outputs_so_far,
            "briefing": briefing,
            "scope_note": (
                "Use only the context provided. "
                "Do not infer additional context not explicitly included here."
            ),
        }
