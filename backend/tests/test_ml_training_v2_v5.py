"""Tests for v2–v5 intelligence model training pipelines."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.ml.memory_promotion_scorer import MemoryPromotionScorer
from app.ml.model_catalog import GRAVITRE_ML_CATALOG, train_ml_model_for_org


def _resolved_candidates(count: int, *, positive: bool = True) -> list[dict]:
    status = "approved" if positive else "rejected"
    return [
        {
            "candidate_type": "successful_response",
            "memory_category": "fact",
            "status": status,
            "frequency": idx + 1,
            "department_count": (idx % 3) + 1,
            "content": f"Memory candidate {idx}",
        }
        for idx in range(count)
    ]


@pytest.mark.asyncio
async def test_memory_promotion_scorer_trains_on_resolved_candidates():
    scorer = MemoryPromotionScorer()
    candidates = _resolved_candidates(10, positive=True) + _resolved_candidates(8, positive=False)
    metrics = await scorer.train(candidates=candidates)
    assert metrics.training_samples + metrics.validation_samples >= scorer.MIN_TRAINING_EXAMPLES
    result = await scorer.score_candidate(candidates[0])
    assert result["status"] == "ok"
    assert result["advisory_only"] is True


@pytest.mark.asyncio
async def test_memory_promotion_scorer_insufficient_data():
    scorer = MemoryPromotionScorer()
    with pytest.raises(ValueError, match="Need at least"):
        await scorer.train(candidates=_resolved_candidates(5))


@pytest.mark.asyncio
async def test_train_v2_intent_classifier_insufficient_data():
    from app.ml.intelligence_training import train_v2_intent_classifier

    with patch("app.ml.intelligence_training.collect_query_corpus", new=AsyncMock(return_value=[])):
        result = await train_v2_intent_classifier("org-1")
    assert result["trained"] is False
    assert result["reason"] == "insufficient_data"


@pytest.mark.asyncio
async def test_train_v5_retrieval_ranker_insufficient_data():
    from app.ml.intelligence_training import train_v5_retrieval_ranker

    mock_client = MagicMock()
    with patch("app.ml.intelligence_training.get_supabase_client", return_value=mock_client), patch(
        "app.ml.intelligence_training.count_training_examples",
        new=AsyncMock(return_value=5),
    ):
        result = await train_v5_retrieval_ranker("org-1")
    assert result["trained"] is False
    assert result["training_examples"] == 5


@pytest.mark.asyncio
async def test_train_ml_model_for_org_dispatches_intent_classifier():
    with patch(
        "app.ml.intelligence_training.train_catalog_model",
        new=AsyncMock(return_value={"trained": True, "model_id": "mid-1"}),
    ):
        result = await train_ml_model_for_org("org-1", "intent_classifier")
    assert result["trained"] is True
    assert result["model_id"] == "mid-1"
    assert "latency_ms" in result


@pytest.mark.asyncio
async def test_retrieval_memory_learner_runs_v3_v4_v5():
    from app.ml.retrieval_learning import RetrievalMemoryLearner

    learner = RetrievalMemoryLearner()
    unified = {
        "trained": True,
        "components": {
            "query_clusterer_v3": {"trained": True},
            "memory_promotion_v4": {"trained": False, "reason": "insufficient_data"},
            "retrieval_ranker_v5": {"trained": True},
        },
    }
    with patch(
        "app.ml.intelligence_training.train_retrieval_memory_learner",
        new=AsyncMock(return_value=unified),
    ):
        result = await learner.train_for_org("org-1")
    assert result["trained"] is True
    assert "query_clusterer_v3" in result["components"]


def test_catalog_includes_v4_memory_promotion_scorer():
    assert "memory_promotion_scorer" in GRAVITRE_ML_CATALOG
    assert GRAVITRE_ML_CATALOG["memory_promotion_scorer"]["advisory_only"] is True


def test_training_dispatch_covers_v2_through_v5():
    from app.ml.intelligence_training import TRAINING_DISPATCH

    expected = {
        "intent_classifier",
        "query_clusterer",
        "memory_promotion_scorer",
        "retrieval_ranker",
        "retrieval_memory_learner",
    }
    assert expected.issubset(TRAINING_DISPATCH.keys())
