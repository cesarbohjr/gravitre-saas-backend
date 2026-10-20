"""Real training/inference and fail-closed activation for the remaining core risk models."""
from datetime import UTC, datetime, timedelta
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.ml.predictive_ops_models import SlaBreachPredictor, DealLossScorer, SLA_FEATURE_KEYS, DEAL_FEATURE_KEYS
from app.ml.bound_risk_training import risk_training_rows, train_bound_risk_model


def records(keys, count=80):
    values = []
    start = datetime(2025, 1, 1, tzinfo=UTC)
    for i in range(count):
        positive = i % 2
        payload = {"entity_id": f"entity-{i}", "features": {key: float(1 + 8*positive + (i % 3)*.05) for key in keys},
                   "observed_at": (start+timedelta(days=2*i)).isoformat(),
                   "outcome_observed_at": (start+timedelta(days=2*i+1)).isoformat()}
        values.append({"input": json.dumps(payload), "expected_output": str(positive)})
    return values


@pytest.mark.asyncio
@pytest.mark.parametrize("cls,keys", [(SlaBreachPredictor, SLA_FEATURE_KEYS), (DealLossScorer, DEAL_FEATURE_KEYS)])
async def test_models_train_calibrate_roundtrip_and_use_every_supplied_row(cls, keys):
    x, y = risk_training_rows(records(keys))
    model = cls()
    metrics = await model.train(x, y)
    assert metrics.auc_roc > .95
    assert metrics.custom_metrics["calibration"] == "sigmoid_time_series_ensemble"
    assert metrics.custom_metrics["holdout_log_loss"] < metrics.custom_metrics["prior_log_loss"]
    restored = cls()
    restored.load(model.save())
    predictions, _ = await restored.predict(x[-2:])
    assert len(predictions) == 2
    assert predictions[0]["risk_score"] < .25
    assert predictions[1]["risk_score"] > .75
    with pytest.raises(ValueError, match="Complete real feature"):
        await restored.predict([{}])
    with pytest.raises(ValueError, match="binary labels"):
        await model.train(x, ["0"]*len(x))


def test_pre_outcome_features_and_independent_temporal_holdout_are_required():
    rows = records(DEAL_FEATURE_KEYS)
    payload = json.loads(rows[0]["input"])
    payload["observed_at"] = payload["outcome_observed_at"]
    rows[0]["input"] = json.dumps(payload)
    with pytest.raises(ValueError, match="precede"):
        risk_training_rows(rows)
    rows = records(DEAL_FEATURE_KEYS)
    payload = json.loads(rows[0]["input"])
    payload["outcome_observed_at"] = "2025-06-01T00:00:00+00:00"
    rows[0]["input"] = json.dumps(payload)
    x, y, parameters = risk_training_rows(rows, include_split=True)
    assert len(x) == 79 and parameters["training_split"] == 63
    assert x[0] != json.loads(rows[0]["input"])["features"]
    rows = records(DEAL_FEATURE_KEYS)
    payload = json.loads(rows[0]["input"])
    payload["outcome_observed_at"] = "2025-02-20T00:00:00+00:00"
    rows[0]["input"] = json.dumps(payload)
    x, y, parameters = risk_training_rows(rows, include_split=True)
    assert 0 not in parameters["calibration_splits"][0][0]
    assert 0 in parameters["calibration_splits"][-1][0]


@pytest.mark.asyncio
async def test_consent_is_required_before_any_dataset_read():
    with patch("app.ml.training_consent.training_is_approved", AsyncMock(return_value=False)), patch(
        "app.ml.bound_training_data.collect_bound_records"
    ) as read:
        result = await train_bound_risk_model("org-a", "sla_breach_predictor", settings=MagicMock())
    assert result["reason"] == "training_permission_inactive"
    read.assert_not_called()


@pytest.mark.asyncio
async def test_approved_training_reuses_registry_promotion_and_rechecks_consent_there():
    with patch("app.ml.training_consent.training_is_approved", AsyncMock(return_value=True)), patch(
        "app.ml.bound_training_data.collect_bound_records", return_value=records(SLA_FEATURE_KEYS)
    ), patch("app.ml.intelligence_training.register_trained_artifact_detailed", AsyncMock(return_value={"model_id": "model-a", "version": 1, "deployed": True, "evaluation": {}})) as register:
        result = await train_bound_risk_model("org-a", "sla_breach_predictor", settings=MagicMock())
    assert result["trained"] is True
    assert register.call_args.args == ("org-a",)
    assert register.call_args.kwargs["base_model"] == "sla_breach_predictor"
