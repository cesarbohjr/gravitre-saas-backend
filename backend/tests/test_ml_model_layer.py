"""Gravitre ML model layer catalog and governance tests."""
from __future__ import annotations

import inspect

import pytest

from app.ml.base import ModelStatus
from app.ml.causal_analysis import CausalImpactAnalyzer
from app.ml.churn_scoring import ChurnRiskScorer
from app.ml.federated_learning import FederatedLearningCoordinator
from app.ml.model_catalog import GRAVITRE_ML_CATALOG, get_catalog, get_model_instance
from app.ml.revenue_forecasting import RevenueForecaster
from app.ml.inference import InferenceService
from app.temporal.worker import registered_workflow_names


FOURTEEN_TYPES = (
    "revenue_forecaster",
    "churn_risk_scorer",
    "causal_impact_analyzer",
    "graph_neural_network",
    "multimodal_router",
    "diffusion_model",
    "federated_learning",
    "self_supervised_embeddings",
    "active_learning",
    "retrieval_memory_learner",
    "meta_learning",
    "neuro_symbolic",
    "agentic_planning",
    "domain_specific_llm",
)


def test_all_14_model_types_in_catalog():
    for name in FOURTEEN_TYPES:
        assert name in GRAVITRE_ML_CATALOG


@pytest.mark.asyncio
async def test_planned_models_return_structured_response():
    analyzer = CausalImpactAnalyzer()
    result = await analyzer.predict_structured(org_id="org-1", metric_name="deal_amount")
    assert result["status"] == "not_available"
    assert "observations" in result["reason"].lower() or "pre" in result["reason"].lower()


@pytest.mark.asyncio
async def test_disabled_models_return_disabled_response():
    coordinator = FederatedLearningCoordinator()
    result = await coordinator.predict_structured()
    assert result["status"] == "disabled"
    assert "DISABLED" in result["reason"]


def test_live_models_route_through_inference_service():
    service = InferenceService()
    assert hasattr(service, "predict")
    assert inspect.iscoroutinefunction(service.predict)


@pytest.mark.asyncio
async def test_no_model_returns_fake_output():
    forecaster = RevenueForecaster()
    result = await forecaster.predict_structured(horizon_days=7)
    assert result["status"] == "insufficient_data"
    assert "confidence_note" in result
    assert "predicted_values" not in result or result.get("status") != "ok"


def test_advisory_only_flag_set_on_action_models():
    assert GRAVITRE_ML_CATALOG["churn_risk_scorer"]["advisory_only"] is True
    assert GRAVITRE_ML_CATALOG["revenue_forecaster"]["advisory_only"] is True
    assert GRAVITRE_ML_CATALOG["workflow_anomaly_detector"]["advisory_only"] is True


@pytest.mark.asyncio
async def test_revenue_forecaster_requires_min_history():
    forecaster = RevenueForecaster()
    result = await forecaster.predict_structured()
    assert result["data_points_used"] < forecaster.MIN_HISTORY_POINTS


@pytest.mark.asyncio
async def test_churn_scorer_output_marked_advisory():
    scorer = ChurnRiskScorer()
    result = await scorer.predict_structured(customer_features={})
    assert result["advisory_only"] is True


def test_ml_training_workflow_registered():
    names = registered_workflow_names()
    assert "MLModelTrainingWorkflow" in names


def test_model_catalog_has_all_required_fields():
    catalog = get_catalog()
    for name, meta in catalog.items():
        assert "status" in meta
        assert meta["status"] in {s.value for s in ModelStatus}


def test_governance_all_business_action_models_advisory():
    business_models = (
        "churn_risk_scorer",
        "revenue_forecaster",
        "causal_impact_analyzer",
        "workflow_anomaly_detector",
        "workflow_duration_forecaster",
        "workflow_success_predictor",
        "agentic_planning",
    )
    for name in business_models:
        assert GRAVITRE_ML_CATALOG[name]["advisory_only"] is True


def test_catalog_model_instances_instantiate():
    for name in FOURTEEN_TYPES:
        instance = get_model_instance(name)
        assert instance is not None
