from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.ml.anomaly import AnomalyDetector
from app.ml.forecasting import WorkflowForecaster


@pytest.mark.asyncio
async def test_anomaly_detector_train_predict_and_detect():
    X = [{"duration_ms": 1000 + i * 50, "error_count": 0, "retry_count": 0} for i in range(30)]
    X.append({"duration_ms": 120000, "error_count": 3, "retry_count": 5})

    detector = AnomalyDetector(contamination=0.1)
    metrics = await detector.train(X)
    assert metrics.training_samples == len(X)

    flags, scores = await detector.predict(X[:5], return_probabilities=True)
    assert len(flags) == 5
    assert scores is not None and len(scores) == 5

    detected = await detector.detect_workflow_anomalies(X[-3:])
    assert len(detected) == 3


@pytest.mark.asyncio
async def test_workflow_forecaster_train_predict_and_forecast():
    X = [{"step_count": i % 5 + 1, "connector_count": i % 3, "decision_count": i % 2} for i in range(60)]
    y = [1500 + (row["step_count"] * 120) + (row["connector_count"] * 80) for row in X]
    timestamps = [datetime.now() - timedelta(hours=i) for i in range(len(X))]

    forecaster = WorkflowForecaster()
    metrics = await forecaster.train(X, y, timestamps=timestamps)
    assert metrics.mae is not None

    preds, intervals = await forecaster.predict([X[0], X[1]], return_probabilities=True, timestamps=timestamps[:2])
    assert len(preds) == 2
    assert intervals is not None and len(intervals) == 2

    future = await forecaster.forecast_workflow_duration("wf_1", historical_runs=X)
    assert len(future) == forecaster.forecast_horizon
