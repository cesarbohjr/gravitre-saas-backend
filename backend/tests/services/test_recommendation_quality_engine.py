"""Tests for RecommendationQualityEngine."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.recommendation_quality_engine import RecommendationQualityEngine


@pytest.mark.asyncio
async def test_rank_recommendations_orders_by_quality_score():
    engine = RecommendationQualityEngine(settings=MagicMock())
    mock_outcomes = AsyncMock()
    mock_outcomes.get_department_outcome_summary = AsyncMock(return_value={"status": "ok", "score": 0.8})
    mock_outcomes.calculate_outcome_score = AsyncMock(return_value={"status": "ok", "score": 0.9})
    engine._outcomes = mock_outcomes

    ranked = await engine.rank_recommendations(
        [
            {"id": "low", "confidence": 0.4},
            {"id": "high", "confidence": 0.9},
        ],
        org_id="org-1",
        department="sales",
    )
    assert ranked[0]["id"] == "high"
    assert ranked[0]["quality_score"] >= ranked[-1]["quality_score"]


@pytest.mark.asyncio
async def test_record_recommendation_feedback_delegates_to_outcomes():
    engine = RecommendationQualityEngine(settings=MagicMock())
    mock_outcomes = AsyncMock()
    engine._outcomes = mock_outcomes

    await engine.record_recommendation_feedback(
        org_id="org-1",
        recommendation_id="rec-1",
        accepted=True,
        department="marketing",
    )
    mock_outcomes.record_recommendation_outcome.assert_awaited_once()
