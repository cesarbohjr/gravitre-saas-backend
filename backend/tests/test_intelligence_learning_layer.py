"""Tests for Gravitre Intelligence Engine learning and evaluation layer."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.learning_layer_registry import LEARNING_LAYER_REGISTRY
from app.ml.model_catalog import GRAVITRE_ML_CATALOG
from app.orchestration_registry import ORCHESTRATION_REGISTRY
from app.services.ai_trust_layer import AITrustLayer, get_ai_trust_layer
from app.services.intelligence_evaluation_service import IntelligenceEvaluationService
from app.services.model_router import ModelRouter, get_model_router
from app.services.outcome_learning_service import OUTCOME_EVENTS, OutcomeLearningService
from app.services.outcome_tracker import OutcomeTracker
from app.services.risk_approval_evaluator import RiskApprovalEvaluator
from app.services.simulation_service import SimulationService
from app.services.training_signal_service import TrainingSignalService


def test_learning_layer_registry_has_thirteen_components():
    assert len(LEARNING_LAYER_REGISTRY) == 13


@pytest.mark.asyncio
async def test_record_recommendation_outcome_valid_event():
    service = OutcomeLearningService()
    with patch.object(service, "_insert_event", AsyncMock()) as insert:
        await service.record_recommendation_outcome(
            "org-1",
            "rec-1",
            "recommendation_created",
            confidence_score=0.8,
        )
    insert.assert_awaited_once()


@pytest.mark.asyncio
async def test_record_recommendation_outcome_invalid_event_rejected():
    service = OutcomeLearningService()
    with pytest.raises(ValueError, match="Invalid outcome_event"):
        await service.record_recommendation_outcome("org-1", "rec-1", "not_a_real_event")


@pytest.mark.asyncio
async def test_prediction_outcome_pending_when_window_open():
    service = OutcomeLearningService()
    with patch(
        "app.temporal.starters.start_outcome_measurement_workflow",
        AsyncMock(),
    ):
        result = await service.record_prediction_outcome(
            "org-1",
            "pred-1",
            "workflow_anomaly_detector",
            0.9,
            None,
            "prediction_generated",
        )
    assert result["measurement_status"] == "pending_measurement"


@pytest.mark.asyncio
async def test_outcome_score_returns_insufficient_data_below_minimum():
    service = OutcomeLearningService()
    with patch.object(service, "_fetch_events", AsyncMock(return_value=[{"outcome_event": "workflow_executed"}])):
        score = await service.calculate_outcome_score("org-1", "agent", "agent-1")
    assert score["status"] == "insufficient_data"


@pytest.mark.asyncio
async def test_outcome_tracker_never_blocks_response():
    tracker = OutcomeTracker()
    with patch.object(asyncio, "create_task") as create_task:
        tracker.track("org-1", None, "msg-1", None, {"confidence": 0.5}, {"intent": "question"})
    create_task.assert_called()


@pytest.mark.asyncio
async def test_advisory_only_models_never_trigger_actions():
    evaluator = RiskApprovalEvaluator()
    with patch("app.services.risk_approval_evaluator.get_supabase_client", return_value=MagicMock()):
        with patch("app.services.risk_approval_evaluator.assert_org_not_blocked"):
            result = await evaluator.evaluate(
                "org-1",
                "user-1",
                {"type": "read_only"},
                {"risk_level": "low"},
                {"advisory_only": True, "requires_approval_for": ["all_actions"]},
            )
    assert result["requires_approval"] is True


@pytest.mark.asyncio
async def test_outcome_dual_write_postgres_and_clickhouse():
    service = OutcomeLearningService()
    with patch.object(service, "_client") as client_mock:
        client_mock.return_value.table.return_value.insert.return_value.execute.return_value = MagicMock()
        with patch.object(service, "_mirror_clickhouse") as mirror:
            await service.record_workflow_outcome("org-1", "wf-1", "run-1", "workflow_executed")
    mirror.assert_called_once()


@pytest.mark.asyncio
async def test_no_fake_outcomes_written():
    service = OutcomeLearningService()
    result = await service.record_prediction_outcome(
        "org-1",
        "pred-1",
        "revenue_forecaster",
        100.0,
        None,
        "prediction_generated",
        measurement_available=False,
    )
    assert result["measurement_status"] == "insufficient_data"


@pytest.mark.asyncio
async def test_ml_evaluation_returns_pending_when_no_actual_value():
    svc = IntelligenceEvaluationService()
    result = await svc.evaluate_ml_prediction("org-1", "revenue_forecaster", 100.0, None, "forecast")
    assert result["evaluation_status"] == "pending_measurement"


@pytest.mark.asyncio
async def test_benchmark_returns_not_configured_when_empty():
    svc = IntelligenceEvaluationService()
    result = await svc.run_benchmark("org-1", "marketing")
    assert result["benchmark_status"] == "not_configured"


@pytest.mark.asyncio
async def test_compare_models_requires_min_evaluations():
    svc = IntelligenceEvaluationService()
    with patch.object(svc._outcomes, "_fetch_events", AsyncMock(return_value=[])):
        result = await svc.compare_models_for_task("org-1", "data_analysis")
    assert result["status"] == "insufficient_data"


@pytest.mark.asyncio
async def test_evaluate_agent_run_org_scoped():
    svc = IntelligenceEvaluationService()
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[{"id": "job-1", "status": "completed", "org_id": "org-1", "agent_id": "agent-1"}]
    )
    with patch.object(svc, "_client", return_value=client):
        result = await svc.evaluate_agent_run("org-1", "agent-1", "job-1")
    assert result["evaluation_status"] == "complete"


@pytest.mark.asyncio
async def test_confidence_routing_fast_when_high():
    router = get_model_router()
    routed = await router.route_with_confidence("classification", 0.9)
    assert routed["tier"] == "low"
    assert routed["escalate_to_human"] is False


@pytest.mark.asyncio
async def test_confidence_routing_escalates_when_low():
    router = get_model_router()
    routed = await router.route_with_confidence("decision_reasoning", 0.2)
    assert routed["escalate_to_human"] is True


@pytest.mark.asyncio
async def test_historical_routing_falls_back_when_no_history():
    router = get_model_router()
    eval_svc = MagicMock()
    eval_svc.recommend_best_model_for_task = AsyncMock(return_value={"status": "insufficient_data"})
    routed = await router.route_with_historical_performance("data_analysis", None, "org-1", eval_svc)
    assert routed["source"] == "default_routing"


@pytest.mark.asyncio
async def test_outcome_routing_deprioritizes_poor_performers():
    router = get_model_router()
    outcome_svc = MagicMock()
    outcome_svc.get_model_outcome_score = AsyncMock(return_value={"status": "ok", "score": 0.1})
    with patch("app.services.model_selector.get_model_selector") as selector_mock:
        selector_mock.return_value.select = AsyncMock(return_value={"primary_model": "llm", "ml_model_name": "intent_classifier"})
        routed = await router.route_with_outcome_score("data_analysis", None, "org-1", outcome_svc)
    assert routed.get("deprioritized") is True


def test_should_escalate_to_human_high_risk():
    router = get_model_router()
    assert router.should_escalate_to_human(0.9, "high") is True


def test_routing_explanation_never_exposes_chain_of_thought():
    router = get_model_router()
    text = router.explain_routing_decision("claude-sonnet-4-6", "finance", 0.71, {"historical_score": 0.82})
    assert "chain" not in text.lower()
    assert "weight" not in text.lower()


@pytest.mark.asyncio
async def test_multistep_fallback_max_attempts_enforced():
    router = get_model_router()
    routed = await router.route_with_multistep_fallback("decision_reasoning", 0.1, attempts=2, max_attempts=2)
    assert routed["escalate_to_human"] is True


@pytest.mark.asyncio
async def test_simulation_returns_insufficient_data_when_no_history():
    sim = SimulationService()
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
    with patch.object(sim, "_client", return_value=client):
        result = await sim.simulate_campaign_change("org-1", {})
    assert result["simulation_status"] == "insufficient_data"


@pytest.mark.asyncio
async def test_bulk_update_always_approval_required():
    sim = SimulationService()
    result = await sim.simulate_bulk_update("org-1", {"record_count": 500})
    assert result["approval_required"] is True
    assert result["reversible"] is False


@pytest.mark.asyncio
async def test_connector_write_always_approval_required():
    sim = SimulationService()
    result = await sim.simulate_connector_write("org-1", {"connector_id": "c-1", "action_name": "update"})
    assert result["approval_required"] is True


@pytest.mark.asyncio
async def test_compare_scenarios_handles_partial_failure():
    sim = SimulationService()
    with patch.object(sim, "simulate_action", AsyncMock(side_effect=[{"simulation_status": "ready"}, Exception("fail")])):
        result = await sim.compare_action_scenarios(
            "org-1",
            [
                {"action_type": "crm_bulk_update", "params": {}},
                {"action_type": "bad", "params": {}},
            ],
        )
    assert len(result["scenarios"]) == 1


@pytest.mark.asyncio
async def test_irreversible_actions_flagged_correctly():
    sim = SimulationService()
    result = await sim.simulate_bulk_update("org-1", {})
    assert result["reversible"] is False


def test_wrap_response_backward_compatible_no_new_required_args():
    layer = AITrustLayer()
    result = layer.wrap_response("answer", [], 0.8, None, [], [], True)
    assert result["answer"] == "answer"
    assert "source_breakdown" in result


@pytest.mark.asyncio
async def test_prediction_explanation_always_has_confidence_note():
    layer = get_ai_trust_layer()
    text = await layer.generate_prediction_explanation("revenue_forecaster", 0.6, 10, "correlational only")
    assert "correlational only" in text


@pytest.mark.asyncio
async def test_missing_context_warning_fires_below_threshold():
    layer = get_ai_trust_layer()
    warning = await layer.generate_missing_context_warning(["HubSpot deals"], 0.4)
    assert "Low confidence" in warning


def test_action_safety_never_hides_high_risk():
    layer = get_ai_trust_layer()
    text = layer.generate_action_safety_explanation("crm_bulk_update", "high", True, {"simulation_status": "ready", "reversible": False})
    assert "approval" in text.lower()
    assert "irreversible" in text.lower()


@pytest.mark.asyncio
async def test_remember_workflow_outcome_routes_to_pending_approval():
    from app.services import agent_memory_service

    client = MagicMock()
    client.table.return_value.insert.return_value.execute.return_value = MagicMock(
        data=[{"id": "m-1", "agent_id": "a-1", "content": "x", "category": "pattern", "confidence": 70, "usage_count": 0, "editable": True}]
    )
    with patch.object(agent_memory_service, "ensure_agent_in_org", return_value={"id": "a-1"}):
        with patch("app.services.agent_memory_service.get_embedding", return_value=[0.1]):
            await agent_memory_service.remember_workflow_outcome(
                MagicMock(), client, "org-1", "a-1", "wf-1", "success", "insight"
            )
    client.table.return_value.insert.assert_called()


@pytest.mark.asyncio
async def test_agent_memory_cross_org_isolation():
    from fastapi import HTTPException
    from app.services import agent_memory_service

    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
    with pytest.raises(HTTPException):
        agent_memory_service.ensure_agent_in_org(client, "org-1", "missing-agent")


@pytest.mark.asyncio
async def test_update_from_outcome_fire_and_forget():
    from app.services import agent_memory_service

    with patch("asyncio.create_task") as create_task:
        await agent_memory_service.update_agent_memory_from_outcome(
            MagicMock(),
            MagicMock(),
            "org-1",
            "agent-1",
            "workflow_executed",
            {"workflow_id": "wf-1", "key_insight": "ok"},
        )
    create_task.assert_called_once()


def test_no_secrets_in_agent_memory():
    from app.services import agent_memory_service

    text = agent_memory_service.format_retrieval_prompt_section({"memories": [{"content": "safe"}]})
    assert "password" not in text


@pytest.mark.asyncio
async def test_training_readiness_insufficient_data_below_threshold():
    svc = TrainingSignalService()
    with patch.object(svc, "_count_workflow_runs", AsyncMock(return_value=1)):
        with patch.object(svc, "_last_trained_at", AsyncMock(return_value=None)):
            with patch("app.services.training_signal_service.count_training_examples", AsyncMock(return_value=0)):
                with patch(
                    "app.services.company_intelligence_collectors.collect_query_corpus",
                    AsyncMock(return_value=[]),
                ):
                    with patch.object(
                        svc._outcomes,
                        "get_training_signal_candidates",
                        AsyncMock(return_value=[]),
                    ):
                        readiness = await svc.get_training_readiness("org-1")
    assert readiness["by_model"]["workflow_anomaly_detector"]["status"] == "insufficient_data"


@pytest.mark.asyncio
async def test_queue_training_uses_temporal_when_configured():
    svc = TrainingSignalService()
    with patch.object(svc, "export_training_signals", AsyncMock(return_value={"status": "ready", "signals": [{}]})):
        with patch.dict("os.environ", {"TEMPORAL_HOST": "localhost:7233"}, clear=False):
            with patch(
                "app.temporal.starters.start_ml_model_training_workflow",
                AsyncMock(return_value={"temporal": True, "workflow_id": "w-1"}),
            ):
                result = await svc.queue_training_if_threshold_met("org-1", "intent_classifier")
    assert result["status"] == "queued"


@pytest.mark.asyncio
async def test_export_signals_returns_insufficient_when_low():
    svc = TrainingSignalService()
    with patch.object(svc._outcomes, "get_training_signal_candidates", AsyncMock(return_value=[])):
        result = await svc.export_training_signals("org-1", "intent_classifier")
    assert result["status"] == "insufficient_data"


@pytest.mark.asyncio
async def test_no_auto_retrain_outside_scheduled_rules():
    svc = TrainingSignalService()
    with patch.object(svc, "export_training_signals", AsyncMock(return_value={"status": "insufficient_data"})):
        result = await svc.queue_training_if_threshold_met("org-1", "intent_classifier")
    assert result["status"] == "insufficient_data"


def test_all_outcome_events_valid_set():
    assert "recommendation_created" in OUTCOME_EVENTS
    assert len(OUTCOME_EVENTS) == 17


def test_existing_ml_layer_intact():
    assert len(GRAVITRE_ML_CATALOG) >= 10


def test_existing_ai_architecture_layer_intact():
    from app.ai_architecture_registry import AI_ARCHITECTURE_REGISTRY

    assert len(AI_ARCHITECTURE_REGISTRY) >= 10


def test_existing_orchestration_layer_intact():
    assert len(ORCHESTRATION_REGISTRY) == 11


def test_no_new_parallel_systems_created():
    assert "ai_outcomes" not in LEARNING_LAYER_REGISTRY
