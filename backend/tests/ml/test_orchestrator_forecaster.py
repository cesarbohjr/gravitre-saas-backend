from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.ml.base import ModelMetrics
from app.services.company_intelligence_orchestrator import CompanyIntelligenceOrchestrator


def _workflow_features(count: int = 35) -> list[dict]:
    rows = []
    for i in range(count):
        rows.append(
            {
                "duration_ms": 1000 + i * 100,
                "status": "completed" if i % 4 else "failed",
                "step_count": 3 + (i % 2),
                "error_count": 0 if i % 4 else 1,
                "retry_count": 0,
                "longest_step_duration_ms": 500.0,
                "avg_step_duration_ms": 250.0,
                "node_count": 4,
                "connector_node_count": 1,
                "agent_node_count": 1,
                "condition_node_count": 1,
                "has_approval_gate": 0,
                "max_graph_depth": 3,
                "run_hour_of_day": 10,
                "run_day_of_week": 2,
                "run_is_weekend": 0,
            }
        )
    return rows


@pytest.mark.asyncio
async def test_forecaster_trains_on_real_extracted_features():
    orchestrator = CompanyIntelligenceOrchestrator()
    with patch.object(orchestrator, "_register_or_update_model", new=AsyncMock(return_value="model-forecaster")):
        model_id, summary = await orchestrator._train_forecaster("org-1", _workflow_features())
    assert model_id == "model-forecaster"
    assert summary is not None
    assert len(summary) > 0
    assert "predicted_duration_ms" in summary[0]
    assert "confidence_interval" in summary[0]


@pytest.mark.asyncio
async def test_forecaster_skipped_below_min_rows():
    orchestrator = CompanyIntelligenceOrchestrator()
    model_id, summary = await orchestrator._train_forecaster("org-1", _workflow_features(10))
    assert model_id is None
    assert summary is None


@pytest.mark.asyncio
async def test_forecast_summary_has_confidence_interval():
    orchestrator = CompanyIntelligenceOrchestrator()
    with patch.object(orchestrator, "_register_or_update_model", new=AsyncMock(return_value="model-forecaster")):
        _, summary = await orchestrator._train_forecaster("org-1", _workflow_features())
    assert summary
    interval = summary[0]["confidence_interval"]
    assert "lower_bound" in interval
    assert "upper_bound" in interval
