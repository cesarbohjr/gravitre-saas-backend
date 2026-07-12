"""Wave 4 — thin complexity classifier for assistant model routing.

Maps turn heuristics to TaskType so ModelRouter / MODEL_TIERS pick an
appropriate tier without a separate engine.

Routing wave (2026-07-12): delegates to assistant_routing_tier for named
product tiers (simple / multi_step / research) while preserving TaskType API.
"""
from __future__ import annotations

from typing import Any

from app.services.model_router import TaskType


def classify_assistant_turn_complexity(
    message: str,
    *,
    mode: str | None = None,
    connected_integrations: list[str] | None = None,
    parameters: dict[str, Any] | None = None,
) -> TaskType:
    """Heuristic TaskType for assistant chat turns (compat wrapper)."""
    from app.services.assistant_routing_tier import classify_routing_tier

    decision = classify_routing_tier(
        message,
        mode=mode,
        connected_integrations=connected_integrations,
        parameters=parameters,
    )
    return decision.task_type


def model_tier_for_task_type(task_type: TaskType) -> str:
    """Map TaskType → MODEL_TIERS key (low/medium/high)."""
    from app.config import TASK_COMPLEXITY

    return TASK_COMPLEXITY.get(task_type.value, "medium")
