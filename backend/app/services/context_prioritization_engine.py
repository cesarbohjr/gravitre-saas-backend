"""Context prioritization — score, rank, and budget context sources for assistant turns."""
from __future__ import annotations

import hashlib
import html
import re
from dataclasses import dataclass, field
from typing import Any, Literal

from app.core.logging import get_logger

logger = get_logger(__name__)

SourceType = Literal[
    "org_context",
    "rag",
    "agent_memory",
    "conversation_memory",
    "company_intelligence",
    "graph",
    "entity_graph",
    "connector_context",
    "task_state",
    "pack_state",
    "knowledge_assignments",
    "knowledge_gap",
    "memory_conflicts",
    "knowledge_fabric",
    "internet",
]

_DEFAULT_TOKEN_BUDGET = 14_000
_SOURCE_RENDER_OVERHEAD_TOKENS = 16
_TRUNCATION_MARKER = "\n[TRUNCATED TO CONTEXT BUDGET]"


@dataclass(frozen=True)
class ContextSource:
    source_id: str
    source_type: SourceType
    label: str
    score: float
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def render_overhead_tokens(self) -> int:
        wrapper_chars = (
            len(self.source_id)
            + len(self.source_type)
            + (2 * len(self.label))
            + 100
        )
        return max(_SOURCE_RENDER_OVERHEAD_TOKENS, wrapper_chars // 4)

    @property
    def token_estimate(self) -> int:
        return max(1, len(self.content) // 4) + self.render_overhead_tokens


@dataclass
class ContextProfile:
    sources: list[ContextSource]
    ranked_sources: list[ContextSource]
    prompt_sections: dict[str, str]
    token_budget: int
    tokens_used: int
    scores: dict[str, float] = field(default_factory=dict)
    excluded_sources: list[dict[str, Any]] = field(default_factory=list)
    duplicate_count: int = 0

    def to_explanation_dict(self) -> dict[str, Any]:
        selected_by_type: dict[str, int] = {}
        tokens_by_type: dict[str, int] = {}
        for source in self.ranked_sources:
            selected_by_type[source.source_type] = (
                selected_by_type.get(source.source_type, 0) + 1
            )
            tokens_by_type[source.source_type] = (
                tokens_by_type.get(source.source_type, 0) + source.token_estimate
            )
        return {
            "sourcesUsed": [
                {
                    "id": source.source_id,
                    "type": source.source_type,
                    "label": source.label,
                    "score": round(source.score, 3),
                    "tokens": source.token_estimate,
                    "truncated": bool(source.metadata.get("truncated")),
                    "retrievalRound": source.metadata.get("retrieval_round"),
                    "authority": source.metadata.get("authority_score"),
                    "freshness": source.metadata.get("freshness_score"),
                    "citation": source.metadata.get("citation"),
                }
                for source in self.ranked_sources
            ],
            "tokenBudget": self.token_budget,
            "tokensUsed": self.tokens_used,
            "scores": self.scores,
            "candidateCount": len(self.sources) + self.duplicate_count,
            "selectedCount": len(self.ranked_sources),
            "duplicateCount": self.duplicate_count,
            "excludedSources": self.excluded_sources,
            "selectedByType": selected_by_type,
            "tokensByType": tokens_by_type,
        }


class ContextPrioritizationEngine:
    """Scores and ranks context sources before prompt assembly."""

    _BASE_WEIGHTS: dict[SourceType, float] = {
        "org_context": 0.72,
        "rag": 0.78,
        "agent_memory": 0.78,
        "conversation_memory": 0.8,
        "company_intelligence": 0.65,
        "graph": 0.82,
        "entity_graph": 0.7,
        "connector_context": 0.68,
        "task_state": 0.6,
        "pack_state": 0.82,
        "knowledge_assignments": 0.74,
        "knowledge_gap": 0.55,
        "memory_conflicts": 0.7,
        "knowledge_fabric": 0.8,
        "internet": 0.58,
    }

    def build_context_profile(
        self,
        *,
        raw_sources: list[ContextSource],
        classification: dict[str, Any],
        token_budget: int = _DEFAULT_TOKEN_BUDGET,
        user_role: str | None = None,
        department: str | None = None,
        retrieval_plan: dict[str, Any] | None = None,
    ) -> ContextProfile:
        scored = self.score_context_sources(
            raw_sources,
            classification,
            user_role=user_role,
            department=department,
            retrieval_plan=retrieval_plan,
        )
        deduplicated, duplicate_exclusions = self.deduplicate_sources(scored)
        ranked, sections, tokens_used, budget_exclusions = self._rank_context_relevance(
            deduplicated,
            token_budget=token_budget,
        )
        return ContextProfile(
            sources=deduplicated,
            ranked_sources=ranked,
            prompt_sections=sections,
            token_budget=token_budget,
            tokens_used=tokens_used,
            scores={source.source_id: source.score for source in scored},
            excluded_sources=duplicate_exclusions + budget_exclusions,
            duplicate_count=len(duplicate_exclusions),
        )

    def score_context_sources(
        self,
        sources: list[ContextSource],
        classification: dict[str, Any],
        *,
        user_role: str | None = None,
        department: str | None = None,
        retrieval_plan: dict[str, Any] | None = None,
    ) -> list[ContextSource]:
        intent = str(classification.get("intent") or "").lower()
        requires_action = bool(classification.get("requires_action"))
        requires_graph = bool(classification.get("requires_graph"))
        dept = str(classification.get("department") or department or "").lower()
        plan_weights = (retrieval_plan or {}).get("source_type_weights") or {}

        scored: list[ContextSource] = []
        for source in sources:
            base = plan_weights.get(source.source_type, self._BASE_WEIGHTS.get(source.source_type, 0.5))
            score = base

            if source.source_type == "rag" and intent in {"knowledge_lookup", "crm_lookup", "analytics"}:
                score += 0.06
            if source.source_type == "knowledge_fabric" and intent in {
                "knowledge_lookup",
                "analytics",
                "risk_analysis",
            }:
                score += 0.04
            if source.source_type == "org_context" and intent in {
                "workflow_execution",
                "agent_management",
                "connector_management",
            }:
                score += 0.1
            if source.source_type == "connector_context" and requires_action:
                score += 0.15
            if source.source_type == "graph" and requires_graph:
                score += 0.08
            if source.source_type == "pack_state" and intent in {
                "analytics",
                "risk_analysis",
                "knowledge_lookup",
                "workflow_execution",
            }:
                score += 0.1
            if source.source_type == "conversation_memory":
                score += 0.08
            if dept and dept in source.label.lower():
                score += 0.06
            if user_role and user_role.lower() in {"admin", "owner"} and source.source_type == "org_context":
                score += 0.04

            retrieval_score = _number(source.metadata.get("retrieval_score"), source.score)
            authority_score = _number(source.metadata.get("authority_score"))
            freshness_score = _number(source.metadata.get("freshness_score"))
            query_overlap = _number(source.metadata.get("query_overlap"))
            score += min(0.04, max(0.0, retrieval_score) * 0.04)
            score += min(0.05, max(0.0, authority_score) * 0.05)
            score += min(0.02, max(0.0, freshness_score) * 0.02)
            score += min(0.06, max(0.0, query_overlap) * 0.06)
            content_bonus = min(0.02, len(source.content) / 80_000)
            score = round(min(1.0, score + content_bonus), 4)
            scored.append(
                ContextSource(
                    source_id=source.source_id,
                    source_type=source.source_type,
                    label=source.label,
                    score=score,
                    content=source.content,
                    metadata=dict(source.metadata),
                )
            )
        return sorted(scored, key=lambda item: item.score, reverse=True)

    def deduplicate_sources(
        self,
        sources: list[ContextSource],
    ) -> tuple[list[ContextSource], list[dict[str, Any]]]:
        """Drop exact cross-source duplicates after scoring, keeping the best copy."""
        kept: list[ContextSource] = []
        seen: dict[str, ContextSource] = {}
        excluded: list[dict[str, Any]] = []
        for source in sorted(sources, key=lambda item: (-item.score, item.source_id)):
            normalized = re.sub(r"\s+", " ", source.content).strip().lower()
            key = str(source.metadata.get("content_fingerprint") or "").strip()
            if not key and normalized:
                key = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
            if key and key in seen:
                excluded.append(
                    {
                        "id": source.source_id,
                        "type": source.source_type,
                        "reason": "duplicate",
                        "duplicateOf": seen[key].source_id,
                    }
                )
                continue
            if key:
                seen[key] = source
            kept.append(source)
        return kept, excluded

    def rank_context_relevance(
        self,
        sources: list[ContextSource],
        *,
        token_budget: int = _DEFAULT_TOKEN_BUDGET,
    ) -> tuple[list[ContextSource], dict[str, str], int]:
        ranked, sections, tokens_used, _ = self._rank_context_relevance(
            sources,
            token_budget=token_budget,
        )
        return ranked, sections, tokens_used

    def _rank_context_relevance(
        self,
        sources: list[ContextSource],
        *,
        token_budget: int,
    ) -> tuple[list[ContextSource], dict[str, str], int, list[dict[str, Any]]]:
        ranked: list[ContextSource] = []
        sections: dict[str, str] = {}
        tokens_used = 0
        excluded: list[dict[str, Any]] = []

        for source in sorted(sources, key=lambda item: item.score, reverse=True):
            if not source.content.strip():
                excluded.append(
                    {"id": source.source_id, "type": source.source_type, "reason": "empty"}
                )
                continue
            estimate = source.token_estimate
            if tokens_used + estimate > token_budget:
                remaining = max(0, token_budget - tokens_used)
                render_overhead = source.render_overhead_tokens
                if (
                    remaining <= render_overhead
                    or (remaining < 200 and ranked)
                ):
                    excluded.append(
                        {"id": source.source_id, "type": source.source_type, "reason": "budget"}
                    )
                    continue
                content_chars = (
                    remaining - render_overhead
                ) * 4
                body_chars = max(0, content_chars - len(_TRUNCATION_MARKER))
                trimmed = source.content[:body_chars].rstrip() + _TRUNCATION_MARKER
                if len(trimmed.strip()) < 40:
                    excluded.append(
                        {"id": source.source_id, "type": source.source_type, "reason": "budget"}
                    )
                    continue
                content = trimmed
                estimate = (
                    max(1, len(trimmed) // 4) + render_overhead
                )
                source = ContextSource(
                    source_id=source.source_id,
                    source_type=source.source_type,
                    label=source.label,
                    score=source.score,
                    content=content,
                    metadata={**source.metadata, "truncated": True},
                )
            else:
                content = source.content

            ranked.append(source)
            section_key = source.source_type if source.source_type not in sections else source.source_id
            sections[section_key] = content
            tokens_used += estimate

        return ranked, sections, tokens_used, excluded

    def explain_context_used(self, profile: ContextProfile) -> str:
        if not profile.ranked_sources:
            return "This answer used your live org snapshot and the current conversation."

        labels = [source.label for source in profile.ranked_sources[:6]]
        joined = ", ".join(labels)
        return (
            f"Gravitre prioritized {len(profile.ranked_sources)} context source(s): {joined}. "
            f"Context budget: ~{profile.tokens_used} tokens of {profile.token_budget}."
        )


_EVIDENCE_SOURCE_TYPES: dict[str, SourceType] = {
    "knowledge": "rag",
    "org_rag": "rag",
    "rag": "rag",
    "knowledge_pack": "knowledge_fabric",
    "knowledge_fabric": "knowledge_fabric",
    "internet": "internet",
    "graph": "graph",
    "business_graph": "graph",
}


def evidence_rows_to_context_sources(
    rows: list[dict[str, Any]],
    *,
    query: str,
) -> list[ContextSource]:
    """Normalize heterogeneous retrieval rows at the prompt boundary."""
    query_terms = _terms(query)
    sources: list[ContextSource] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        content = str(row.get("content") or "").strip()
        if not content:
            continue
        kind = str(row.get("kind") or "rag").strip().lower()
        source_type = _EVIDENCE_SOURCE_TYPES.get(kind, "rag")
        label = str(
            row.get("citation")
            or row.get("source")
            or row.get("url")
            or f"{kind} source {index + 1}"
        ).strip()
        identity = str(
            row.get("document_id")
            or row.get("source_id")
            or row.get("url")
            or row.get("citation")
            or row.get("source")
            or ""
        ).strip()
        stable_material = f"{identity}\n{content}" if identity else content
        digest = hashlib.sha256(stable_material.encode("utf-8")).hexdigest()[:16]
        overlap = _term_overlap(query_terms, _terms(content))
        metadata = dict(row)
        metadata.update(
            {
                "source_identity": identity.lower() if identity else "",
                "content_fingerprint": hashlib.sha256(
                    re.sub(r"\s+", " ", content).strip().lower().encode("utf-8")
                ).hexdigest(),
                "retrieval_score": _number(row.get("score"), row.get("semantic_score")),
                "query_overlap": overlap,
                "citation": row.get("citation") or row.get("url") or row.get("source"),
            }
        )
        sources.append(
            ContextSource(
                source_id=f"{source_type}:{digest}",
                source_type=source_type,
                label=label,
                score=_number(row.get("score"), row.get("semantic_score")),
                content=content,
                metadata=metadata,
            )
        )
    return sources


def render_evidence_profile(profile: ContextProfile) -> str:
    """Render ranked evidence without restoring source-kind ordering."""
    return render_context_sources(profile.ranked_sources)


def render_context_sources(sources: list[ContextSource]) -> str:
    """Render already-ranked sources in their selected order."""
    labels: dict[SourceType, str] = {
        "rag": "ORG PRIVATE KNOWLEDGE",
        "knowledge_fabric": "PLATFORM KNOWLEDGE PACK EXCERPTS",
        "internet": "INTERNET RESEARCH",
        "graph": "CONNECTED BUSINESS SYSTEMS — ORG ENTITY GRAPH",
    }
    parts: list[str] = []
    for source in sources:
        heading = labels.get(source.source_type, "CONTEXT SOURCE")
        safe_id = html.escape(source.source_id, quote=True)
        safe_type = html.escape(source.source_type, quote=True)
        safe_label = html.escape(source.label, quote=True)
        safe_content = re.sub(
            r"<(/?)context_source",
            r"&lt;\1context_source",
            source.content,
            flags=re.I,
        )
        parts.append(
            f"{heading}:\n"
            f'<context_source id="{safe_id}" type="{safe_type}" label="{safe_label}">\n'
            f"Source: {safe_label}\n"
            f"{safe_content.strip()}\n"
            "</context_source>"
        )
    return "\n\n".join(parts)


def _number(*values: Any) -> float:
    for value in values:
        try:
            if value is not None:
                return max(0.0, min(1.0, float(value)))
        except (TypeError, ValueError):
            continue
    return 0.0


def _terms(text: str) -> set[str]:
    return {
        term
        for term in re.findall(r"[a-z0-9]{3,}", (text or "").lower())
        if term not in {"the", "and", "for", "with", "that", "this", "from"}
    }


def _term_overlap(query_terms: set[str], content_terms: set[str]) -> float:
    if not query_terms:
        return 0.0
    return len(query_terms & content_terms) / len(query_terms)


_engine: ContextPrioritizationEngine | None = None


def get_context_prioritization_engine() -> ContextPrioritizationEngine:
    global _engine
    if _engine is None:
        _engine = ContextPrioritizationEngine()
    return _engine
