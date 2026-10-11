"""Phase 1 ops repairs: honest conversation-health keys, no sentiment no-op in
voice prefetch, scheduler plan under Temporal, startup schema check,
optimization_recommendations columns, drift copy."""
from __future__ import annotations

import asyncio
import re
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# Fix 7a: speculative prefetch no longer runs (and discards) sentiment
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_prefetch_does_not_run_sentiment_analysis():
    from tests.services.pipecat_voice.test_speculative_prefetch import _processor

    proc = await _processor(min_chars=5)
    with (
        patch("app.services.chat_dialogue_settings.load_chat_dialogue_settings", AsyncMock(return_value={})),
        patch("app.services.sentiment_friction_service.get_sentiment_friction_service") as mock_sentiment,
        patch(
            "app.services.unified_turn_tool_retrieval.is_task_shaped_for_retrieval",
            return_value=(False, "chat", ""),
        ),
        patch("app.services.unified_turn_tool_retrieval.warm_tool_document_embeddings", return_value=0),
        patch("app.workflows.repository.get_supabase_client", return_value=object()),
    ):
        await proc._prefetch("hello there how are you")
    mock_sentiment.assert_not_called()


# ---------------------------------------------------------------------------
# Fix 7b: conversation-health no longer reports a fabricated frustration score
# ---------------------------------------------------------------------------
def _health_client(rows: list[dict[str, Any]]) -> MagicMock:
    client = MagicMock()
    chain = client.table.return_value.select.return_value
    chain.eq.return_value.gte.return_value.limit.return_value.execute.return_value = MagicMock(data=rows)
    return client


@pytest.mark.asyncio
async def test_conversation_health_reports_measured_low_quality_rate():
    from app.routers.admin_chat import get_conversation_health

    rows = [
        {"response_quality": 0.2, "query_category": "help"},
        {"response_quality": 0.9, "query_category": "data"},
        {"response_quality": 0.4, "query_category": "data"},
        {"response_quality": None, "query_category": "data"},
    ]
    with patch("app.routers.admin_chat.get_supabase_client", return_value=_health_client(rows)):
        out = await get_conversation_health(org_id="org-1", _admin=("u", "org-1", "admin"), settings=MagicMock())
    assert "avg_frustration_score_7d" not in out
    assert "escalation_rate_7d" not in out
    assert "consensus_trigger_rate_7d" not in out
    assert out["low_quality_rate_7d"] == pytest.approx(0.667, abs=1e-3)
    assert out["quality_sample_size"] == 3
    assert "frustration" in out["not_measured"]


@pytest.mark.asyncio
async def test_conversation_health_without_quality_data_is_null():
    from app.routers.admin_chat import get_conversation_health

    with patch("app.routers.admin_chat.get_supabase_client", return_value=_health_client([])):
        out = await get_conversation_health(org_id="org-1", _admin=("u", "org-1", "admin"), settings=MagicMock())
    assert out["low_quality_rate_7d"] is None
    assert out["avg_confidence_7d"] is None


# ---------------------------------------------------------------------------
# Fix 8: measurement / replan tick runs in Temporal mode too, exactly once
# ---------------------------------------------------------------------------
def test_scheduler_plan_keeps_memory_promotion_tick_under_temporal():
    from app.schedulers.startup_plan import learning_scheduler_plan

    assert learning_scheduler_plan(use_temporal=True) == {
        "company_intelligence": False,
        "memory_promotion": True,
    }
    assert learning_scheduler_plan(use_temporal=False) == {
        "company_intelligence": True,
        "memory_promotion": True,
    }


def test_memory_promotion_workflow_has_no_starter_caller():
    """The reason the in-process tick must run in Temporal mode."""
    app_dir = REPO_ROOT / "backend" / "app"
    callers = [
        path
        for path in app_dir.rglob("*.py")
        if re.search(r"(?<!def )start_memory_promotion_workflow\(", path.read_text(encoding="utf-8"))
    ]
    assert callers == []


def test_lifespan_starts_memory_promotion_scheduler_once_from_plan():
    import inspect

    from app import main as main_module

    source = inspect.getsource(main_module.lifespan)
    assert source.count("start_memory_promotion_scheduler()") == 1
    assert 'learning_plan["memory_promotion"]' in source
    assert "start_startup_schema_check()" in source


# ---------------------------------------------------------------------------
# Fix 10: startup schema check
# ---------------------------------------------------------------------------
def test_schema_check_reports_missing_columns():
    from app.core.schema_check import SCHEMA_DEPENDENCIES, check_schema_columns

    calls: list[tuple[str, str]] = []

    class _Q:
        def __init__(self, table: str):
            self.table = table
            self.col = ""

        def select(self, col: str):
            self.col = col
            return self

        def limit(self, n: int):
            assert n == 0
            return self

        def execute(self):
            calls.append((self.table, self.col))
            if (self.table, self.col) == ("goals", "category"):
                raise RuntimeError("column goals.category does not exist")
            return SimpleNamespace(data=[])

    client = SimpleNamespace(table=lambda name: _Q(name))
    result = check_schema_columns(client)
    expected = sum(len(cols) for cols in SCHEMA_DEPENDENCIES.values())
    assert result["checked"] == expected == len(calls)
    assert result["ok"] is False
    assert [(m["table"], m["column"]) for m in result["missing"]] == [("goals", "category")]
    assert ("custom_instructions", "kind") in calls
    assert ("custom_instructions", "department") in calls
    assert ("agent_memories", "is_current") in calls
    assert ("org_metric_definitions", "definition") in calls


@pytest.mark.asyncio
async def test_schema_check_skipped_in_tests_and_never_raises():
    from app.core import schema_check

    assert schema_check.start_startup_schema_check() is None
    assert await schema_check.run_startup_schema_check() is None

    class _Boom:
        def table(self, name: str):
            raise RuntimeError("network down")

    result = await schema_check.run_startup_schema_check(force=True, client=_Boom())
    assert result is not None and result["ok"] is False  # logged, not raised


# ---------------------------------------------------------------------------
# Fix 9: optimization_recommendations insert uses the schema that exists
# ---------------------------------------------------------------------------
def _first_schema_columns() -> set[str]:
    sql = (REPO_ROOT / "supabase/migrations/20260426000200_workflow_optimization.sql").read_text()
    block = sql.split("CREATE TABLE IF NOT EXISTS public.optimization_recommendations (", 1)[1].split(");", 1)[0]
    return {m.group(1) for m in re.finditer(r"^\s*([a-z_]+)\s", block, re.MULTILINE)}


def test_optimization_insert_uses_existing_columns_and_logs_errors():
    from app.services.optimization_service import (
        OptimizationService,
        Recommendation,
        RecommendationType,
    )

    service = OptimizationService.__new__(OptimizationService)
    service.settings = MagicMock()
    client = MagicMock()
    client.table.return_value.insert.return_value.execute.side_effect = RuntimeError("boom")
    rec = Recommendation(
        id="wf-1:retry",
        type=RecommendationType.ADD_RETRY,
        title="Add retry",
        issue="Failures observed",
        suggested_change="Add bounded retry",
        estimated_impact="Lower failure rate",
        confidence=0.8,
        risk="low",
    )
    with (
        patch("app.services.optimization_service.get_supabase_client", return_value=client),
        patch("app.services.optimization_service.logger") as log,
    ):
        service._persist_recommendations("org-1", "wf-1", [rec])  # noqa: SLF001
    rows = client.table.return_value.insert.call_args.args[0]
    allowed = _first_schema_columns()
    assert {"issue", "suggested_change", "risk_level", "status"} <= allowed
    for row in rows:
        assert set(row) <= allowed, set(row) - allowed
        assert row["risk_level"] == "low"
        assert row["status"] == "open"
        assert row["suggested_change"]["title"] == "Add retry"
    log.warning.assert_called_once()
    assert "boom" in str(log.warning.call_args)


# ---------------------------------------------------------------------------
# Fix 6: Meson model copy no longer promises drift monitoring
# ---------------------------------------------------------------------------
def test_meson_model_detail_does_not_claim_drift_monitoring():
    from app.services.meson_service import MesonService

    service = MesonService(model_router=object())  # type: ignore[arg-type]
    for status in ("deployed", "draft"):
        client = MagicMock()
        q = client.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value
        q.execute.return_value = MagicMock(
            data=[
                {
                    "id": "m1",
                    "name": "Intent",
                    "status": status,
                    "model_type": "classifier",
                    "deployed_version": 2 if status == "deployed" else None,
                    "current_version": 2,
                    "dataset_id": "d1",
                }
            ]
        )
        resp = service._page_context_model_detail(client, "org-1", entity_id="m1")  # noqa: SLF001
        for insight in resp.insights:
            text = insight.summary.lower()
            assert "monitor drift" not in text
            assert "will flag drift" not in text
