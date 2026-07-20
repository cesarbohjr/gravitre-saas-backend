"""Module C Phase 3 — confirm churn / anomaly / forecast gates cannot be silently bypassed."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.ml.churn_scoring import ChurnRiskScorer
from app.ml.intelligence_training import (
    MIN_WORKFLOW_ROWS,
    train_churn_risk_scorer,
    train_workflow_anomaly_detector,
    train_workflow_duration_forecaster,
)
from app.ml.learning_to_rank import RetrievalRanker


@pytest.mark.asyncio
async def test_churn_trainer_enforces_min_examples():
    client = MagicMock()
    with patch(
        "app.ml.churn_feature_ingest.list_churn_training_rows",
        return_value=[{"features": {"days_since_last_activity": 1}, "churned": False}] * 5,
    ):
        result = await train_churn_risk_scorer("org-1", client=client)
    assert result["trained"] is False
    assert result["reason"] == "insufficient_data"
    assert result["required"] == ChurnRiskScorer.MIN_TRAINING_EXAMPLES
    assert result["training_examples"] == 5


@pytest.mark.asyncio
async def test_churn_scorer_train_raises_below_gate():
    scorer = ChurnRiskScorer()
    with pytest.raises(ValueError, match="Need at least"):
        await scorer.train(
            [{"days_since_last_activity": 1}] * 10,
            [0] * 10,
        )


@pytest.mark.asyncio
async def test_anomaly_trainer_enforces_min_workflow_rows():
    client = MagicMock()
    with patch(
        "app.ml.intelligence_training.collect_workflow_run_features",
        return_value=[{"duration_ms": 1000}] * (MIN_WORKFLOW_ROWS - 1),
    ):
        result = await train_workflow_anomaly_detector("org-1", client=client)
    assert result["trained"] is False
    assert result["reason"] == "insufficient_data"
    assert result["required"] == MIN_WORKFLOW_ROWS


@pytest.mark.asyncio
async def test_duration_forecaster_enforces_min_workflow_rows():
    client = MagicMock()
    rows = [{"duration_ms": 1000, "step_count": 2}] * (MIN_WORKFLOW_ROWS - 1)
    with (
        patch(
            "app.ml.intelligence_training.collect_workflow_run_features",
            return_value=rows,
        ),
        patch(
            "app.ml.intelligence_training.features_to_forecaster_train",
            return_value=(rows, [1000.0] * len(rows)),
        ),
    ):
        result = await train_workflow_duration_forecaster("org-1", client=client)
    assert result["trained"] is False
    assert result["reason"] == "insufficient_data"
    assert result["required"] == MIN_WORKFLOW_ROWS


@pytest.mark.asyncio
async def test_retrieval_ranker_gate_is_one_hundred():
    assert RetrievalRanker.MIN_TRAINING_EXAMPLES == 100
    ranker = RetrievalRanker()
    with pytest.raises(ValueError, match="Need at least 100"):
        await ranker.train(
            [{"rerank_score": 0.5, "source_reliability_score": 0.5, "rank_position": 1,
              "source_document_age_days": 1, "outcome_helpful": True}]
            * 50
        )
