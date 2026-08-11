"""Research Manager — confidence-gated retrieval decisions for the RETRIEVE stage.

Owns whether to broaden research, which cascade layers to run, and how evidence
is ranked/deduplicated/compressed before the LLM reasons. The model does not
decide "should I search"; this component does.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from app.config import Settings
from app.services.adaptive_research_cascade import (
    ResearchScope,
    assess_internal_retrieval_thinness,
    resolve_active_stages,
    should_run_internet_research,
    should_run_intelligence_packs_stage,
)
from app.services.retrieval_provenance import summarize_retrieval_effectiveness

# Stop-early: higher bar than "not thin" — only skip downstream layers when
# internal evidence is genuinely strong (performance guardrail).
STOP_CASCADE_SCORE = 0.75
STOP_CASCADE_MIN_SOURCES = 3
STOP_CASCADE_HIGH_SCORE = 0.85

_KIND_AUTHORITY: dict[str, int] = {
    "knowledge": 100,
    "memory": 90,
    "hybrid_memory": 85,
    "graph": 80,
    "intelligence_pack": 60,
    "internet": 40,
}


class CascadeStage(StrEnum):
    CONVERSATION_MEMORY = "conversation_memory"
    INTERNAL_RAG = "internal_rag"
    CONNECTORS = "connectors"
    KNOWLEDGE_GRAPH = "knowledge_graph"
    INTELLIGENCE_PACKS = "intelligence_packs"
    INTERNET_RESEARCH = "internet_research"
    REASONING = "reasoning"


@dataclass(frozen=True)
class CascadePlan:
    """Which cascade layers Research Manager will run for this turn."""

    stages_to_run: tuple[str, ...]
    stopped_at: str | None
    confidence_sufficient: bool
    skip_graph: bool
    skip_external: bool


@dataclass(frozen=True)
class CuratedEvidence:
    """Ranked, deduplicated sources ready for prompt injection."""

    sources: list[dict[str, Any]]
    rag_section: str
    retrieval_effectiveness: dict[str, Any]


def is_confidence_sufficient(
    *,
    retrieval_effectiveness: dict[str, Any] | None,
    rag_sources: list[dict[str, Any]] | None = None,
    memory_context: dict[str, Any] | None = None,
    graph_context: dict[str, Any] | None = None,
) -> bool:
    """True when internal retrieval is strong enough to stop the cascade early."""
    if assess_internal_retrieval_thinness(
        retrieval_effectiveness=retrieval_effectiveness,
        rag_sources=rag_sources,
        memory_context=memory_context,
        graph_context=graph_context,
    ):
        return False

    effectiveness = retrieval_effectiveness if isinstance(retrieval_effectiveness, dict) else {}
    source_count = int(effectiveness.get("source_count") or 0)
    score_raw = effectiveness.get("retrieval_score")
    score = float(score_raw) if score_raw is not None else None

    if score is not None and score >= STOP_CASCADE_HIGH_SCORE and source_count >= 1:
        return True
    if score is not None and score >= STOP_CASCADE_SCORE and source_count >= STOP_CASCADE_MIN_SOURCES:
        return True
    return False


def _content_fingerprint(row: dict[str, Any]) -> str:
    content = str(row.get("content") or row.get("snippet") or "").strip().lower()[:500]
    if content:
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    source_id = str(row.get("id") or row.get("document_id") or row.get("source") or "")
    return hashlib.sha256(source_id.encode()).hexdigest()[:16]


def authority_rank_sources(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Authority-rank and deduplicate retrieval rows."""
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for row in sources:
        if not isinstance(row, dict):
            continue
        fp = _content_fingerprint(row)
        if fp in seen:
            continue
        seen.add(fp)
        unique.append(dict(row))

    def sort_key(row: dict[str, Any]) -> tuple[int, float, str]:
        kind = str(row.get("kind") or "unknown")
        authority = _KIND_AUTHORITY.get(kind, 50)
        score = float(row.get("score") or 0.0)
        name = str(row.get("source") or row.get("title") or "")
        return (-authority, -score, name)

    return sorted(unique, key=sort_key)


def compress_evidence_section(
    rag_sources: list[dict[str, Any]],
    *,
    max_chars: int = 12000,
    per_source_chars: int = 1200,
) -> str:
    """Build a bounded knowledge_base prompt block from curated sources."""
    if not rag_sources:
        return ""
    payload = [
        {
            "source": source.get("source"),
            "content": str(source.get("content", ""))[:per_source_chars],
            "score": source.get("score"),
            "kind": source.get("kind"),
        }
        for source in rag_sources
    ]
    body = json.dumps(payload, default=str)[:max_chars]
    return f"<knowledge_base>\n{body}\n</knowledge_base>\n"


def build_cascade_plan(
    *,
    research_scope: str | None,
    settings: Settings,
    knowledge_assignments: list[dict[str, Any]] | None,
    confidence_sufficient: bool,
    stopped_at: str | None = None,
) -> CascadePlan:
    """Decide which cascade stages to execute (external gated by scope + confidence)."""
    scope = str(research_scope or ResearchScope.INTERNAL_ONLY.value).strip().lower()
    all_stages = resolve_active_stages(research_scope, settings=settings)

    if confidence_sufficient and (not scope or scope == ResearchScope.INTERNAL_ONLY.value):
        internal = tuple(
            stage
            for stage in all_stages
            if stage
            in {
                CascadeStage.CONVERSATION_MEMORY.value,
                CascadeStage.INTERNAL_RAG.value,
                CascadeStage.CONNECTORS.value,
                CascadeStage.KNOWLEDGE_GRAPH.value,
            }
        )
        return CascadePlan(
            stages_to_run=internal + (CascadeStage.REASONING.value,),
            stopped_at=stopped_at or CascadeStage.INTERNAL_RAG.value,
            confidence_sufficient=True,
            skip_graph=stopped_at in {CascadeStage.CONVERSATION_MEMORY.value, CascadeStage.INTERNAL_RAG.value},
            skip_external=True,
        )

    stages = list(all_stages)
    skip_graph = confidence_sufficient
    skip_external = confidence_sufficient and scope == ResearchScope.INTERNAL_ONLY.value

    if skip_graph and CascadeStage.KNOWLEDGE_GRAPH.value in stages:
        stages.remove(CascadeStage.KNOWLEDGE_GRAPH.value)

    if skip_external:
        for ext in (CascadeStage.INTELLIGENCE_PACKS.value, CascadeStage.INTERNET_RESEARCH.value):
            if ext in stages:
                stages.remove(ext)
    else:
        if not should_run_intelligence_packs_stage(
            research_scope,
            settings=settings,
            knowledge_assignments=knowledge_assignments,
        ):
            if CascadeStage.INTELLIGENCE_PACKS.value in stages:
                stages.remove(CascadeStage.INTELLIGENCE_PACKS.value)
        if should_run_internet_research(
            research_scope,
            settings=settings,
            internal_thin=not confidence_sufficient,
        ):
            if CascadeStage.INTERNET_RESEARCH.value not in stages:
                if CascadeStage.REASONING.value in stages:
                    stages.insert(
                        stages.index(CascadeStage.REASONING.value),
                        CascadeStage.INTERNET_RESEARCH.value,
                    )
                else:
                    stages.append(CascadeStage.INTERNET_RESEARCH.value)
        elif CascadeStage.INTERNET_RESEARCH.value in stages:
            stages.remove(CascadeStage.INTERNET_RESEARCH.value)

    return CascadePlan(
        stages_to_run=tuple(stages),
        stopped_at=stopped_at,
        confidence_sufficient=confidence_sufficient,
        skip_graph=skip_graph,
        skip_external=skip_external,
    )


def should_fetch_graph_layer(
    *,
    classification: dict[str, Any] | None,
    plan_active: bool,
    requires_graph: bool,
    graph_weight: float,
    confidence_sufficient: bool,
) -> bool:
    """Graph fetch gated by policy AND Research Manager confidence stop-early."""
    if confidence_sufficient:
        return False
    if requires_graph:
        return True
    if plan_active and float(graph_weight or 0) >= 0.7:
        return True
    return False


def curate_retrieval_bundle(
    sources: list[dict[str, Any]],
    rag_sources: list[dict[str, Any]],
    *,
    plan: Any = None,
    classification: dict[str, Any] | None = None,
) -> CuratedEvidence:
    """Authority-rank, dedupe, and compress evidence for the model."""
    ranked_sources = authority_rank_sources(sources)
    ranked_rag = authority_rank_sources(rag_sources)
    effectiveness = summarize_retrieval_effectiveness(
        ranked_sources,
        plan=plan,
        classification=classification,
    )
    section = compress_evidence_section(ranked_rag)
    return CuratedEvidence(
        sources=ranked_sources,
        rag_section=section,
        retrieval_effectiveness=effectiveness,
    )


def research_manager_metadata(
    *,
    plan: CascadePlan,
    research_scope: str | None,
) -> dict[str, Any]:
    """Diagnostic metadata attached to research_cascade."""
    return {
        "research_manager": True,
        "cascade_stopped_at": plan.stopped_at,
        "confidence_sufficient": plan.confidence_sufficient,
        "skip_graph": plan.skip_graph,
        "skip_external": plan.skip_external,
        "planned_stages": list(plan.stages_to_run),
        "research_scope": research_scope or ResearchScope.INTERNAL_ONLY.value,
    }
