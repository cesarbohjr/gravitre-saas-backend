"""ClickHouse analytics replica — fire-and-forget dual-write tests."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.clickhouse_service import ClickHouseService
from app.services.latency_tracking import log_pipeline_latency


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


@pytest.fixture
def settings():
    from types import SimpleNamespace

    return SimpleNamespace()


@pytest.mark.asyncio
async def test_clickhouse_write_is_fire_and_forget(settings):
    db = MagicMock()
    db.table.return_value.insert.return_value.execute.return_value = None
    ch_mock = MagicMock()
    ch_mock.is_available.return_value = True
    ch_mock.insert_events = AsyncMock(side_effect=RuntimeError("clickhouse down"))

    with patch("app.services.clickhouse_service.get_clickhouse_service", return_value=ch_mock):
        await log_pipeline_latency(
            settings,
            org_id="org-1",
            stage_name="retrieval",
            duration_ms=100,
            client=db,
        )
    db.table.assert_called_with("ai_pipeline_latency")


@pytest.mark.asyncio
async def test_postgres_write_still_happens_when_clickhouse_down(settings):
    db = MagicMock()
    insert_mock = db.table.return_value.insert
    insert_mock.return_value.execute.return_value = None

    with patch("app.services.clickhouse_service.get_clickhouse_service") as get_ch:
        svc = ClickHouseService()
        get_ch.return_value = svc
        await log_pipeline_latency(
            settings,
            org_id="org-1",
            stage_name="generation",
            duration_ms=50,
            client=db,
        )
    insert_mock.assert_called_once()


@pytest.mark.asyncio
async def test_dashboard_falls_back_to_postgres_when_clickhouse_unavailable():
    from app.services.performance_dashboard_service import load_performance_dashboard

    settings = MagicMock()
    db = MagicMock()
    db.table.return_value.select.return_value.eq.return_value.gte.return_value.execute.return_value.data = [
        {
            "stage_name": "retrieval",
            "duration_ms": 120,
            "cache_hit": False,
            "tier": "tier_2",
            "estimated_cost_usd": 0.001,
        }
    ]
    with patch("app.services.clickhouse_service.get_clickhouse_service") as get_ch:
        svc = MagicMock()
        svc.is_available.return_value = False
        get_ch.return_value = svc
        result = await load_performance_dashboard(settings, "org-1", client=db)
    assert result["sampleCount"] == 1
    assert "retrieval" in result["byStage"]


def test_clickhouse_tables_use_correct_engine_and_partition():
    sql = (_repo_root() / "scripts/clickhouse_schema.sql").read_text(encoding="utf-8")
    for table in ("pipeline_events", "outcome_events", "mcp_executions"):
        assert f"gravitre.{table}" in sql
    assert sql.count("ENGINE = MergeTree()") >= 3
    assert "PARTITION BY toYYYYMM(created_at)" in sql


def test_no_sensitive_data_in_clickhouse_beyond_analytics_events():
    sql = (_repo_root() / "scripts/clickhouse_schema.sql").read_text(encoding="utf-8").lower()
    forbidden = ("password", "credential", "message_content", "email", "auth_config", "secret")
    for term in forbidden:
        assert term not in sql


def test_clickhouse_service_noop_when_host_unset(monkeypatch):
    monkeypatch.delenv("CLICKHOUSE_HOST", raising=False)
    svc = ClickHouseService()
    assert svc.is_available() is False
