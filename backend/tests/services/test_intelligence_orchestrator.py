"""Tests for Wave 0-1 intelligence orchestration layer."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.context_prioritization_engine import ContextPrioritizationEngine, ContextSource
from app.services.conversation_memory_engine import ConversationMemoryEngine
from app.services.execution_confidence_engine import ExecutionConfidenceEngine
from app.services.intelligence_engine_settings import IntelligenceEngineSettings


def test_context_prioritization_prefers_rag_for_search_intent():
    engine = ContextPrioritizationEngine()
    sources = [
        ContextSource("org", "org_context", "Org", 0.0, "org data"),
        ContextSource("rag", "rag", "Knowledge", 0.0, "knowledge data"),
    ]
    profile = engine.build_context_profile(
        raw_sources=sources,
        classification={"intent": "knowledge_lookup", "requires_action": False},
    )
    assert profile.ranked_sources[0].source_type == "rag"
    explanation = engine.explain_context_used(profile)
    assert "Knowledge" in explanation or "context source" in explanation


@pytest.mark.asyncio
async def test_conversation_memory_records_rejection():
    engine = ConversationMemoryEngine()
    engine._state = MagicMock()
    engine._state.get_task_state = AsyncMock(return_value={})
    engine._state.update_task_state = AsyncMock()
    await engine.record_rejection("conv-1", "org-1", "Build a workflow for stale deals")
    engine._state.update_task_state.assert_awaited()


def test_execution_confidence_blends_context_and_rag():
    engine = ExecutionConfidenceEngine()
    result = engine.assess_response(
        query="What is our pipeline?",
        answer="Pipeline has 12 open deals.",
        rag_sources=[{"content": "12 deals", "score": 0.9}],
        context_profile={
            "sourcesUsed": [
                {"type": "org_context", "score": 0.8},
                {"type": "rag", "score": 0.9},
            ]
        },
    )
    assert result["score"] >= 0.4
    assert "confidence" in result["reason"].lower() or "Confidence" in result["reason"]


@pytest.mark.asyncio
async def test_intelligence_orchestrator_prepare_turn():
    from app.services.intelligence_orchestrator import IntelligenceOrchestrator

    orchestrator = IntelligenceOrchestrator()
    mock_retrieval = SimpleNamespace(
        rag_sources=[{"content": "doc", "score": 0.8}],
        rag_section="<knowledge_base>doc</knowledge_base>",
        memory_section="",
        memory_context={},
        retrieval_plan={},
        org_context={"connectedIntegrations": ["hubspot"]},
        sources=[],
        graph_context={},
    )

    with patch.object(orchestrator._memory_engine, "build_context_profile", AsyncMock(return_value={"prompt_section": "", "memory": {}, "relevant": {}, "suppressed_suggestion_keys": []})), patch.object(
        orchestrator._retrieval,
        "retrieve",
        AsyncMock(return_value=mock_retrieval),
    ), patch(
        "app.services.intelligence_orchestrator.get_org_context_service",
    ) as org_service, patch(
        "app.services.intelligence_orchestrator.get_company_intelligence_orchestrator",
    ) as company_orchestrator, patch(
        "app.services.intelligence_orchestrator.build_entity_context_section",
        AsyncMock(return_value=""),
    ), patch.object(
        orchestrator._signals,
        "collect_signals",
        AsyncMock(return_value={"signals": []}),
    ), patch.object(
        orchestrator._planning,
        "should_plan",
        AsyncMock(return_value=False),
    ), patch.object(
        orchestrator._registry,
        "list_connected_integrations",
        return_value=["hubspot"],
    ):
        org_service.return_value.get_context_bundle.return_value = ({}, "org markdown")
        company_orchestrator.return_value.get_context_for_prompt = AsyncMock(return_value="company intel")
        turn = await orchestrator.prepare_assistant_turn(
            org_id="org-1",
            user_id="user-1",
            conversation_id="conv-1",
            query="Search HubSpot for Acme",
            classification={"intent": "crm_lookup", "department": "sales", "classification_confidence": 0.7},
            client=MagicMock(),
            agent_id=None,
            environment_name="default",
            engine_settings=IntelligenceEngineSettings(max_chunks=8, validation_enabled=False),
            task_state={},
            persona={},
        )

    assert turn.retrieval is mock_retrieval
    assert turn.context_profile.get("sourcesUsed")
    assert turn.context_explanation
    assert isinstance(turn.explainability, dict)
    assert isinstance(turn.execution_gate, dict)
    assert isinstance(turn.working_memory, dict)
    assert "long_term" in turn.working_memory
    assert isinstance(turn.operational_envelope, dict)
    assert turn.operational_envelope.get("whatHappened")
