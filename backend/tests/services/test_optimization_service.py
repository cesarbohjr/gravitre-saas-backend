from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.optimization_service import OptimizationService, Recommendation, RecommendationType


@pytest.fixture
def service(mock_settings) -> OptimizationService:
    with patch("app.services.optimization_service.get_settings", return_value=mock_settings):
        return OptimizationService()


@pytest.mark.asyncio
async def test_analyze_workflow_generates_recommendations(service: OptimizationService):
    mock_client = MagicMock()
    mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
        {"id": "run-1", "status": "completed", "duration_ms": 350000},
        {"id": "run-2", "status": "failed", "duration_ms": 330000},
        {"id": "run-3", "status": "failed", "duration_ms": 310000},
    ]
    with patch("app.services.optimization_service.get_supabase_client", return_value=mock_client):
        with patch.object(service.model_router, "complete", AsyncMock(return_value=SimpleNamespace(content="Add retries"))):
            with patch.object(service, "_persist_recommendations") as persist:
                recs = await service.analyze_workflow(org_id="org-1", workflow_id="wf-1", days=30)
    assert len(recs) >= 2
    assert any(rec.type == RecommendationType.ADD_RETRY for rec in recs)
    persist.assert_called_once()


@pytest.mark.asyncio
async def test_analyze_workflow_empty_runs(service: OptimizationService):
    mock_client = MagicMock()
    mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = []
    with patch("app.services.optimization_service.get_supabase_client", return_value=mock_client):
        recs = await service.analyze_workflow(org_id="org-1", workflow_id="wf-1", days=7)
    assert recs == []


def test_persist_recommendations_handles_insert(service: OptimizationService):
    mock_client = MagicMock()
    with patch("app.services.optimization_service.get_supabase_client", return_value=mock_client):
        service._persist_recommendations(  # noqa: SLF001
            org_id="org-1",
            workflow_id="wf-1",
            recs=[
                Recommendation(
                    id="wf-1:retry",
                    type=RecommendationType.ADD_RETRY,
                    title="Add retry",
                    issue="Failures observed",
                    suggested_change="Add bounded retry",
                    estimated_impact="Lower failure rate",
                    confidence=0.8,
                    risk="low",
                )
            ],
        )
    mock_client.table.assert_called_once_with("optimization_recommendations")
