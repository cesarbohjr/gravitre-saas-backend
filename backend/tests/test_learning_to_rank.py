from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.ml.learning_to_rank import RetrievalRanker
from app.ml.source_reliability import (
    RELIABILITY_WEIGHT,
    apply_reliability_adjustment,
    clip_reliability_weight,
)


def _training_examples(count: int, *, helpful: bool = True) -> list[dict]:
    rows = []
    for idx in range(count):
        rows.append(
            {
                "rerank_score": 0.5 + (idx % 5) * 0.05,
                "source_reliability_score": 0.4 + (idx % 3) * 0.1,
                "rank_position": float((idx % 8) + 1),
                "source_document_age_days": float(idx % 30),
                "outcome_helpful": helpful if idx % 4 else not helpful,
            }
        )
    return rows


@pytest.mark.asyncio
async def test_falls_back_to_fixed_weight_below_min_examples():
    with patch(
        "app.ml.learning_to_rank.get_model_registry",
        side_effect=RuntimeError("no registry"),
    ):
        from app.ml.learning_to_rank import get_weight_for_org

        weight = await get_weight_for_org("org-1", MagicMock(), MagicMock())
    assert weight == RELIABILITY_WEIGHT


@pytest.mark.asyncio
async def test_trains_on_real_outcome_features():
    ranker = RetrievalRanker()
    examples = _training_examples(120)
    metrics = await ranker.train(examples)
    assert metrics.training_samples == 96
    assert metrics.validation_samples == 24
    assert ranker.get_learned_weight() is not None


def test_learned_weight_is_bounded():
    assert clip_reliability_weight(0.001) == pytest.approx(0.05)
    assert clip_reliability_weight(9.9) == pytest.approx(0.35)
    assert clip_reliability_weight(0.2) == pytest.approx(0.2)


def test_learned_weight_uses_same_additive_mechanism_as_v5():
    rows = [
        {"id": "a", "document_id": "doc-1", "score": 0.8},
        {"id": "b", "document_id": "doc-2", "score": 0.7},
    ]
    reliability = {"doc-1": 1.0, "doc-2": 0.0, "doc-3": 0.5}
    learned_weight = 0.22
    adjusted = apply_reliability_adjustment(rows, reliability, learned_weight)
    by_id = {row["id"]: row for row in adjusted}
    assert by_id["a"]["final_score"] == pytest.approx(0.8 + learned_weight * 1.0)
    assert by_id["b"]["final_score"] == pytest.approx(0.7 + learned_weight * 0.0)


@pytest.mark.asyncio
async def test_predict_weight_adjustment_returns_bounded_learned_weight():
    ranker = RetrievalRanker()
    ranker.learned_reliability_weight = 0.29
    weight = await ranker.predict_weight_adjustment({})
    assert weight == pytest.approx(0.29)


@pytest.mark.asyncio
async def test_get_weight_for_org_uses_deployed_ranker():
    ranker = RetrievalRanker()
    ranker.learned_reliability_weight = 0.21
    artifact = ranker.save()
    deployed = MagicMock(id="model-1", deployed_version=2)
    deployed.name = "company-retrieval-ranker"

    registry = MagicMock()
    registry.list_models = AsyncMock(return_value=[deployed])
    registry.load_model_artifact = AsyncMock(return_value=artifact)

    with patch("app.ml.learning_to_rank.get_model_registry", return_value=registry):
        from app.ml.learning_to_rank import get_weight_for_org

        weight = await get_weight_for_org("org-1", MagicMock(), MagicMock())
    assert weight == pytest.approx(0.21)
