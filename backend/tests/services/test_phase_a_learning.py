"""Phase A: learning signal bus, strategy ledger, confidence calibrator."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.confidence_calibrator import ConfidenceCalibrator
from app.services.confidence_scorer import ConfidenceScorer
from app.services.learning_strategy_keys import build_model_strategy_key, build_route_strategy_key
from app.services.learning_signal_aggregator import LearningSignalAggregator, SIGNAL_WEIGHTS
from app.services.strategy_performance_ledger import StrategyPerformanceLedger, MIN_SAMPLES_FOR_PREFERENCE


def test_build_route_strategy_key_ml():
    key = build_route_strategy_key(
        {"primary_model": "ml_internal", "ml_model_name": "intent_classifier"},
        {"intent": "question_answering"},
        {"graph": {"nodes": 1}},
    )
    assert key.startswith("route:question_answering:ml:intent_classifier:")
    assert "graph" in key


def test_build_model_strategy_key():
    assert build_model_strategy_key("workflow_anomaly_detector") == "model:workflow_anomaly_detector"


@pytest.mark.asyncio
async def test_aggregator_ingest_records_to_ledger():
    aggregator = LearningSignalAggregator()
    mock_client = MagicMock()
    mock_client.table.return_value.insert.return_value.execute.return_value = None
    with patch.object(aggregator, "_client", return_value=mock_client):
        with patch(
            "app.services.strategy_performance_ledger.get_strategy_performance_ledger"
        ) as ledger_factory:
            ledger = AsyncMock()
            ledger_factory.return_value = ledger
            await aggregator.ingest(
                "org-1",
                "explicit_helpful",
                "positive",
                strategy_key="route:qa:llm:standard:no_graph:no_pred:no_causal",
            )
    ledger.record_from_signal.assert_awaited_once()


@pytest.mark.asyncio
async def test_ledger_choose_preferred_strategy_defaults_without_samples():
    ledger = StrategyPerformanceLedger()
    with patch.object(ledger, "rank_strategies", AsyncMock(return_value=[
        {"strategy_key": "llm:fast", "decided_samples": 0, "win_rate": None},
        {"strategy_key": "llm:standard", "decided_samples": 0, "win_rate": None},
    ])):
        result = await ledger.choose_preferred_strategy(
            "org-1",
            "llm:standard",
            ["llm:fast", "llm:standard"],
        )
    assert result["selected_key"] == "llm:standard"
    assert result["reason"] == "default_insufficient_evidence"


@pytest.mark.asyncio
async def test_ledger_choose_preferred_strategy_switches_on_evidence():
    ledger = StrategyPerformanceLedger()
    with patch.object(ledger, "rank_strategies", AsyncMock(return_value=[
        {
            "strategy_key": "llm:fast",
            "decided_samples": MIN_SAMPLES_FOR_PREFERENCE + 5,
            "win_rate": 0.85,
        },
        {
            "strategy_key": "llm:standard",
            "decided_samples": MIN_SAMPLES_FOR_PREFERENCE,
            "win_rate": 0.55,
        },
    ])):
        result = await ledger.choose_preferred_strategy(
            "org-1",
            "llm:standard",
            ["llm:fast", "llm:standard"],
        )
    assert result["selected_key"] == "llm:fast"
    assert result["reason"] == "ledger_win_rate"


def test_confidence_calibrator_default_when_insufficient_signals():
    calibrator = ConfidenceCalibrator()
    mock_client = MagicMock()
    mock_client.table.return_value.select.return_value.eq.return_value.gte.return_value.limit.return_value.execute.return_value.data = []
    with patch.object(calibrator, "_client", return_value=mock_client):
        assert calibrator.get_multiplier("org-1") == 1.0


def test_confidence_scorer_with_calibration_bounded():
    scorer = ConfidenceScorer()
    with patch("app.services.confidence_calibrator.get_confidence_calibrator") as factory:
        factory.return_value.get_multiplier.return_value = 1.15
        score = scorer.compute_with_calibration(
            "org-1",
            rag_quality=0.8,
            source_reliability=0.7,
            ml_confidence=0.9,
            classification_confidence=0.85,
        )
    assert score <= 1.0
    assert score > 0.8


def test_signal_weights_are_positive():
    assert all(weight > 0 for weight in SIGNAL_WEIGHTS.values())
