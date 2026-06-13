"""Map assistant UI modes and explicit model picks to router overrides."""
from __future__ import annotations

from app.services.model_router import TaskType

AVAILABLE_MODELS: dict[str, dict[str, str]] = {
    "gpt-5.5": {"provider": "openai", "label": "GPT-5.5", "description": "Most capable"},
    "gpt-5.4-mini": {"provider": "openai", "label": "GPT-5.4 Mini", "description": "Fast & efficient"},
    "claude-sonnet-4-6": {"provider": "anthropic", "label": "Claude Sonnet 4.6", "description": "Best for writing"},
    "claude-haiku-4-5-20251001": {
        "provider": "anthropic",
        "label": "Claude Haiku 4.5",
        "description": "Fastest response",
    },
    "gemini-2.5-pro": {"provider": "gemini", "label": "Gemini 2.5 Pro", "description": "Multimodal"},
    "gemini-2.5-flash": {"provider": "gemini", "label": "Gemini 2.5 Flash", "description": "Fast & cheap"},
}

MODE_DEFAULT_MODELS: dict[str, str] = {
    "fast": "gpt-5.4-mini",
    "standard": "gpt-5.5",
    "reasoning": "gpt-5.5",
    "agent": "gpt-5.5",
}

MODE_TASK_TYPE: dict[str, TaskType] = {
    "fast": TaskType.SUMMARIZATION,
    "standard": TaskType.RAG_ANSWERING,
    "reasoning": TaskType.DECISION_REASONING,
    "agent": TaskType.WORKFLOW_PLANNING,
}


def resolve_assistant_model(
    mode: str | None,
    model_override: str | None,
) -> tuple[str | None, TaskType]:
    """Return (model_override, task_type) for ModelRouter.prepare_stream."""
    override = (model_override or "").strip()
    if override:
        if override not in AVAILABLE_MODELS:
            override = MODE_DEFAULT_MODELS.get((mode or "standard").strip().lower(), "gpt-5.5")
        normalized_mode = (mode or "standard").strip().lower()
        task = MODE_TASK_TYPE.get(normalized_mode, TaskType.RAG_ANSWERING)
        return override, task

    normalized_mode = (mode or "standard").strip().lower()
    default_model = MODE_DEFAULT_MODELS.get(normalized_mode, MODE_DEFAULT_MODELS["standard"])
    task = MODE_TASK_TYPE.get(normalized_mode, TaskType.RAG_ANSWERING)
    return default_model, task


def infer_mode_from_model(model: str | None) -> str:
    if not model:
        return "standard"
    if model in ("gpt-5.4-mini", "claude-haiku-4-5-20251001", "gemini-2.5-flash"):
        return "fast"
    if model in ("gpt-5.5", "claude-sonnet-4-6", "gemini-2.5-pro"):
        return "reasoning"
    return "standard"
