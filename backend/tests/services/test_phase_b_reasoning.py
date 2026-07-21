"""Phase B: reasoning depth — causal fallback, graph decisions, consensus personas."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.consensus_personas import (
    CHAT_CONSENSUS_PERSONAS,
    HIGH_STAKES_DEBATE_PERSONAS,
    build_agent_defs,
    persona_vote_weights,
)
from app.services.correlational_causal_context import load_causal_enrichment_context
from app.services.decision_intelligence_service import DecisionIntelligenceService, _graph_recommendation_confidence
from app.services.source_reliability_resolver import resolve_average_source_reliability, resolve_source_credibility


def test_consensus_personas_include_reviewers():
    assert "fact_checker" in CHAT_CONSENSUS_PERSONAS
    assert "compliance_reviewer" in HIGH_STAKES_DEBATE_PERSONAS
    assert "devils_advocate" in HIGH_STAKES_DEBATE_PERSONAS


def test_build_agent_defs_uses_weights():
    defs = build_agent_defs(["fact_checker", "devils_advocate"])
    assert len(defs) == 2
    assert defs[0]["role"] == "fact_checker"
    weights = persona_vote_weights(["fact_checker", "devils_advocate"])
    assert weights["fact_checker"] > weights["devils_advocate"]


@pytest.mark.asyncio
async def test_causal_fallback_uses_attribution_when_scaffold_unavailable():
    with patch(
        "app.services.correlational_causal_context.CausalImpactAnalyzer.predict_structured",
        AsyncMock(return_value={"status": "not_available", "reason": "PLANNED"}),
    ):
        with patch(
            "app.services.correlational_causal_context.get_outcome_attribution_service"
        ) as factory:
            service = AsyncMock()
            service.load_admin_outcomes_snapshot = AsyncMock(
                return_value={
                    "agentSummaries": [
                        {
                            "agentId": "a1",
                            "sufficientData": True,
                            "winRate": 0.7,
                            "sampleSize": 12,
                        }
                    ],
                    "pendingMeasurements": 1,
                }
            )
            factory.return_value = service
            result = await load_causal_enrichment_context("org-1", "why did revenue drop?")
    assert result["status"] == "correlational_fallback"
    assert result["best_agent_win_rate"] == 0.7
    assert "correlational" in result["confidence_note"].lower()


@pytest.mark.asyncio
async def test_causal_fallback_insufficient_data():
    with patch(
        "app.services.correlational_causal_context.CausalImpactAnalyzer.predict_structured",
        AsyncMock(return_value={"status": "not_available"}),
    ):
        with patch(
            "app.services.correlational_causal_context.get_outcome_attribution_service"
        ) as factory:
            service = AsyncMock()
            service.load_admin_outcomes_snapshot = AsyncMock(
                return_value={"agentSummaries": [], "pendingMeasurements": 3}
            )
            factory.return_value = service
            result = await load_causal_enrichment_context("org-1", "why?")
    assert result["status"] == "correlational_insufficient_data"


@pytest.mark.asyncio
async def test_resolve_average_source_reliability_from_rag_scores():
    sources = [{"type": "rag", "document_id": "doc-1"}, {"type": "knowledge_graph"}]
    with patch(
        "app.services.source_reliability_resolver.fetch_source_reliability_scores",
        AsyncMock(return_value={"doc-1": 0.8}),
    ):
        with patch("app.services.source_reliability_resolver.get_supabase_client", return_value=MagicMock()):
            score = await resolve_average_source_reliability("org-1", sources)
    assert score == pytest.approx(0.775, abs=0.01)


@pytest.mark.asyncio
async def test_resolve_source_credibility_uses_org_scores():
    with patch(
        "app.services.source_reliability_resolver.fetch_source_reliability_scores",
        AsyncMock(return_value={"doc-1": 0.82}),
    ):
        with patch("app.services.source_reliability_resolver.get_supabase_client", return_value=MagicMock()):
            score = await resolve_source_credibility("org-1", "doc-1", "rag")
    assert score == 0.82


def test_graph_recommendation_confidence_scales_with_signals():
    graph = {"explanation": {"businessSignals": [{}, {}, {}], "relatedEntities": []}}
    payload = _graph_recommendation_confidence(graph)
    assert payload["confidence"] > 0.5


@pytest.mark.asyncio
async def test_decision_intelligence_merges_graph_signals():
    service = DecisionIntelligenceService()
    with patch(
        "app.services.decision_intelligence_service.get_knowledge_graph_service"
    ) as graph_factory:
        graph_factory.return_value.answer_business_question = AsyncMock(
            return_value={
                "status": "ok",
                "identifiedEntity": {"entityType": "deal", "entityId": "d1"},
                "explanation": {
                    "relatedEntities": [{"id": "x"}],
                    "businessSignals": [{"title": "Follow up", "estimated_impact": "medium"}],
                    "scopeNote": "One-hop only",
                },
            }
        )
        with patch(
            "app.services.decision_intelligence_service.get_optimization_suggestion_service"
        ) as opt_factory:
            opt_factory.return_value.list_suggestions = AsyncMock(return_value={"suggestions": []})
            with patch(
                "app.services.decision_intelligence_service.resolve_average_source_reliability",
                AsyncMock(return_value=0.75),
            ):
                result = await service.recommend_next_action("org-1", "deal pipeline")
    assert result["graph_context"] is not None
    assert len(result["recommendations"]) >= 1
    assert "knowledge_graph" in result["recommendations"][0]["evidence_sources"][0]
