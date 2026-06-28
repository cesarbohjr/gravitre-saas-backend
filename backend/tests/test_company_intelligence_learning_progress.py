"""Learning progress API for new-org intelligence UX."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.company_intelligence_orchestrator import CompanyIntelligenceOrchestrator


@pytest.mark.asyncio
async def test_learning_progress_returns_real_counts():
    orchestrator = CompanyIntelligenceOrchestrator(settings=MagicMock())
    with (
        patch(
            "app.services.company_intelligence_orchestrator.collect_query_corpus",
            new=AsyncMock(return_value=[{"query_text": f"q{i}"} for i in range(12)]),
        ),
        patch(
            "app.services.company_intelligence_orchestrator.collect_workflow_run_features",
            return_value=[{"run_id": f"r{i}"} for i in range(7)],
        ),
        patch.object(
            orchestrator,
            "_load_latest_snapshot",
            new=AsyncMock(
                return_value={
                    "context_markdown": "Learned patterns",
                    "updated_at": "2026-06-07T12:00:00+00:00",
                }
            ),
        ),
        patch.object(orchestrator, "_is_stale", return_value=False),
        patch.object(orchestrator, "_client", return_value=MagicMock()),
    ):
        progress = await orchestrator.get_learning_progress("org-1")

    assert progress["queryRows"] == 12
    assert progress["queryRowsNeeded"] == 50
    assert progress["workflowRows"] == 7
    assert progress["workflowRowsNeeded"] == 30
    assert progress["hasAnySnapshot"] is True


@pytest.mark.asyncio
async def test_learning_progress_zero_for_brand_new_org():
    orchestrator = CompanyIntelligenceOrchestrator(settings=MagicMock())
    with (
        patch(
            "app.services.company_intelligence_orchestrator.collect_query_corpus",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "app.services.company_intelligence_orchestrator.collect_workflow_run_features",
            return_value=[],
        ),
        patch.object(orchestrator, "_load_latest_snapshot", new=AsyncMock(return_value=None)),
        patch.object(orchestrator, "_client", return_value=MagicMock()),
    ):
        progress = await orchestrator.get_learning_progress("org-new")

    assert progress["queryRows"] == 0
    assert progress["workflowRows"] == 0
    assert progress["hasAnySnapshot"] is False
