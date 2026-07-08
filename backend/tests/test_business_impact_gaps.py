"""Business Impact aggregation and suggestion explanation API gaps."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config import Settings
from app.services.business_impact_service import load_business_impact_snapshot
from app.services.optimization_suggestion_service import (
    OptimizationSuggestionService,
    _serialize_suggestion,
)


def test_serialize_suggestion_includes_explanation():
    row = {
        "id": "sug-1",
        "target_entity_type": "deal",
        "target_entity_id": "deal-1",
        "suggestion_type": "stalled_deal",
        "evidence": {
            "source": "agent_action_outcomes",
            "sample_size": 18,
            "confidence_note": "correlational only",
        },
        "suggested_action": "Review stalled deals.",
        "estimated_impact": None,
        "status": "pending_review",
        "created_at": "2026-06-07T00:00:00Z",
    }
    serialized = _serialize_suggestion(row)
    assert serialized["explanation"]
    assert "stalled deal" in serialized["explanation"].lower()
    assert serialized["suggestionType"] == "stalled_deal"


@pytest.mark.asyncio
async def test_get_suggestion_returns_explanation():
    service = OptimizationSuggestionService(settings=MagicMock())
    row = {
        "id": "sug-2",
        "target_entity_type": "invoice",
        "target_entity_id": "inv-1",
        "suggestion_type": "overdue_invoice",
        "evidence": {"source": "quickbooks.invoices", "sample_size": 5},
        "suggested_action": "Follow up on overdue invoices.",
        "estimated_impact": None,
        "status": "pending_review",
    }
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[row]
    )
    with patch.object(service, "_client", return_value=client):
        result = await service.get_suggestion("org-1", "sug-2")
    assert result["id"] == "sug-2"
    assert "overdue invoice" in result["explanation"].lower()


@pytest.mark.asyncio
async def test_business_impact_aggregates_pending_suggestions_and_outcomes():
    pending_row = {
        "id": "sug-3",
        "suggestion_type": "overdue_invoice",
        "suggested_action": "3 invoices overdue.",
        "evidence": {"source": "quickbooks.invoices", "sample_size": 3},
        "status": "pending_review",
        "created_at": "2026-06-07T00:00:00Z",
    }
    client = MagicMock()

    def table(name):
        t = MagicMock()
        if name == "optimization_suggestions":
            t.select.return_value.eq.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = MagicMock(
                data=[pending_row]
            )
        elif name == "agents":
            t.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
                data=[{"id": "agent-1", "name": "Sales Agent"}]
            )
        return t

    client.table.side_effect = table
    outcome_service = MagicMock()
    outcome_service.get_agent_outcome_summary = AsyncMock(
        return_value={
            "sufficientData": True,
            "winRate": 0.2,
            "sampleSize": 20,
            "confidenceNote": "correlational only",
        }
    )
    with patch("app.services.business_impact_service.get_supabase_client", return_value=client):
        with patch(
            "app.services.business_impact_service.get_outcome_attribution_service",
            return_value=outcome_service,
        ):
            snapshot = await load_business_impact_snapshot("org-1", settings=MagicMock())
    assert snapshot["pendingReviewCount"] == 1
    assert snapshot["pendingBusinessSignals"] == 1
    assert snapshot["businessImpactScore"] < 100
    assert len(snapshot["revenueRiskItems"]) >= 2
    assert snapshot["revenueRiskItems"][0]["explanation"]


@pytest.mark.asyncio
async def test_v10_business_detectors_are_registered():
    service = OptimizationSuggestionService(
        settings=Settings(
            app_env="dev",
            supabase_url="https://test.supabase.co",
            supabase_anon_key="anon-test",
            supabase_service_role_key="service-role-test",
            supabase_jwt_secret="jwt-secret-test",
            openai_api_key="sk-test-openai",
        )
    )
    with patch.object(service, "_detect_slow_steps", new=AsyncMock(return_value=[])):
        with patch.object(service, "_detect_low_reliability_references", new=AsyncMock(return_value=[])):
            with patch.object(service, "_detect_poor_outcome_patterns", new=AsyncMock(return_value=[])):
                with patch.object(
                    service,
                    "_detect_post_publish_marketing_underperformance",
                    new=AsyncMock(return_value=[]),
                ):
                    with patch.object(service, "_detect_duplicate_steps", new=AsyncMock(return_value=[])):
                        stalled = AsyncMock(return_value=[{"id": "s1"}])
                        overdue = AsyncMock(return_value=[{"id": "s2"}])
                        backlog = AsyncMock(return_value=[{"id": "s3"}])
                        with patch.object(service, "_detect_stalled_deals", new=stalled):
                            with patch.object(service, "_detect_overdue_invoices", new=overdue):
                                with patch.object(service, "_detect_support_backlog_growth", new=backlog):
                                    with patch.object(
                                        service,
                                        "_detect_process_mining_bottlenecks",
                                        new=AsyncMock(return_value=[]),
                                    ):
                                        result = await service.detect_suggestions_for_org("org-1")
    assert result == [{"id": "s1"}, {"id": "s2"}, {"id": "s3"}]
    stalled.assert_awaited_once()
    overdue.assert_awaited_once()
    backlog.assert_awaited_once()
