"""Context prioritization — score, rank, and budget context sources for assistant turns."""
from __future__ import annotations

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
]

_DEFAULT_TOKEN_BUDGET = 14_000


@dataclass(frozen=True)
class ContextSource:
    source_id: str
    source_type: SourceType
    label: str
    score: float
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def token_estimate(self) -> int:
        return max(1, len(self.content) // 4)


@dataclass
class ContextProfile:
    sources: list[ContextSource]
    ranked_sources: list[ContextSource]
    prompt_sections: dict[str, str]
    token_budget: int
    tokens_used: int
    scores: dict[str, float] = field(default_factory=dict)

    def to_explanation_dict(self) -> dict[str, Any]:
        return {
            "sourcesUsed": [
                {
                    "id": source.source_id,
                    "type": source.source_type,
                    "label": source.label,
                    "score": round(source.score, 3),
                }
                for source in self.ranked_sources
            ],
            "tokenBudget": self.token_budget,
            "tokensUsed": self.tokens_used,
            "scores": self.scores,
        }


class ContextPrioritizationEngine:
    """Scores and ranks context sources before prompt assembly."""

    _BASE_WEIGHTS: dict[SourceType, float] = {
        "org_context": 0.72,
        "rag": 0.85,
        "agent_memory": 0.78,
        "conversation_memory": 0.8,
        "company_intelligence": 0.65,
        "graph": 0.88,
        "entity_graph": 0.7,
        "connector_context": 0.68,
        "task_state": 0.6,
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
        ranked, sections, tokens_used = self.rank_context_relevance(scored, token_budget=token_budget)
        return ContextProfile(
            sources=scored,
            ranked_sources=ranked,
            prompt_sections=sections,
            token_budget=token_budget,
            tokens_used=tokens_used,
            scores={source.source_id: source.score for source in scored},
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
                score += 0.12
            if source.source_type == "org_context" and intent in {
                "workflow_execution",
                "agent_management",
                "connector_management",
            }:
                score += 0.1
            if source.source_type == "connector_context" and requires_action:
                score += 0.15
            if source.source_type == "graph" and requires_graph:
                score += 0.14
            if source.source_type == "conversation_memory":
                score += 0.08
            if dept and dept in source.label.lower():
                score += 0.06
            if user_role and user_role.lower() in {"admin", "owner"} and source.source_type == "org_context":
                score += 0.04

            content_bonus = min(0.08, len(source.content) / 20_000)
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

    def rank_context_relevance(
        self,
        sources: list[ContextSource],
        *,
        token_budget: int = _DEFAULT_TOKEN_BUDGET,
    ) -> tuple[list[ContextSource], dict[str, str], int]:
        ranked: list[ContextSource] = []
        sections: dict[str, str] = {}
        tokens_used = 0

        for source in sorted(sources, key=lambda item: item.score, reverse=True):
            if not source.content.strip():
                continue
            estimate = source.token_estimate
            if tokens_used + estimate > token_budget and ranked:
                remaining = max(0, token_budget - tokens_used)
                if remaining < 200:
                    continue
                trimmed = source.content[: remaining * 4]
                if len(trimmed.strip()) < 40:
                    continue
                content = trimmed
                estimate = len(trimmed) // 4
            else:
                content = source.content

            ranked.append(source)
            section_key = source.source_type if source.source_type not in sections else source.source_id
            sections[section_key] = content
            tokens_used += estimate

        return ranked, sections, tokens_used

    def explain_context_used(self, profile: ContextProfile) -> str:
        if not profile.ranked_sources:
            return "This answer used your live org snapshot and the current conversation."

        labels = [source.label for source in profile.ranked_sources[:6]]
        joined = ", ".join(labels)
        return (
            f"Gravitre prioritized {len(profile.ranked_sources)} context source(s): {joined}. "
            f"Context budget: ~{profile.tokens_used} tokens of {profile.token_budget}."
        )


_engine: ContextPrioritizationEngine | None = None


def get_context_prioritization_engine() -> ContextPrioritizationEngine:
    global _engine
    if _engine is None:
        _engine = ContextPrioritizationEngine()
    return _engine
