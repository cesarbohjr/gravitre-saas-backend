"""Adaptive research cascade — internal retrieval breadth before external research."""
from __future__ import annotations

import json
import re
from enum import StrEnum
from typing import Any

from app.config import Settings
from app.services.assistant_availability import rag_sources_effectively_empty

# Contentless tokens — keyword overlap alone on these must not pass relevance.
_INTERNET_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "or",
        "to",
        "of",
        "in",
        "on",
        "for",
        "with",
        "about",
        "what",
        "how",
        "why",
        "when",
        "where",
        "who",
        "can",
        "you",
        "me",
        "us",
        "i",
        "my",
        "our",
        "your",
        "is",
        "are",
        "do",
        "does",
        "did",
        "help",
        "please",
        "tell",
        "show",
        "get",
        "find",
        "best",
        "top",
        "vs",
        "versus",
    }
)
_TOKEN_RE = re.compile(r"[a-z0-9]{2,}")
# Minimum topical overlap for a web hit to surface as a "source checked".
INTERNET_RELEVANCE_FLOOR = 0.22

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
    """Governance gate: internet research when flag on and a provider is configured."""
    if not bool(getattr(settings, "internet_research_enabled", True)):
        return False
    from app.services.web_research import is_web_research_provider_configured

    return is_web_research_provider_configured(settings)


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
    internal_thin: bool = False,
) -> bool:
    """True when governance allows and scope or thin-internal auto-escalation applies."""
    if not _internet_research_allowed(settings):
        return False
    if internal_thin:
        return True
    return "internet_research" in resolve_active_stages(research_scope, settings=settings)


def resolve_active_stages_with_auto_internet(
    research_scope: str | None,
    *,
    settings: Settings,
    internal_thin: bool = False,
) -> list[str]:
    """Active cascade stages, inserting internet when internal retrieval is thin."""
    stages = list(resolve_active_stages(research_scope, settings=settings))
    if (
        internal_thin
        and _internet_research_allowed(settings)
        and "internet_research" not in stages
    ):
        if "reasoning" in stages:
            stages.insert(stages.index("reasoning"), "internet_research")
        else:
            stages.append("internet_research")
    return stages


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


def _contentful_tokens(text: str) -> set[str]:
    return {
        tok
        for tok in _TOKEN_RE.findall((text or "").lower())
        if tok not in _INTERNET_STOPWORDS and len(tok) >= 3
    }


def score_internet_result_relevance(query: str, *, title: str, snippet: str) -> float:
    """Topical overlap score in [0, 1] — not raw keyword hits on stopwords."""
    q = _contentful_tokens(query)
    if not q:
        return 0.0
    doc = _contentful_tokens(f"{title} {snippet}")
    if not doc:
        return 0.0
    overlap = q & doc
    if not overlap:
        return 0.0
    # Prefer denser overlap; title hits count double via re-adding title tokens.
    title_hits = q & _contentful_tokens(title)
    return min(1.0, (len(overlap) / len(q)) * 0.7 + (len(title_hits) / max(1, len(q))) * 0.5)


def filter_relevant_internet_results(
    query: str,
    results: list[dict[str, Any]] | None,
    *,
    min_score: float = INTERNET_RELEVANCE_FLOOR,
) -> list[dict[str, Any]]:
    """Drop provider hits with no genuine topical connection to the query."""
    kept: list[dict[str, Any]] = []
    for item in results or []:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "")
        snippet = str(item.get("snippet") or item.get("content") or "")
        score = score_internet_result_relevance(query, title=title, snippet=snippet)
        if score < min_score:
            continue
        enriched = dict(item)
        enriched["relevance_score"] = round(score, 3)
        kept.append(enriched)
    return kept


def normalize_internet_results(
    payload: dict[str, Any],
    *,
    query: str | None = None,
) -> list[dict[str, Any]]:
    """Map search_web output into rag_sources-compatible rows (relevance-filtered)."""
    raw = list(payload.get("results") or [])
    q = (query or payload.get("query") or "").strip()
    if q:
        raw = filter_relevant_internet_results(q, raw)
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "Web result")
        url = str(item.get("url") or "")
        snippet = str(item.get("snippet") or item.get("content") or "").strip()
        if not snippet and not url:
            continue
        rel = float(item.get("relevance_score") or 0.55)
        rows.append(
            {
                "id": f"internet-{index}",
                "content": snippet,
                "score": max(0.35, min(0.9, rel)),
                "source": title,
                "title": title,
                "url": url,
                "kind": "internet",
                "metadata": {
                    "provider": payload.get("provider") or "tavily",
                    "url": url,
                    "relevance_score": rel,
                },
            }
        )
    return rows


def format_internet_research_section(payload: dict[str, Any], *, query: str | None = None) -> str:
    """Prompt block for cascade-injected internet results (empty when none relevant)."""
    rows = normalize_internet_results(payload, query=query)
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
    provider = (payload or {}).get("provider") if payload else None
    updated["internet_research"] = {
        "ran": ran,
        "skipped_reason": skipped_reason,
        "result_count": result_count,
        "error": (payload or {}).get("error"),
        "provider": provider if ran else None,
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
    if cascade_state.get("internal_thin") and internet_meta.get("ran"):
        lines.append(
            "Internal sources were thin — live internet research was run automatically. "
            "Cite web results distinctly from org knowledge."
        )
    elif cascade_state.get("internal_thin") and not internet_meta.get("ran"):
        lines.append(
            "Internal sources were thin. Internet research was unavailable or returned no results."
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


def confidence_band_from_score(score: float | None) -> str:
    """Map retrieval_score to a display band — real scores only, no synthetic inflation."""
    if score is None:
        return "unknown"
    if score >= 0.75:
        return "high"
    if score >= 0.45:
        return "medium"
    return "low"


def build_source_breakdown(sources: list[dict[str, Any]] | None) -> dict[str, int]:
    breakdown: dict[str, int] = {}
    for row in sources or []:
        if not isinstance(row, dict):
            continue
        kind = str(row.get("kind") or "unknown")
        breakdown[kind] = breakdown.get(kind, 0) + 1
    return breakdown


def build_cascade_stage_progress(cascade: dict[str, Any]) -> list[dict[str, Any]]:
    """Per-stage status for research plan visualization (Phase 5)."""
    active = list(cascade.get("active_stages") or [])
    internet = cascade.get("internet_research") if isinstance(cascade.get("internet_research"), dict) else {}
    packs = cascade.get("intelligence_packs") if isinstance(cascade.get("intelligence_packs"), dict) else {}
    rows: list[dict[str, Any]] = []
    for stage in CASCADE_STAGE_ORDER:
        if stage not in active:
            continue
        status = "completed"
        detail: str | None = None
        if stage == "internet_research":
            if internet.get("ran"):
                count = int(internet.get("result_count") or 0)
                status = "completed" if count > 0 else "empty"
                detail = f"{count} web results"
            elif not cascade.get("internet_research_enabled"):
                status = "skipped"
                detail = "governance gated"
            else:
                status = "skipped"
        elif stage == "intelligence_packs":
            if packs.get("ran"):
                count = int(packs.get("result_count") or 0)
                status = "completed" if count > 0 else "empty"
                detail = f"{count} pack sources"
            else:
                status = "skipped"
                detail = str(packs.get("skipped_reason") or "no pack assignments")
        elif stage == "reasoning":
            status = "pending"
        rows.append(
            {
                "stage": stage,
                "label": stage.replace("_", " ").title(),
                "status": status,
                "detail": detail,
            }
        )
    return rows


_STAGE_PROGRESS_VERBS: dict[str, str] = {
    "conversation_memory": "Reading conversation memory",
    "internal_rag": "Searching internal knowledge",
    "knowledge_graph": "Walking knowledge graph",
    "connectors": "Querying connected systems",
    "intelligence_packs": "Consulting intelligence packs",
    "internet_research": "Searching the web",
    "reasoning": "Reasoning over findings",
}


def build_research_progress_steps(cascade: dict[str, Any]) -> list[str]:
    """Human-readable cascade steps for Wave 6 SSE progress (named verbs, not stage ids)."""
    steps: list[str] = []
    for row in build_cascade_stage_progress(cascade):
        stage = str(row.get("stage") or "")
        verb = _STAGE_PROGRESS_VERBS.get(stage) or str(row.get("label") or "Working")
        status = str(row.get("status") or "pending")
        detail = row.get("detail")
        if status == "completed":
            steps.append(f"{verb}" + (f" ({detail})" if detail else ""))
        elif status == "empty":
            steps.append(f"{verb} — no matches")
        elif status == "skipped":
            steps.append(f"{verb} skipped" + (f" ({detail})" if detail else ""))
        else:
            steps.append(f"{verb}…")
    return steps


def enrich_research_cascade(
    cascade: dict[str, Any],
    *,
    retrieval_effectiveness: dict[str, Any] | None,
    sources: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    """Phase 4 — attach real retrieval effectiveness and source breakdown."""
    updated = dict(cascade)
    effectiveness = retrieval_effectiveness if isinstance(retrieval_effectiveness, dict) else {}
    score = effectiveness.get("retrieval_score")
    numeric_score = float(score) if score is not None else None
    updated["retrieval_score"] = score
    updated["source_count"] = effectiveness.get("source_count")
    updated["confidence_band"] = confidence_band_from_score(numeric_score)
    updated["top_sources"] = list(effectiveness.get("top_sources") or [])[:6]
    updated["source_breakdown"] = build_source_breakdown(sources)
    updated["stage_progress"] = build_cascade_stage_progress(updated)
    updated["progress_steps"] = build_research_progress_steps(updated)
    return updated


def should_emit_research_cascade_sse(cascade: dict[str, Any] | None) -> bool:
    """True when the client should receive cascade metadata mid-stream."""
    if not isinstance(cascade, dict) or not cascade:
        return False
    if cascade.get("internal_thin") and cascade.get("internet_research_enabled"):
        return True
    scope = str(cascade.get("research_scope") or ResearchScope.INTERNAL_ONLY.value)
    if scope != ResearchScope.INTERNAL_ONLY.value:
        return True
    internet = cascade.get("internet_research") if isinstance(cascade.get("internet_research"), dict) else {}
    packs = cascade.get("intelligence_packs") if isinstance(cascade.get("intelligence_packs"), dict) else {}
    if internet.get("ran") or packs.get("ran"):
        return True
    if cascade.get("stage_progress") or cascade.get("research_actions"):
        return True
    return False


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
    active_stages = resolve_active_stages_with_auto_internet(
        research_scope,
        settings=settings,
        internal_thin=internal_thin,
    )

    return {
        "internal_thin": internal_thin,
        "suggest_broaden": False,
        "prompt_message": None,
        "options": [],
        "auto_internet_when_thin": internal_thin and internet_enabled,
        "research_scope": research_scope or ResearchScope.INTERNAL_ONLY.value,
        "active_stages": active_stages,
        "stage_order": list(CASCADE_STAGE_ORDER),
        "internet_research_enabled": internet_enabled,
        "retrieval_score": (retrieval_effectiveness or {}).get("retrieval_score"),
        "source_count": (retrieval_effectiveness or {}).get("source_count"),
    }
