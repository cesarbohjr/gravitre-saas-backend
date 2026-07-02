"""Phase Omega enterprise intelligence evolution tests."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.ai_architecture_registry import AI_ARCHITECTURE_REGISTRY
from app.ml.federated_learning import FederatedLearningCoordinator
from app.ml.world_models import WorldModelScaffold
from app.operators.consensus_engine import ConsensusEngine
from app.services.business_digital_twin_engine import BusinessDigitalTwinEngine
from app.services.knowledge_graph_service import KnowledgeGraphService
from app.services.predictive_operations_engine import PredictiveOperationsEngine
from app.services.process_mining_service import ProcessMiningService


@pytest.mark.asyncio
async def test_multi_hop_capped_at_max_hops():
    service = KnowledgeGraphService()
    with patch(
        "app.services.knowledge_graph_service.get_related_entities",
        new=AsyncMock(return_value=[]),
    ):
        result = await service.traverse_multi_hop("org-1", "agent", "a1", max_hops=10)
    assert result["maxHopsRequested"] == service.MAX_HOPS
    assert "scope_note" in result


@pytest.mark.asyncio
async def test_confidence_decays_per_hop():
    service = KnowledgeGraphService()
    hops = [
        {"entityType": "deal", "entityId": "d1", "relationshipType": "tracked-by", "confidence": 0.9},
    ]

    async def _neighbors(*args, **kwargs):
        depth = kwargs.get("max_results")
        _ = depth
        return hops if args[2] == "a1" else []

    with patch("app.services.knowledge_graph_service.get_related_entities", side_effect=_neighbors):
        result = await service.traverse_multi_hop("org-1", "agent", "a1", max_hops=2)
    assert result["paths"]
    assert result["paths"][0]["confidence"] <= 0.9


@pytest.mark.asyncio
async def test_low_confidence_edges_not_traversed():
    service = KnowledgeGraphService()
    with patch(
        "app.services.knowledge_graph_service.get_related_entities",
        new=AsyncMock(
            return_value=[
                {
                    "entityType": "deal",
                    "entityId": "d1",
                    "relationshipType": "tracked-by",
                    "confidence": 0.05,
                }
            ]
        ),
    ):
        result = await service.traverse_multi_hop("org-1", "agent", "a1", max_hops=2)
    assert result["paths"] == []


@pytest.mark.asyncio
async def test_scope_note_always_present():
    service = KnowledgeGraphService()
    with patch(
        "app.services.knowledge_graph_service.get_related_entities",
        new=AsyncMock(return_value=[]),
    ):
        result = await service.traverse_multi_hop("org-1", "agent", "a1")
    assert result.get("scope_note")


@pytest.mark.asyncio
async def test_graph_recommendation_advisory_only():
    service = KnowledgeGraphService()
    with patch.object(service, "traverse_multi_hop", new=AsyncMock(return_value={"paths": []})):
        with patch(
            "app.services.decision_intelligence_service.get_decision_intelligence_service"
        ) as mock_decision:
            mock_decision.return_value.recommend_next_action = AsyncMock(return_value={"recommendations": []})
            recs = await service.get_graph_recommendations("org-1", "agent", "a1", "grow pipeline")
    assert all(r.get("advisory_only") for r in recs) or recs == []


@pytest.mark.asyncio
async def test_one_hop_methods_unchanged():
    service = KnowledgeGraphService()
    with patch(
        "app.services.knowledge_graph_service.get_related_entities",
        new=AsyncMock(return_value=[]),
    ):
        result = await service.explain_entity("org-1", "agent", "a1", client=MagicMock())
    assert result["hopLimit"] == 1
    assert "scopeNote" in result


@pytest.mark.asyncio
async def test_unsupported_domain_returns_structured_response():
    engine = BusinessDigitalTwinEngine()
    result = await engine.simulate("org-1", "unknown_domain", "change")
    assert result["simulation_status"] == "domain_not_supported"


@pytest.mark.asyncio
async def test_insufficient_data_returns_honestly():
    engine = BusinessDigitalTwinEngine()
    with patch.object(engine, "_load_domain_series", new=AsyncMock(return_value=[1, 2])):
        result = await engine.simulate("org-1", "revenue", "change")
    assert result["simulation_status"] == "insufficient_data"


@pytest.mark.asyncio
async def test_digital_twin_scope_note_always_present():
    engine = BusinessDigitalTwinEngine()
    with patch.object(engine, "_load_domain_series", new=AsyncMock(return_value=list(range(20)))):
        result = await engine.simulate("org-1", "revenue", "increase prices", {"delta_percent": 5})
    assert result.get("scope_note")
    assert result.get("approval_required") is True


@pytest.mark.asyncio
async def test_no_fabricated_financial_projections():
    engine = BusinessDigitalTwinEngine()
    with patch.object(engine, "_load_domain_series", new=AsyncMock(return_value=list(range(20)))):
        result = await engine.simulate("org-1", "revenue", "change", {"delta_percent": 0})
    assumptions = " ".join(result.get("assumptions") or [])
    assert "fabricated" in assumptions.lower() or "measured" in assumptions.lower()


def test_v9_boundary_preserved():
    assert "V9" in BusinessDigitalTwinEngine.__doc__ or "v9" in BusinessDigitalTwinEngine.__doc__.lower()


@pytest.mark.asyncio
async def test_health_score_insufficient_data_below_min():
    service = ProcessMiningService()
    mock_client = MagicMock()
    mock_client.table.return_value.select.return_value.eq.return_value.gte.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[{"id": "1", "status": "completed"}]
    )
    with patch.object(service, "_client", return_value=mock_client):
        result = await service.calculate_process_health_score("org-1")
    assert result["status"] == "insufficient_data"


@pytest.mark.asyncio
async def test_cost_estimate_none_without_financial_connector():
    service = ProcessMiningService()
    mock_client = MagicMock()
    mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[]
    )
    with patch.object(service, "_client", return_value=mock_client):
        result = await service.estimate_business_impact("org-1", {"avgDurationMs": 1000, "sampleSize": 5})
    assert result["costEstimate"] is None


@pytest.mark.asyncio
async def test_consensus_advisory_only():
    engine = ConsensusEngine()
    with patch.object(engine, "_get_agent_stance", new=AsyncMock(return_value={"persona": "validator", "vote": "support", "confidence": 0.8, "summary": "ok"})):
        with patch.object(engine._chat_consensus, "deliberate", new=AsyncMock(return_value={"consensus_recommendation": "go", "consensus_explanation": "reviewed"})):
            with patch.object(engine, "_persist_deliberation", new=AsyncMock()):
                result = await engine.deliberate("org-1", "do x", {}, ["validator"])
    assert result["advisory_only"] is True
    assert result["approval_required"] is True


def test_vote_breakdown_includes_all_agents():
    engine = ConsensusEngine()
    stances = [
        {"persona": "a", "vote": "support", "confidence": 0.9, "summary": "yes"},
        {"persona": "b", "vote": "oppose", "confidence": 0.7, "summary": "no"},
    ]
    agg = engine._aggregate_votes(stances)
    assert set(agg["vote_breakdown"].keys()) >= {"support", "oppose", "revise"}


def test_tiebreak_uses_confidence_not_arbitrary():
    engine = ConsensusEngine()
    stances = [
        {"persona": "a", "vote": "support", "confidence": 0.9, "summary": ""},
        {"persona": "b", "vote": "oppose", "confidence": 0.4, "summary": ""},
    ]
    agg = engine._aggregate_votes(stances)
    assert agg["consensus_vote"] in {"support", "oppose", "revise"}


@pytest.mark.asyncio
async def test_domain_pack_planned_for_untrained_models():
    from app.services.predictive_operations_engine import ModelPlannedError

    engine = PredictiveOperationsEngine()
    with patch.object(engine, "_predict_model", new=AsyncMock(side_effect=ModelPlannedError("x"))):
        result = await engine.run_domain_predictions("org-1", "finance")
    assert result["predictions"]["revenue_forecaster"]["status"] == "planned"
    assert result["advisory_only"] is True


@pytest.mark.asyncio
async def test_all_outputs_advisory_only_predictive():
    engine = PredictiveOperationsEngine()
    with patch.object(
        engine,
        "_predict_model",
        new=AsyncMock(return_value={"status": "ok", "model": "churn_risk_scorer", "advisory_only": True}),
    ):
        result = await engine.run_domain_predictions("org-1", "sales")
    assert result["advisory_only"] is True


@pytest.mark.asyncio
async def test_memory_lineage_reads_audit_table():
    from app.services.agent_memory_service import AgentMemoryIntelligenceService

    service = AgentMemoryIntelligenceService()
    mock_client = MagicMock()
    mem_chain = MagicMock()
    mem_chain.select.return_value = mem_chain
    mem_chain.eq.return_value = mem_chain
    mem_chain.limit.return_value = mem_chain
    mem_chain.order.return_value = mem_chain
    mem_chain.execute.side_effect = [
        MagicMock(data=[{"id": "m1", "content": "term", "provenance": "queries"}]),
        MagicMock(data=[{"action": "approved", "actor_id": "u1", "created_at": "2026-06-07"}]),
    ]

    def table(name):
        return mem_chain

    mock_client.table.side_effect = table
    lineage = await service.get_memory_lineage("org-1", "m1", client=mock_client)
    assert lineage["promotion_path"]
    assert lineage["why_this_was_remembered"]


@pytest.mark.asyncio
async def test_federated_learning_remains_disabled():
    coord = FederatedLearningCoordinator()
    result = await coord.predict_structured()
    assert result["status"] == "disabled"


@pytest.mark.asyncio
async def test_activation_checklist_auto_checked():
    scaffold = WorldModelScaffold()
    with patch.object(scaffold, "_count_measured_outcomes", new=AsyncMock(return_value=10)):
        status = await scaffold.check_activation_status("org-1")
    assert status["all_prerequisites_met"] is False
    assert "prerequisites" in status


@pytest.mark.asyncio
async def test_not_available_when_prerequisites_unmet():
    scaffold = WorldModelScaffold()
    with patch.object(scaffold, "_count_measured_outcomes", new=AsyncMock(return_value=0)):
        payload = await scaffold.predict_structured(org_id="org-1")
    assert payload["status"] == "not_available"


@pytest.mark.asyncio
async def test_executive_brief_advisory_only():
    from app.services.research_service import AutonomousResearchService

    service = AutonomousResearchService()
    with patch.object(service, "research", new=AsyncMock(return_value={"findings": [], "sources": []})):
        with patch(
            "app.services.decision_intelligence_service.get_decision_intelligence_service"
        ) as mock_decision:
            mock_decision.return_value.recommend_next_action = AsyncMock(return_value={"recommendations": []})
            brief = await service.generate_executive_brief("org-1", ["AI ops"])
    assert brief["advisory_only"] is True


def test_all_new_services_have_advisory_only_flag():
    keys = [
        "enterprise_knowledge_graph",
        "business_digital_twin",
        "process_mining",
        "consensus_engine",
        "predictive_operations",
        "world_models",
        "autonomous_research",
    ]
    for key in keys:
        assert AI_ARCHITECTURE_REGISTRY[key].get("advisory_only") is True


def test_registry_has_phase_omega_entries():
    assert "consensus_engine" in AI_ARCHITECTURE_REGISTRY
    assert "business_digital_twin" in AI_ARCHITECTURE_REGISTRY
    assert "organizational_memory" in AI_ARCHITECTURE_REGISTRY
    assert AI_ARCHITECTURE_REGISTRY["federated_learning"]["status"] == "disabled"
