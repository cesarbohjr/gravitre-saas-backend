"""Tests for BusinessSignalsEngine."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.business_signals_engine import BusinessSignalsEngine


@pytest.mark.asyncio
async def test_collect_signals_aggregates_predictive_alerts():
    engine = BusinessSignalsEngine(settings=MagicMock())
    engine._predictive = AsyncMock()
    engine._predictive.run_domain_predictions = AsyncMock(
        return_value={
            "predictions": {
                "churn_model": {
                    "status": "ok",
                    "risk_score": 0.82,
                    "prediction": {"summary": "Elevated churn in enterprise segment"},
                }
            }
        }
    )
    engine._predictive.generate_early_warning_alerts = AsyncMock(return_value=[])
    engine._quality = AsyncMock()
    engine._quality.rank_recommendations = AsyncMock(side_effect=lambda rows, **kwargs: rows)

    with patch("app.services.business_signals_engine.get_optimization_suggestion_service") as mock_opt:
        mock_opt.return_value.list_suggestions = AsyncMock(return_value={"suggestions": []})
        with patch("app.services.business_signals_engine.list_failure_alerts", return_value=[]):
            payload = await engine.collect_signals("org-1", department="sales", client=MagicMock())

    assert payload["signals"]
    assert payload["signals"][0]["source"] == "predictive_operations"


@pytest.mark.asyncio
async def test_generate_department_brief_includes_risks_and_actions():
    engine = BusinessSignalsEngine(settings=MagicMock())
    engine.collect_signals = AsyncMock(
        return_value={
            "signals": [
                {
                    "title": "Pipeline gap",
                    "summary": "Coverage below target",
                    "signal_type": "risk",
                    "quality_score": 0.77,
                },
                {
                    "title": "Upsell opportunity",
                    "summary": "Accounts ready for expansion",
                    "signal_type": "opportunity",
                    "quality_score": 0.71,
                },
            ],
            "collected_at": "2026-07-03T00:00:00Z",
        }
    )
    brief = await engine.generate_department_brief("org-1", "sales")
    assert brief["department"] == "sales"
    assert brief["risks"]
    assert brief["recommended_actions"]


@pytest.mark.asyncio
async def test_collect_signals_attaches_priority_scoring_payload():
    engine = BusinessSignalsEngine(settings=MagicMock())
    engine._predictive = AsyncMock()
    engine._predictive.run_domain_predictions = AsyncMock(return_value={"predictions": {}})
    engine._predictive.generate_early_warning_alerts = AsyncMock(return_value=[])
    engine._quality = AsyncMock()
    engine._quality.rank_recommendations = AsyncMock(side_effect=lambda rows, **kwargs: rows)

    fake_scoring = {
        "department": "sales",
        "capturedAt": "2026-09-04T00:00:00Z",
        "priorities": [
            {
                "title": "Acme expansion",
                "priorityScore": 81.5,
                "priorityBand": "high",
                "explanations": ["Engagement signal +20.0 pts"],
            }
        ],
        "gaps": [],
    }
    fake_audit = {"departments": []}

    with patch("app.services.business_signals_engine.get_optimization_suggestion_service") as mock_opt, patch(
        "app.services.business_signals_engine.list_failure_alerts", return_value=[]
    ), patch(
        "app.services.department_signal_scoring_service.get_department_signal_scoring_service"
    ) as mock_scorer_factory:
        mock_opt.return_value.list_suggestions = AsyncMock(return_value={"suggestions": []})
        mock_scorer = MagicMock()
        mock_scorer.score_department.return_value = fake_scoring
        mock_scorer.audit_sources.return_value = fake_audit
        mock_scorer_factory.return_value = mock_scorer
        payload = await engine.collect_signals("org-1", department="sales", client=MagicMock(), use_cache=False)

    assert payload["signal_scoring"] == fake_scoring
    assert payload["signal_source_audit"] == fake_audit
    assert any(row.get("source") == "signal_scoring_engine" for row in payload["signals"])
