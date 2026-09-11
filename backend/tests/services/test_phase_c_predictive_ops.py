"""Phase C: predictive ops expansion with honest data gates."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.ml.base import ModelStatus
from app.ml.model_catalog import GRAVITRE_ML_CATALOG, get_model_instance
from app.ml.predictive_ops_models import CapacityForecaster, DealLossScorer, SlaBreachPredictor
from app.services.predictive_operations_engine import PredictiveOperationsEngine


def test_phase_c_catalog_includes_trained_ops_models():
    for name in ("sla_breach_predictor", "deal_loss_scorer", "capacity_forecaster"):
        assert GRAVITRE_ML_CATALOG[name]["status"] == ModelStatus.TRAINED


@pytest.mark.asyncio
async def test_untrained_sla_predictor_reports_data_gate():
    predictor = SlaBreachPredictor()
    with patch.object(predictor, "_count_ticket_signals", AsyncMock(return_value=12)):
        result = await predictor.predict_structured(org_id="org-1")
    assert result["status"] == "not_trained"
    assert result["data_gate"]["met"] is False


@pytest.mark.asyncio
async def test_predictive_ops_untrained_org_model_reports_gate():
    engine = PredictiveOperationsEngine()
    mock_instance = SlaBreachPredictor()
    with patch(
        "app.services.predictive_operations_engine.get_org_model_status",
        AsyncMock(return_value={"catalog_status": ModelStatus.TRAINED.value}),
    ):
        with patch(
            "app.ml.model_catalog.load_org_trained_catalog_model",
            AsyncMock(return_value=mock_instance),
        ):
            with patch.object(mock_instance, "_count_ticket_signals", AsyncMock(return_value=5)):
                with pytest.raises(Exception):
                    await engine._predict_model("org-1", "sla_breach_predictor")


@pytest.mark.asyncio
async def test_predictive_ops_trained_model_calls_predict_structured():
    engine = PredictiveOperationsEngine()
    mock_instance = AsyncMock()
    mock_instance.predict_structured = AsyncMock(
        return_value={"status": "ok", "risk_score": 0.72, "advisory_only": True}
    )
    with patch(
        "app.services.predictive_operations_engine.get_org_model_status",
        AsyncMock(return_value={"catalog_status": ModelStatus.TRAINED.value}),
    ):
        with patch(
            "app.ml.model_catalog.load_org_trained_catalog_model",
            AsyncMock(return_value=mock_instance),
        ):
            result = await engine._predict_model("org-1", "churn_risk_scorer")
    assert result["status"] == "ok"
    assert result["risk_score"] == 0.72


@pytest.mark.asyncio
async def test_domain_pack_includes_new_models():
    engine = PredictiveOperationsEngine()
    assert "deal_loss_scorer" in engine.DOMAIN_PREDICTION_PACKS["sales"]
    assert "sla_breach_predictor" in engine.DOMAIN_PREDICTION_PACKS["support"]


@pytest.mark.asyncio
async def test_model_missing_structured_interface_degrades_honestly():
    """Regression: workflow_anomaly_detector / workflow_success_predictor /
    workflow_duration_forecaster route to AnomalyDetector / WorkflowSuccessPredictor /
    WorkflowForecaster, none of which implement predict_structured(). Before the
    fix this raised an uncaught AttributeError inside asyncio.gather, 500-ing the
    whole /intelligence/predictive domain request for every org (found live via
    2026-09-11 page audit — sales/support/operations domains were 100% broken).

    A model class lacking the structured-prediction interface must degrade to an
    honest "not_available" card, never crash the request.
    """
    engine = PredictiveOperationsEngine()

    class _NoStructuredInterface:
        """Stands in for AnomalyDetector et al — no predict_structured method."""

    mock_instance = _NoStructuredInterface()
    with patch(
        "app.services.predictive_operations_engine.get_org_model_status",
        AsyncMock(return_value={"catalog_status": ModelStatus.TRAINED.value}),
    ):
        with patch(
            "app.ml.model_catalog.load_org_trained_catalog_model",
            AsyncMock(return_value=mock_instance),
        ):
            result = await engine._predict_model("org-1", "workflow_anomaly_detector")

    assert result["status"] == "not_available"
    assert result["model"] == "workflow_anomaly_detector"
    assert result["advisory_only"] is True


@pytest.mark.asyncio
async def test_run_domain_predictions_never_500s_when_one_model_lacks_interface():
    """End-to-end: run_domain_predictions must return a normal payload (never
    raise) even when the domain pack includes a model class without
    predict_structured — this is the exact path the live /intelligence/predictive
    API hit for the support/operations/sales domains.
    """
    engine = PredictiveOperationsEngine()

    class _NoStructuredInterface:
        pass

    with patch(
        "app.services.predictive_operations_engine.get_org_model_status",
        AsyncMock(return_value={"catalog_status": ModelStatus.TRAINED.value}),
    ):
        with patch(
            "app.ml.model_catalog.load_org_trained_catalog_model",
            AsyncMock(return_value=_NoStructuredInterface()),
        ):
            result = await engine.run_domain_predictions("org-1", "support")

    assert result["domain"] == "support"
    statuses = {name: payload.get("status") for name, payload in result["predictions"].items()}
    assert statuses["workflow_anomaly_detector"] == "not_available"
