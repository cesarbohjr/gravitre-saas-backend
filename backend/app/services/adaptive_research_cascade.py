"""Adaptive research cascade — internal retrieval breadth before external research."""
from __future__ import annotations

from enum import StrEnum
from typing import Any

from app.config import Settings
from app.services.assistant_availability import rag_sources_effectively_empty

# Real signal from summarize_retrieval_effectiveness (retrieval_provenance.py).
THIN_RETRIEVAL_SCORE_THRESHOLD = 0.35
THIN_SOURCE_COUNT = 2

CASCADE_STAGE_ORDER = (
    "conversation_memory",
    "internal_rag",
    "knowledge_graph",
    "connectors",
    "intelligence_packs",
    "internet_research",
    "reasoning",
)


class ResearchScope(StrEnum):
    INTERNAL_ONLY = "internal_only"
    INTELLIGENCE_PACKS = "intelligence_packs"
    INTERNET_RESEARCH = "internet_research"
    EVERYTHING = "everything"


ADAPTIVE_RESEARCH_LEAD = (
    "I found limited information within your organization's connected knowledge. "
    "I can broaden my research."
)


def _internet_research_allowed(settings: Settings) -> bool:
    """Governance gate: internet research stays off until explicitly enabled."""
    enabled_flag = bool(getattr(settings, "internet_research_enabled", False))
    configured = bool((getattr(settings, "tavily_api_key", None) or "").strip())
    return enabled_flag and configured


def assess_internal_retrieval_thinness(
    *,
    retrieval_effectiveness: dict[str, Any] | None,
    rag_sources: list[dict[str, Any]] | None,
    memory_context: dict[str, Any] | None = None,
    graph_context: dict[str, Any] | None = None,
) -> bool:
    """True when internal retrieval is unlikely sufficient for a grounded answer."""
    if rag_sources_effectively_empty(rag_sources):
        memory_rows = 0
        if isinstance(memory_context, dict):
            for key in ("memories", "patterns", "facts"):
                memory_rows += len(memory_context.get(key) or [])
        if memory_rows == 0 and not (isinstance(graph_context, dict) and graph_context):
            return True

    effectiveness = retrieval_effectiveness if isinstance(retrieval_effectiveness, dict) else {}
    source_count = int(effectiveness.get("source_count") or 0)
    score = effectiveness.get("retrieval_score")
    if source_count <= THIN_SOURCE_COUNT:
        return True
    if score is not None and float(score) < THIN_RETRIEVAL_SCORE_THRESHOLD:
        return True
    return False


def build_research_scope_options(settings: Settings) -> list[dict[str, Any]]:
    internet_allowed = _internet_research_allowed(settings)
    options: list[dict[str, Any]] = [
        {
            "scope": ResearchScope.INTERNAL_ONLY.value,
            "label": "Internal only",
            "description": "Stay with your connected knowledge, memory, and graph.",
            "enabled": True,
        },
        {
            "scope": ResearchScope.INTELLIGENCE_PACKS.value,
            "label": "+ Intelligence Packs",
            "description": "Add curated pack signals and external source hints.",
            "enabled": True,
        },
        {
            "scope": ResearchScope.INTERNET_RESEARCH.value,
            "label": "+ Live Internet Research",
            "description": "Search the public web when governance allows.",
            "enabled": internet_allowed,
            "disabled_reason": (
                None
                if internet_allowed
                else "Pending governance approval — internet research is not enabled for this environment."
            ),
        },
        {
            "scope": ResearchScope.EVERYTHING.value,
            "label": "Everything available",
            "description": "Use all enabled internal and pack sources.",
            "enabled": True,
        },
    ]
    return options


def resolve_active_stages(
    research_scope: str | None,
    *,
    settings: Settings,
) -> list[str]:
    """Map user-selected scope to cascade stages (internet gated)."""
    scope = str(research_scope or ResearchScope.INTERNAL_ONLY.value).strip().lower()
    internet_ok = _internet_research_allowed(settings)
    base = [
        "conversation_memory",
        "internal_rag",
        "knowledge_graph",
        "connectors",
    ]
    if scope in {ResearchScope.INTELLIGENCE_PACKS.value, ResearchScope.EVERYTHING.value}:
        base.append("intelligence_packs")
    if scope == ResearchScope.INTERNET_RESEARCH.value and internet_ok:
        base.append("internet_research")
    elif scope == ResearchScope.EVERYTHING.value and internet_ok:
        base.append("internet_research")
    base.append("reasoning")
    return base


def build_research_policy_extension(
    *,
    research_scope: str | None,
    cascade_state: dict[str, Any],
) -> str:
    """Prompt section injected when internal retrieval is thin."""
    if not cascade_state.get("internal_thin"):
        return ""

    scope = str(research_scope or ResearchScope.INTERNAL_ONLY.value)
    active_stages = cascade_state.get("active_stages") or []
    lines = [
        "## Adaptive Research",
        ADAPTIVE_RESEARCH_LEAD,
        f"Active research scope: {scope.replace('_', ' ')}.",
        f"Cascade stages in use: {', '.join(active_stages)}.",
        (
            "Prefer verified internal sources first. If context remains thin, say plainly "
            "what is missing — do not invent facts."
        ),
    ]
    if cascade_state.get("suggest_broaden") and not research_scope:
        lines.append(
            "The user has not chosen a broader research scope yet. Answer with what you have, "
            "then invite them to pick a research option if they want you to go further."
        )
    if not cascade_state.get("internet_research_enabled"):
        lines.append("Live internet research is disabled pending governance approval.")
    return "\n".join(lines)


def evaluate_research_cascade(
    *,
    retrieval_effectiveness: dict[str, Any] | None,
    rag_sources: list[dict[str, Any]] | None,
    memory_context: dict[str, Any] | None = None,
    graph_context: dict[str, Any] | None = None,
    research_scope: str | None = None,
    settings: Settings,
) -> dict[str, Any]:
    internal_thin = assess_internal_retrieval_thinness(
        retrieval_effectiveness=retrieval_effectiveness,
        rag_sources=rag_sources,
        memory_context=memory_context,
        graph_context=graph_context,
    )
    internet_enabled = _internet_research_allowed(settings)
    active_stages = resolve_active_stages(research_scope, settings=settings)
    options = build_research_scope_options(settings)
    suggest_broaden = internal_thin and not str(research_scope or "").strip()

    return {
        "internal_thin": internal_thin,
        "suggest_broaden": suggest_broaden,
        "prompt_message": ADAPTIVE_RESEARCH_LEAD if suggest_broaden else None,
        "options": options if suggest_broaden else [],
        "research_scope": research_scope or ResearchScope.INTERNAL_ONLY.value,
        "active_stages": active_stages,
        "stage_order": list(CASCADE_STAGE_ORDER),
        "internet_research_enabled": internet_enabled,
        "retrieval_score": (retrieval_effectiveness or {}).get("retrieval_score"),
        "source_count": (retrieval_effectiveness or {}).get("source_count"),
    }
