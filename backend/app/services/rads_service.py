"""Retrieval-augmented decision entry point — orchestrates existing services only."""
from __future__ import annotations

from typing import Any

from app.config import Settings, get_settings
from app.services.ai_trust_layer import get_ai_trust_layer
from app.services.confidence_honesty import (
    CONFIDENCE_SOURCE_HEURISTIC,
    CONFIDENCE_SOURCE_INSUFFICIENT,
    annotate_confidence,
    label_confidence,
)
from app.services.decision_intelligence_service import get_decision_intelligence_service
from app.services.knowledge_graph_service import get_knowledge_graph_service
from app.services.rag_service import get_rag_service


class RetrievalAugmentedDecisionService:
    """
    Entry point for recommend / explain product capabilities.
    Orchestrates RAG, knowledge graph, decision intelligence, and trust envelope.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    async def decide(
        self,
        org_id: str,
        question: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        rag = get_rag_service()
        rag_result = await rag.query(org_id=org_id, query=question, top_k=8)
        evidence = [
            {
                "type": "rag",
                "content": str(getattr(chunk, "content", "") or "")[:300],
                "documentId": getattr(chunk, "document_id", None),
            }
            for chunk in (rag_result.chunks or [])
        ]

        graph_context: dict[str, Any] = {}
        if context and context.get("entity_id") and context.get("entity_type"):
            graph_context = await get_knowledge_graph_service().explain_entity(
                org_id,
                str(context["entity_type"]),
                str(context["entity_id"]),
            )
        elif context and context.get("entity_id"):
            graph_context = await get_knowledge_graph_service().answer_business_question(org_id, question)

        recommendation = await get_decision_intelligence_service(self.settings).recommend_next_action(
            org_id,
            question,
        )
        recs = recommendation.get("recommendations") or []
        primary = recs[0] if recs else {
            "action": "Gather more org usage and feedback before recommending action.",
            "reasoning": "Insufficient structured recommendations available.",
            **label_confidence(0.3, source=CONFIDENCE_SOURCE_INSUFFICIENT, is_estimate=True),
        }
        sources = list(evidence)
        if graph_context:
            sources.append({"type": "knowledge_graph", "context": graph_context})

        confidence = float(primary.get("confidence") or 0.3)
        envelope = get_ai_trust_layer().wrap_response(
            answer=str(primary.get("action") or ""),
            sources=sources,
            confidence=confidence,
            reasoning_summary=str(primary.get("reasoning") or ""),
            actions_taken=[],
            actions_pending_approval=[primary] if primary.get("requires_approval", True) else [],
            advisory_only=True,
        )
        return annotate_confidence(
            envelope,
            is_estimate=bool(primary.get("confidence_is_estimate", True)),
            source=str(primary.get("confidence_source") or CONFIDENCE_SOURCE_HEURISTIC),
            value=confidence,
        )


_rads_service: RetrievalAugmentedDecisionService | None = None


def get_rads_service(settings: Settings | None = None) -> RetrievalAugmentedDecisionService:
    global _rads_service
    if _rads_service is None or settings is not None:
        _rads_service = RetrievalAugmentedDecisionService(settings)
    return _rads_service
