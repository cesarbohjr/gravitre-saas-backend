"""Adaptive research cascade — internal retrieval breadth before external research."""
from __future__ import annotations

import json
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


def should_run_internet_research(
    research_scope: str | None,
    *,
    settings: Settings,
) -> bool:
    """True when governance allows and the selected scope includes internet research."""
    if not _internet_research_allowed(settings):
        return False
    return "internet_research" in resolve_active_stages(research_scope, settings=settings)


def should_run_intelligence_packs_stage(
    research_scope: str | None,
    *,
    settings: Settings,
    knowledge_assignments: list[dict[str, Any]] | None = None,
) -> bool:
    """True when scope includes intelligence packs and the agent has pack assignments."""
    if "intelligence_packs" not in resolve_active_stages(research_scope, settings=settings):
        return False
    from app.services.pack_operational_state_service import extract_pack_ids

    return bool(extract_pack_ids(knowledge_assignments))


def normalize_internet_results(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Map Tavily search_web output into rag_sources-compatible rows."""
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(payload.get("results") or []):
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "Web result")
        url = str(item.get("url") or "")
        snippet = str(item.get("snippet") or item.get("content") or "").strip()
        if not snippet and not url:
            continue
        rows.append(
            {
                "id": f"internet-{index}",
                "content": snippet,
                "score": 0.55,
                "source": title,
                "title": title,
                "url": url,
                "kind": "internet",
                "metadata": {"provider": "tavily", "url": url},
            }
        )
    return rows


def format_internet_research_section(payload: dict[str, Any]) -> str:
    """Prompt block for cascade-injected internet results."""
    rows = normalize_internet_results(payload)
    if not rows:
        return ""
    body = json.dumps(
        [
            {
                "title": row.get("title"),
                "url": row.get("url"),
                "snippet": row.get("content"),
            }
            for row in rows
        ],
        default=str,
    )[:8000]
    return f"<internet_research>\n{body}\n</internet_research>\n"


def attach_internet_research_to_cascade(
    cascade: dict[str, Any],
    *,
    payload: dict[str, Any] | None,
    ran: bool,
    skipped_reason: str | None = None,
) -> dict[str, Any]:
    """Merge internet stage outcome into research_cascade metadata."""
    updated = dict(cascade)
    result_count = int((payload or {}).get("totalResults") or 0)
    updated["internet_research"] = {
        "ran": ran,
        "skipped_reason": skipped_reason,
        "result_count": result_count,
        "error": (payload or {}).get("error"),
        "provider": "tavily" if ran else None,
    }
    return updated


def build_research_policy_extension(
    *,
    research_scope: str | None,
    cascade_state: dict[str, Any],
) -> str:
    """Prompt section for adaptive / internet-augmented research."""
    internet_meta = (
        cascade_state.get("internet_research")
        if isinstance(cascade_state.get("internet_research"), dict)
        else {}
    )
    scope = str(research_scope or ResearchScope.INTERNAL_ONLY.value)
    pack_meta = (
        cascade_state.get("intelligence_packs")
        if isinstance(cascade_state.get("intelligence_packs"), dict)
        else {}
    )
    include = (
        cascade_state.get("internal_thin")
        or internet_meta.get("ran")
        or pack_meta.get("ran")
        or scope
        in {
            ResearchScope.INTELLIGENCE_PACKS.value,
            ResearchScope.INTERNET_RESEARCH.value,
            ResearchScope.EVERYTHING.value,
        }
    )
    if not include:
        return ""

    active_stages = cascade_state.get("active_stages") or []
    lines = [
        "## Adaptive Research",
    ]
    if cascade_state.get("internal_thin"):
        lines.append(ADAPTIVE_RESEARCH_LEAD)
    lines.extend(
        [
            f"Active research scope: {scope.replace('_', ' ')}.",
            f"Cascade stages in use: {', '.join(active_stages)}.",
            (
                "Prefer verified internal sources first. If context remains thin, say plainly "
                "what is missing — do not invent facts."
            ),
        ]
    )
    if cascade_state.get("suggest_broaden") and not research_scope:
        lines.append(
            "The user has not chosen a broader research scope yet. Answer with what you have, "
            "then invite them to pick a research option if they want you to go further."
        )
    internet_meta = cascade_state.get("internet_research") if isinstance(cascade_state.get("internet_research"), dict) else {}
    if internet_meta.get("ran") and int(internet_meta.get("result_count") or 0) > 0:
        lines.append(
            "Live internet research results are included below. Cite them naturally and distinguish "
            "them from internal organizational knowledge."
        )
    elif internet_meta.get("ran") and internet_meta.get("error"):
        lines.append("Live internet research ran but returned no usable results.")
    elif not cascade_state.get("internet_research_enabled"):
        lines.append("Live internet research is disabled pending governance approval.")
    if pack_meta.get("ran") and int(pack_meta.get("result_count") or 0) > 0:
        lines.append(
            "Intelligence pack sources are included below. Treat them as curated external signals "
            "distinct from internal organizational documents."
        )
    elif pack_meta.get("ran") and int(pack_meta.get("result_count") or 0) == 0:
        lines.append("Intelligence pack research ran but returned no matching pack sources.")
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
