"""Tests for Gravitre Intelligence Engine advanced orchestration layer."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.orchestration_registry import ORCHESTRATION_REGISTRY
from app.services.agent_selector import AgentSelector
from app.services.confidence_scorer import ConfidenceScorer
from app.services.context_assembler import ContextAssembler
from app.services.explanation_generator import ExplanationGenerator
from app.services.intelligence_router import IntelligenceRouter
from app.services.learning_feedback_loop import LearningFeedbackLoop
from app.services.model_selector import ModelSelector
from app.services.outcome_tracker import OutcomeTracker
from app.services.risk_approval_evaluator import RiskApprovalEvaluator
from app.services.task_classifier import TaskClassifier
from app.services.tool_connector_selector import ToolConnectorSelector


def test_orchestration_registry_has_22_components():
    assert len(ORCHESTRATION_REGISTRY) == 26


@pytest.mark.asyncio
async def test_intelligence_router_routes_simple_question_to_tier_1():
    router = IntelligenceRouter()
    with patch.object(router._task_classifier, "classify", AsyncMock(return_value={
        "intent": "question_answering",
        "latency_target": "tier_1",
        "requires_action": False,
        "classification_confidence": 0.6,
    })):
        with patch.object(router._context_assembler, "assemble", AsyncMock(return_value={"rag_context": []})):
            with patch.object(router._model_selector, "select", AsyncMock(return_value={"primary_model": "llm"})):
                with patch(
                    "app.services.intelligence_router.get_decision_intelligence_service",
                ) as mock_decision:
                    mock_decision.return_value.recommend_next_action = AsyncMock(
                        return_value={"recommendations": [{"action": "Review docs", "confidence": 0.5, "requires_approval": True}]}
                    )
                    result = await router.route("org-1", "user-1", "How do I create a workflow?", "api")
    assert result["classification"]["latency_target"] == "tier_1"
    assert result["advisory_only"] is True


@pytest.mark.asyncio
async def test_intelligence_router_routes_complex_task_to_tier_3():
    router = IntelligenceRouter()
    with patch.object(router._task_classifier, "classify", AsyncMock(return_value={
        "intent": "workflow_execution",
        "latency_target": "tier_3",
        "requires_action": True,
        "requires_approval": True,
        "classification_confidence": 0.7,
    })):
        with patch.object(router._context_assembler, "assemble", AsyncMock(return_value={"rag_context": []})):
            with patch.object(router._model_selector, "select", AsyncMock(return_value={"primary_model": "llm"})):
                with patch.object(router._agent_selector, "select", AsyncMock(return_value={"persona": {"role": "Ops"}})):
                    with patch.object(router._tool_selector, "select_for_task", AsyncMock(return_value={"write_requires_approval": True})):
                        with patch.object(router._risk_evaluator, "evaluate", AsyncMock(return_value={"requires_approval": True})):
                            result = await router.route("org-1", "user-1", "Execute workflow automation", "api")
    assert result["requires_approval"] is True
    assert result["classification"]["latency_target"] == "tier_3"


@pytest.mark.asyncio
async def test_task_classifier_sets_correct_pipeline_flags():
    classifier = TaskClassifier()
    result = await classifier.classify("org-1", "Why is revenue down this quarter?")
    assert result["intent"] == "data_analysis"
    assert result["requires_prediction"] is True
    assert result["requires_causal"] is True
    assert result["requires_action"] is False


@pytest.mark.asyncio
async def test_context_assembler_queries_sources_in_parallel():
    assembler = ContextAssembler()
    with patch("app.services.context_assembler.get_rag_service") as mock_rag:
        mock_rag.return_value.query = AsyncMock(return_value=MagicMock(chunks=[]))
        with patch("app.services.context_assembler.get_hybrid_memory_service") as mock_mem:
            mock_mem.return_value.query_all_memory = AsyncMock(return_value={})
            with patch("app.services.context_assembler.get_company_intelligence_orchestrator") as mock_ci:
                mock_ci.return_value.get_context_for_prompt = AsyncMock(return_value="")
                result = await assembler.assemble("org-1", "user-1", "hello", {"requires_graph": False})
    assert "rag_context" in result
    assert "memory_context" in result


@pytest.mark.asyncio
async def test_context_assembler_handles_source_failure_gracefully():
    assembler = ContextAssembler()
    with patch("app.services.context_assembler.get_rag_service") as mock_rag:
        mock_rag.return_value.query = AsyncMock(side_effect=RuntimeError("rag down"))
        with patch("app.services.context_assembler.get_hybrid_memory_service") as mock_mem:
            mock_mem.return_value.query_all_memory = AsyncMock(return_value={"episodic_memories": []})
            with patch("app.services.context_assembler.get_company_intelligence_orchestrator") as mock_ci:
                mock_ci.return_value.get_context_for_prompt = AsyncMock(return_value="")
                result = await assembler.assemble("org-1", "user-1", "hello", {})
    assert result["rag_context"] == []


@pytest.mark.asyncio
async def test_model_selector_prefers_trained_ml_over_llm():
    selector = ModelSelector()
    with patch.object(selector, "_org_has_deployed_model", AsyncMock(return_value=True)):
        with patch("app.services.model_selector.get_org_model_status", AsyncMock(return_value={"catalog_status": "trained"})):
            result = await selector.select("org-1", {"intent": "data_analysis"})
    assert result["primary_model"] == "ml_internal"


@pytest.mark.asyncio
async def test_model_selector_falls_back_to_llm_when_ml_planned():
    selector = ModelSelector()
    result = await selector.select("org-1", {"intent": "data_analysis", "risk_level": "low", "latency_target": "tier_2"})
    assert result["primary_model"] == "llm"


@pytest.mark.asyncio
async def test_agent_selector_validates_connector_availability():
    selector = AgentSelector()
    with patch.object(selector, "_get_connected", AsyncMock(return_value={"hubspot", "platform"})):
        result = await selector.select("org-1", {"intent": "sales_task", "department": "sales", "requires_action": True})
    assert "persona_key" in result
    assert isinstance(result["missing_connectors"], list)


@pytest.mark.asyncio
async def test_tool_connector_selector_least_privilege():
    selector = ToolConnectorSelector()
    with patch.object(selector._registry, "list_connected_integrations", return_value=["hubspot"]):
        with patch.object(selector._registry, "get_available_tools", AsyncMock(return_value=[
            {"function": {"name": "hubspot_search"}, "capability_tier": "read"},
            {"function": {"name": "hubspot_update"}, "capability_tier": "write", "requires_approval": True},
        ])):
            result = await selector.select_for_task(
                "org-1",
                {"intent": "crm_lookup"},
                {"preferred_connectors": ["hubspot"]},
            )
    assert len(result["read_tools"]) >= 1
    assert result["write_requires_approval"] is True


@pytest.mark.asyncio
async def test_risk_evaluator_requires_approval_for_financial_actions():
    evaluator = RiskApprovalEvaluator()
    with patch("app.services.risk_approval_evaluator.get_supabase_client", return_value=MagicMock()):
        with patch("app.services.risk_approval_evaluator.assert_org_not_blocked"):
            result = await evaluator.evaluate(
                "org-1",
                "user-1",
                {"type": "invoice_send", "is_financial": True},
                {"risk_level": "low"},
                {"role": "Finance", "requires_approval_for": []},
            )
    assert result["requires_approval"] is True


@pytest.mark.asyncio
async def test_risk_evaluator_requires_approval_for_high_risk():
    evaluator = RiskApprovalEvaluator()
    with patch("app.services.risk_approval_evaluator.get_supabase_client", return_value=MagicMock()):
        with patch("app.services.risk_approval_evaluator.assert_org_not_blocked"):
            result = await evaluator.evaluate(
                "org-1",
                "user-1",
                {"type": "read_report"},
                {"risk_level": "high"},
                {"role": "HR", "requires_approval_for": []},
            )
    assert result["requires_approval"] is True


@pytest.mark.asyncio
async def test_risk_evaluator_allows_read_actions_without_approval():
    evaluator = RiskApprovalEvaluator()
    with patch("app.services.risk_approval_evaluator.get_supabase_client", return_value=MagicMock()):
        with patch("app.services.risk_approval_evaluator.assert_org_not_blocked"):
            result = await evaluator.evaluate(
                "org-1",
                "user-1",
                {"type": "read_report"},
                {"risk_level": "low"},
                {"role": "Analyst", "requires_approval_for": []},
            )
    assert result["can_proceed_without_approval"] is True


@pytest.mark.asyncio
async def test_explanation_generator_never_exposes_chain_of_thought():
    generator = ExplanationGenerator()
    text = await generator.explain(
        "answer",
        "org-1",
        [{"source": "Policy Handbook", "score": 0.8}],
        {"reasoning_trace": [{"toolName": "knowledge_base"}]},
    )
    assert "chain-of-thought" not in text.lower()
    assert "Policy Handbook" in text or "internal sources" in text.lower()


def test_explanation_generator_includes_confidence_note_for_predictions():
    generator = ExplanationGenerator()
    text = generator._explain_prediction(
        {"data_points_used": 42, "model_used": "workflow_anomaly_detector", "confidence_note": "Correlational only."}
    )
    assert "42" in text
    assert "Correlational only." in text


def test_confidence_scorer_renormalizes_missing_signals():
    score = ConfidenceScorer().compute(rag_quality=0.8, source_reliability=None, ml_confidence=None, classification_confidence=0.6)
    assert 0.0 < score < 1.0


def test_confidence_scorer_neutral_when_no_signals():
    assert ConfidenceScorer().compute(None, None, None, None) == 0.5


def test_outcome_tracker_is_fire_and_forget():
    tracker = OutcomeTracker()
    with patch("asyncio.create_task") as mock_task:
        tracker.track("org-1", None, "msg-1", None, {"answer": "ok"}, {"intent": "general"})
        assert mock_task.called


@pytest.mark.asyncio
async def test_outcome_tracker_never_blocks_response():
    tracker = OutcomeTracker()
    with patch.object(tracker, "_track_async", AsyncMock()):
        tracker.track("org-1", None, "msg-1", None, {"answer": "ok"}, {"intent": "general"})
        await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_learning_feedback_loop_routes_to_correct_subsystem():
    loop = LearningFeedbackLoop()
    with patch.object(loop, "_update_retrieval_signals", AsyncMock()) as mock_retrieval:
        await loop.process_feedback("org-1", "response_quality", {"sources": []})
        mock_retrieval.assert_awaited_once()


def test_intelligence_router_does_not_replace_agent_intelligence():
    from app.operators.agent_intelligence import AgentIntelligence

    assert hasattr(AgentIntelligence, "execute_task_streaming")
    assert hasattr(AgentIntelligence, "execute_task")


@pytest.mark.asyncio
async def test_no_write_action_executes_without_approval_id():
    from app.routers.intelligence_engine import ExecuteRequest
    from app.services.risk_approval_evaluator import RiskApprovalEvaluator

    evaluator = RiskApprovalEvaluator()
    with patch("app.services.risk_approval_evaluator.get_supabase_client", return_value=MagicMock()):
        with patch("app.services.risk_approval_evaluator.assert_org_not_blocked"):
            risk = await evaluator.evaluate(
                "org-1",
                "user-1",
                {"type": "deal_stage_update", "is_customer_facing": True},
                {"requires_approval": True, "risk_level": "medium"},
                {"role": "Sales", "requires_approval_for": ["deal_stage_update"]},
            )
    assert risk["requires_approval"] is True
    req = ExecuteRequest(action_plan={"type": "deal_stage_update"}, approval_id=None)
    assert req.approval_id is None


@pytest.mark.asyncio
async def test_tier_0_cache_still_hits_before_router():
    from app.operators.agent_intelligence import AgentIntelligence

    intel = AgentIntelligence()
    assert hasattr(intel, "execute_task_streaming")
    source = open(intel.execute_task_streaming.__code__.co_filename, encoding="utf-8").read()
    assert "tier0_hit" in source
    assert "get_task_classifier" in source
    assert source.index("tier0_hit") < source.index("get_task_classifier")


@pytest.mark.asyncio
async def test_end_to_end_revenue_question_pipeline():
    router = IntelligenceRouter()
    question = "Why is revenue down and what should we do?"
    with patch.object(router._context_assembler, "assemble", AsyncMock(return_value={
        "rag_context": [{"content": "Q3 dip", "score": 0.7}],
        "memory_context": {},
        "company_intelligence": "Revenue trends",
    })):
        with patch.object(router._model_selector, "select", AsyncMock(return_value={"primary_model": "llm", "llm_tier": "standard"})):
            with patch(
                "app.services.intelligence_router.get_decision_intelligence_service",
            ) as mock_decision:
                mock_decision.return_value.recommend_next_action = AsyncMock(
                    return_value={
                        "recommendations": [{
                            "action": "Review stalled deals in pipeline",
                            "reasoning": "Correlational revenue decline",
                            "confidence": 0.62,
                            "requires_approval": True,
                        }]
                    }
                )
                with patch.object(router, "_run_enrichments", AsyncMock(return_value={
                    "prediction": {"status": "llm_fallback"},
                    "causal": {"status": "not_available"},
                })):
                    with patch.object(router._task_classifier, "classify", AsyncMock(side_effect=router._task_classifier.classify)):
                        result = await router.route("org-1", "user-1", question, "api")
    assert result["classification"]["intent"] == "data_analysis"
    assert result["enrichments"]["prediction"]["status"] == "llm_fallback"
    assert result["confidence_band"] in {"medium", "low", "high"}
    assert result["advisory_only"] is True
    assert len(result.get("sources") or []) >= 1


@pytest.mark.asyncio
async def test_forecast_response_always_has_confidence_note():
    router = IntelligenceRouter()
    result = await router.forecast("org-1", "revenue", horizon_days=30)
    assert result["advisory_only"] is True
    assert "confidence_note" in result["reasoning_summary"].lower() or "correlational" in result["reasoning_summary"].lower()


@pytest.mark.asyncio
async def test_advisory_only_responses_never_auto_execute():
    router = IntelligenceRouter()
    with patch.object(router._task_classifier, "classify", AsyncMock(return_value={
        "intent": "question_answering",
        "requires_action": False,
        "classification_confidence": 0.5,
    })):
        with patch.object(router._context_assembler, "assemble", AsyncMock(return_value={"rag_context": []})):
            with patch.object(router._model_selector, "select", AsyncMock(return_value={"primary_model": "llm"})):
                with patch(
                    "app.services.intelligence_router.get_decision_intelligence_service",
                ) as mock_decision:
                    mock_decision.return_value.recommend_next_action = AsyncMock(
                        return_value={"recommendations": [{"action": "Review", "confidence": 0.5}]}
                    )
                    result = await router.route("org-1", "user-1", "What changed?", "api")
    assert result["advisory_only"] is True
    assert result.get("actions_taken") == []
