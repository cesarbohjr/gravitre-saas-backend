"""Map assistant UI modes and explicit model picks to router overrides."""
from __future__ import annotations

from app.services.llm_catalog import get_llm_model, is_known_llm, visible_llm_models
from app.services.model_router import TaskType

# Picker list: current (non-deprecated) catalog models. Deprecated ids are not
# listed but resolve_assistant_model still honours them (saved agents).
AVAILABLE_MODELS: dict[str, dict[str, str]] = {
    m.id: {"provider": m.provider, "label": m.label, "description": m.description}
    for m in visible_llm_models()
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
        if not is_known_llm(override):
            override = MODE_DEFAULT_MODELS.get(
                (mode or "standard").strip().lower(), MODE_DEFAULT_MODELS["standard"]
            )
        normalized_mode = (mode or "standard").strip().lower()
        task = MODE_TASK_TYPE.get(normalized_mode, TaskType.RAG_ANSWERING)
        return override, task

    normalized_mode = (mode or "standard").strip().lower()
    default_model = MODE_DEFAULT_MODELS.get(normalized_mode, MODE_DEFAULT_MODELS["standard"])
    task = MODE_TASK_TYPE.get(normalized_mode, TaskType.RAG_ANSWERING)
    return default_model, task


def infer_mode_from_model(model: str | None) -> str:
    entry = get_llm_model(model)
    if entry is None:
        return "standard"
    if entry.tier == "fast":
        return "fast"
    if entry.tier == "flagship":
        return "reasoning"
    return "standard"
