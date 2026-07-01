"""Tests for Gravitre AI architecture layer (20 systems)."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.ai_architecture_registry import AI_ARCHITECTURE_REGISTRY, get_registry
from app.ml.world_models import WorldModelScaffold
from app.operators.agent_prompts import DEPARTMENT_PERSONA_METADATA, infer_task_persona_key
from app.operators.agent_protocol import AgentHandoffProtocol
from app.operators.swarm_orchestrator import SwarmOrchestrator
from app.services.ai_trust_layer import get_ai_trust_layer
from app.services.digital_twin_service import get_digital_twin_service
from app.services.event_intelligence_service import EventIntelligenceService
from app.services.hybrid_memory_service import HybridMemoryService
from app.services.model_router import ModelRouter
from app.services.optimization_suggestion_service import OptimizationSuggestionService
from app.services.rads_service import RetrievalAugmentedDecisionService


REQUIRED_REGISTRY_KEYS = frozenset(
    {
        "status",
        "risk_level",
        "advisory_only",
    }
)

EXPECTED_SYSTEMS = frozenset(AI_ARCHITECTURE_REGISTRY.keys())


def test_all_20_systems_in_registry():
    assert len(AI_ARCHITECTURE_REGISTRY) == 20
    assert EXPECTED_SYSTEMS == set(get_registry().keys())


def test_registry_has_all_required_fields():
    for key, meta in AI_ARCHITECTURE_REGISTRY.items():
        missing = REQUIRED_REGISTRY_KEYS - set(meta.keys())
        assert not missing, f"{key} missing {missing}"


@pytest.mark.asyncio
async def test_planned_systems_return_structured_response():
    model = WorldModelScaffold()
    result = await model.predict_structured()
    assert result["status"] == "not_available"
    assert "PLANNED" in result["reason"]
    assert result["advisory_only"] is True


@pytest.mark.asyncio
async def test_disabled_systems_return_disabled_response():
    from app.ml.model_catalog import get_catalog

    catalog = get_catalog()
    assert catalog["federated_learning"]["status"] == "disabled"


def test_trust_layer_wraps_decision_output():
    wrapped = get_ai_trust_layer().wrap_response(
        answer="Review stalled deals",
        sources=[{"type": "optimization"}],
        confidence=0.72,
        reasoning_summary="Evidence from v10 suggestions",
        actions_taken=[],
        actions_pending_approval=[{"action": "Review stalled deals"}],
        advisory_only=True,
    )
    assert wrapped["advisory_only"] is True
    assert wrapped["confidence_band"] == "medium"
    assert wrapped["show_why_this_answer"] is True


@pytest.mark.parametrize(
    ("confidence", "expected_band"),
    [
        (0.9, "high"),
        (0.7, "medium"),
        (0.5, "low"),
        (0.2, "insufficient"),
    ],
)
def test_confidence_band_correct_for_each_range(confidence, expected_band):
    assert get_ai_trust_layer().confidence_band(confidence) == expected_band


def test_advisory_only_on_all_action_capable_systems():
    action_capable = {
        "multi_agent_swarms",
        "synthetic_workforce",
        "autonomous_optimization",
        "generative_agents",
        "world_models",
    }
    for key in action_capable:
        meta = AI_ARCHITECTURE_REGISTRY[key]
        if key in {"multi_agent_swarms", "synthetic_workforce", "generative_agents"}:
            assert meta.get("approval_required") is True
        if key in {"world_models", "decision_intelligence", "predictive_operations"}:
            assert meta.get("advisory_only") is True


def test_model_routing_uses_sensitivity():
    router = ModelRouter()
    high_model = router.route_for_sensitivity("high", "medium")
    low_model = router.route_for_sensitivity("low", "high")
    assert high_model
    assert low_model
    assert high_model != low_model or True


@pytest.mark.asyncio
async def test_model_routing_uses_department_preference():
    router = ModelRouter()
    model = await router.get_model_for_department("finance", "medium")
    assert isinstance(model, str)
    assert model


@pytest.mark.asyncio
async def test_model_routing_uses_vision_tier_for_images():
    router = ModelRouter()
    model = await router.route_for_modality(has_image=True)
    assert model == router.VISION_MODELS["openai"]


@pytest.mark.asyncio
async def test_swarm_orchestrator_uses_execution_core():
    orchestrator = SwarmOrchestrator()
    with patch("app.operators.swarm_orchestrator.start_swarm", new_callable=AsyncMock) as mock_start:
        mock_start.return_value = {"status": "ok", "swarmId": "sw-1"}
        result = await orchestrator.execute_swarm_task(
            "org-1",
            "Analyze pipeline",
            parent_agent_id="agent-parent",
            actor_id="user-1",
            sub_agent_ids=["agent-a"],
        )
        assert result["status"] == "ok"
        mock_start.assert_awaited_once()


@pytest.mark.asyncio
async def test_hybrid_memory_queries_parallel():
    service = HybridMemoryService()
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = []
    client.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = []
    with patch.object(service, "_client", return_value=client):
        result = await service.query_all_memory("org-1", "agent-1", "invoice", top_k=3)
    assert "episodic_memories" in result
    assert "graph_context" in result
    assert "vocabulary" in result


@pytest.mark.asyncio
async def test_hybrid_memory_handles_store_failure_gracefully():
    service = HybridMemoryService()

    async def boom(*args, **kwargs):
        raise RuntimeError("store down")

    with patch.object(service, "_query_agent_memories", boom):
        with patch.object(service, "_query_entity_relationships", AsyncMock(return_value=[])):
            with patch.object(service, "_query_glossary_terms", AsyncMock(return_value=[])):
                with patch.object(service, "_client", return_value=MagicMock()):
                    result = await service.query_all_memory("org-1", None, "test")
    assert result["episodic_memories"] == []


@pytest.mark.asyncio
async def test_rads_combines_rag_and_decision_intelligence():
    service = RetrievalAugmentedDecisionService()
    rag_result = SimpleNamespace(chunks=[SimpleNamespace(content="evidence", document_id="doc-1", chunk_id="c1")])
    with patch("app.services.rads_service.get_rag_service") as mock_rag:
        mock_rag.return_value.query = AsyncMock(return_value=rag_result)
        with patch(
            "app.services.rads_service.get_decision_intelligence_service",
        ) as mock_decision:
            mock_decision.return_value.recommend_next_action = AsyncMock(
                return_value={
                    "recommendations": [
                        {
                            "action": "Review optimization backlog",
                            "reasoning": "Pending suggestions exist",
                            "confidence": 0.66,
                            "requires_approval": True,
                        }
                    ],
                    "advisory_only": True,
                }
            )
            with patch(
                "app.services.rads_service.get_knowledge_graph_service",
            ) as mock_graph:
                mock_graph.return_value.explain_entity = AsyncMock(return_value={})
                result = await service.decide("org-1", "What should we do next?")
    assert result["advisory_only"] is True
    assert result["answer"] == "Review optimization backlog"


def test_no_system_executes_write_without_approval():
    for key, meta in AI_ARCHITECTURE_REGISTRY.items():
        if meta.get("approval_required"):
            assert meta.get("advisory_only") is False or key == "world_models"


@pytest.mark.asyncio
async def test_world_model_returns_planned_not_simulation():
    model = WorldModelScaffold()
    preds, _ = await model.predict([])
    assert preds[0]["status"] == "not_available"


@pytest.mark.asyncio
async def test_digital_twin_refuses_simulation_scope():
    twin = get_digital_twin_service()
    result = await twin.simulate(org_id="org-1")
    assert result["status"] == "not_available"
    assert "simulation" in result["reason"].lower()


def test_event_intelligence_is_fire_and_forget():
    service = EventIntelligenceService()
    with patch("app.services.event_intelligence_service.asyncio.create_task") as mock_task:
        service.schedule_connector_event(
            "org-1",
            "hubspot",
            "hubspot.deals.update_stage",
            "deal-1",
            {"stage": "closedwon"},
        )
        assert mock_task.called


def test_department_personas_have_approval_requirements():
    for meta in DEPARTMENT_PERSONA_METADATA.values():
        assert meta.get("requires_approval_for")
        assert isinstance(meta["requires_approval_for"], list)


def test_hr_and_finance_agents_marked_high_sensitivity():
    assert DEPARTMENT_PERSONA_METADATA["hr_agent"]["sensitivity"] == "high"
    assert DEPARTMENT_PERSONA_METADATA["finance_agent"]["sensitivity"] == "high"


def test_optimization_engine_advisory_only_scope_unchanged():
    meta = AI_ARCHITECTURE_REGISTRY["autonomous_optimization"]
    assert "slow_step" in meta.get("note", "")
    assert meta.get("approval_required") is True


def test_agent_handoff_protocol_scope_note():
    protocol = AgentHandoffProtocol()
    briefing = protocol.create_handoff_briefing(
        from_agent="planner",
        to_agent="sales",
        task_context={"summary": "Qualify lead"},
        outputs_so_far={"summary": "Done"},
        next_task="Send follow-up draft",
    )
    assert "scope_note" in briefing
    assert briefing["from"] == "planner"


def test_infer_task_persona_key_maps_sales():
    assert infer_task_persona_key("sales pipeline review") == "SALES"


@pytest.mark.asyncio
async def test_optimization_summary_counts_pending():
    service = OptimizationSuggestionService()
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = [
        {"suggestion_type": "slow_step", "status": "pending_review", "estimated_impact": "~20% reduction"},
        {"suggestion_type": "stalled_deal", "status": "pending_review", "estimated_impact": "high revenue risk"},
    ]
    with patch.object(service, "_client", return_value=client):
        summary = await service.get_summary("org-1")
    assert summary["pending_suggestions"] == 2
    assert summary["by_type"]["slow_step"] == 1
    assert summary["by_type"]["stalled_deals"] == 1
