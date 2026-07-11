"""Wave 4 — thin complexity classifier for assistant model routing.

Maps turn heuristics to TaskType so ModelRouter / MODEL_TIERS pick an
appropriate tier without a separate engine.
"""
from __future__ import annotations

import re
from typing import Any

from app.services.model_router import TaskType

_CONNECTOR_HINT = re.compile(
    r"\b(create|update|delete|send|post|list|search|sync|connect|apollo|hubspot|"
    r"slack|salesforce|jira|github|notion|stripe)\b",
    re.I,
)
_MULTI_STEP_HINT = re.compile(
    r"\b(then|after that|next|and also|multi[- ]?step|plan|workflow|orchestrat)\b",
    re.I,
)


def classify_assistant_turn_complexity(
    message: str,
    *,
    mode: str | None = None,
    connected_integrations: list[str] | None = None,
    parameters: dict[str, Any] | None = None,
) -> TaskType:
    """Heuristic TaskType for assistant chat turns.

    - fast mode / short factual → SUMMARIZATION (low tier)
    - connector / multi-step / long → WORKFLOW_PLANNING or DECISION_REASONING (high)
    - default → RAG_ANSWERING (medium)
    """
    params = parameters or {}
    explicit = str(params.get("complexity") or "").strip().lower()
    if explicit in {"high", "complex"} or params.get("require_high_model"):
        return TaskType.DECISION_REASONING
    if explicit in {"low", "simple", "fast"}:
        return TaskType.SUMMARIZATION

    mode_key = str(mode or "standard").strip().lower()
    text = str(message or "").strip()
    words = len(text.split())
    connected = [str(c).strip() for c in (connected_integrations or []) if str(c).strip()]

    if mode_key == "fast" and words < 80 and not _CONNECTOR_HINT.search(text):
        return TaskType.SUMMARIZATION

    if words > 400 or len(text) > 2500:
        return TaskType.DECISION_REASONING

    if _MULTI_STEP_HINT.search(text) or (connected and _CONNECTOR_HINT.search(text)):
        return TaskType.WORKFLOW_PLANNING

    if mode_key in {"reasoning", "agent", "deep"}:
        return TaskType.DECISION_REASONING

    return TaskType.RAG_ANSWERING


def model_tier_for_task_type(task_type: TaskType) -> str:
    """Map TaskType → MODEL_TIERS key (low/medium/high)."""
    from app.config import TASK_COMPLEXITY

    return TASK_COMPLEXITY.get(task_type.value, "medium")
