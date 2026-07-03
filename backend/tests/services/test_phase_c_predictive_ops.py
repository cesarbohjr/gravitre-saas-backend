"""Phase C: predictive ops expansion with honest data gates."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.ml.base import ModelStatus
from app.ml.model_catalog import GRAVITRE_ML_CATALOG, get_model_instance
from app.ml.predictive_ops_models import CapacityForecaster, DealLossScorer, SlaBreachPredictor
from app.services.predictive_operations_engine import PredictiveOperationsEngine


def test_phase_c_catalog_includes_planned_ops_models():
    for name in ("sla_breach_predictor", "deal_loss_scorer", "capacity_forecaster"):
        assert GRAVITRE_ML_CATALOG[name]["status"] == ModelStatus.PLANNED


@pytest.mark.asyncio
async def test_planned_sla_predictor_reports_data_gate():
    predictor = SlaBreachPredictor()
    with patch.object(predictor, "_count_ticket_signals", AsyncMock(return_value=12)):
        result = await predictor.predict_structured(org_id="org-1")
    assert result["status"] == "not_available"
    assert result["data_gate"]["met"] is False


@pytest.mark.asyncio
async def test_predictive_ops_planned_model_returns_data_gate():
    engine = PredictiveOperationsEngine()
    with patch(
        "app.services.predictive_operations_engine.get_org_model_status",
        AsyncMock(),
    ):
        result = await engine._predict_model("org-1", "deal_loss_scorer")
    assert result["status"] == "planned"
    assert "data_gate" in result


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
            "app.services.predictive_operations_engine.get_model_instance",
            return_value=mock_instance,
        ):
            result = await engine._predict_model("org-1", "churn_risk_scorer")
    assert result["status"] == "ok"
    assert result["risk_score"] == 0.72


@pytest.mark.asyncio
async def test_domain_pack_includes_new_models():
    engine = PredictiveOperationsEngine()
    assert "deal_loss_scorer" in engine.DOMAIN_PREDICTION_PACKS["sales"]
    assert "sla_breach_predictor" in engine.DOMAIN_PREDICTION_PACKS["support"]
