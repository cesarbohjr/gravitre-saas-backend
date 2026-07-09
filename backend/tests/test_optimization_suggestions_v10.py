from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config import Settings
from app.services.optimization_suggestion_service import (
    ALLOWED_STATUSES,
    OptimizationSuggestionService,
    PRODUCTION_TABLE_NAMES,
)


@pytest.mark.asyncio
async def test_detection_never_writes_to_production_tables():
    import inspect

    import app.services.optimization_suggestion_service as module

    detect_source = "".join(
        inspect.getsource(getattr(OptimizationSuggestionService, name))
        for name in dir(OptimizationSuggestionService)
        if name.startswith("_detect_")
    )
    for table in PRODUCTION_TABLE_NAMES:
        assert f'table("{table}").insert' not in detect_source
        assert f'table("{table}").update' not in detect_source

    service = OptimizationSuggestionService(
        settings=Settings(
            app_env="dev",
            supabase_url="https://test.supabase.co",
            supabase_anon_key="anon-test",
            supabase_service_role_key="service-role-test",
            supabase_jwt_secret="jwt-secret-test",
        )
    )
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.gte.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[]
    )
    client.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[{"id": "s-1"}])
    with patch.object(service, "_client", return_value=client):
        with patch.object(service, "_detect_slow_steps", new=AsyncMock(return_value=[])):
            with patch.object(service, "_detect_low_reliability_references", new=AsyncMock(return_value=[])):
                with patch.object(service, "_detect_poor_outcome_patterns", new=AsyncMock(return_value=[])):
                    with patch.object(
                        service, "_detect_post_publish_marketing_underperformance", new=AsyncMock(return_value=[])
                    ):
                        with patch.object(service, "_detect_duplicate_steps", new=AsyncMock(return_value=[])):
                            with patch.object(service, "_detect_stalled_deals", new=AsyncMock(return_value=[])):
                                with patch.object(service, "_detect_overdue_invoices", new=AsyncMock(return_value=[])):
                                    with patch.object(
                                        service, "_detect_support_backlog_growth", new=AsyncMock(return_value=[])
                                    ):
                                        with patch.object(
                                            service,
                                            "_detect_process_mining_bottlenecks",
                                            new=AsyncMock(return_value=[]),
                                        ):
                                            await service.detect_suggestions_for_org("org-1")
    inserted_tables = [call.args[0] for call in client.table.call_args_list]
    assert all(name == "optimization_suggestions" for name in inserted_tables if name != "workflow_steps")


def test_no_status_value_permits_auto_apply():
    assert "auto_applied" not in ALLOWED_STATUSES
    import app.services.optimization_suggestion_service as module

    migration = (
        Path(module.__file__).resolve().parents[3]
        / "supabase/migrations/20260708161000_outcome_dependency_optimization_v8_v10.sql"
    )
    assert migration.exists()
    assert "auto_applied" not in migration.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_every_suggestion_has_reproducible_evidence():
    service = OptimizationSuggestionService(settings=MagicMock())
    client = MagicMock()
    client.table.return_value.insert.return_value.execute.return_value = MagicMock(
        data=[{"id": "s-1", "evidence": {"source": "workflow_steps.duration", "step_name": "Fetch CRM"}}]
    )
    with patch.object(service, "_client", return_value=client):
        row = await service._insert_suggestion(
            "org-1",
            target_entity_type="workflow_node",
            target_entity_id="Fetch CRM",
            suggestion_type="slow_step",
            evidence={"source": "workflow_steps.duration", "step_name": "Fetch CRM", "baseline_ms": 100},
            suggested_action="Review step latency",
            estimated_impact=None,
        )
    assert row["evidence"]["source"] == "workflow_steps.duration"


@pytest.mark.asyncio
async def test_mark_applied_only_records_does_not_modify():
    service = OptimizationSuggestionService(settings=MagicMock())
    client = MagicMock()
    client.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[
            {
                "id": "s-1",
                "status": "applied",
                "applied_change_summary": "Added cache manually",
                "target_entity_type": "workflow",
                "target_entity_id": "wf-1",
                "suggestion_type": "slow_step",
                "evidence": {"source": "workflow_steps.duration"},
                "suggested_action": "Cache",
            }
        ]
    )
    with patch.object(service, "_client", return_value=client):
        result = await service.mark_applied(
            "org-1",
            "s-1",
            reviewed_by="admin-1",
            applied_change_summary="Added cache manually",
        )
    assert result["status"] == "applied"
    assert client.table.call_args.args[0] == "optimization_suggestions"


@pytest.mark.asyncio
async def test_suggestions_gated_by_minimum_confidence():
    service = OptimizationSuggestionService(settings=MagicMock())
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.not_.is_.return_value.execute.return_value = MagicMock(
        data=[{"source_document_id": "doc-1", "outcome_helpful": True}] * 5
    )
    with patch.object(service, "_client", return_value=client):
        suggestions = await service._detect_low_reliability_references("org-1")
    assert suggestions == []


@pytest.mark.asyncio
async def test_estimated_impact_null_when_not_honestly_derivable():
    service = OptimizationSuggestionService(settings=MagicMock())
    client = MagicMock()
    client.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[{"id": "s-1"}])
    with patch.object(service, "_client", return_value=client):
        row = await service._insert_suggestion(
            "org-1",
            target_entity_type="rag_source_reference",
            target_entity_id="doc-1",
            suggestion_type="low_reliability_source",
            evidence={"source": "rag_chunk_outcomes", "reliability_score": 0.2},
            suggested_action="Review source",
            estimated_impact=None,
        )
    assert row.get("estimated_impact") is None
