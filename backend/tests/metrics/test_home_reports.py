"""Home dashboard Reports aggregation: real rows in, design widgets out."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.metrics.home_reports import (
    WORKFLOWS_KEY,
    aggregate_home_reports,
    build_home_reports,
    home_reports_cache,
    normalize_runs,
)
from tests.support.build_insights import authenticate, chain_mock, clear_overrides, client

NOW = datetime(2026, 10, 7, 15, 0, tzinfo=timezone.utc)  # a Wednesday


@pytest.fixture(autouse=True)
def _reset():
    home_reports_cache.clear()
    yield
    clear_overrides()
    home_reports_cache.clear()


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _aggregate(runs, prev_runs=(), **kw):
    args = dict(
        range_key="7d",
        now=NOW,
        tz_offset_min=0,
        runs=list(runs),
        prev_runs=list(prev_runs),
        agent_names={"a1": {"name": "Sales Agent", "model": "gpt-4.1"}},
        agent_count=2,
        spend=1.5,
        prev_spend=1.0,
        model_count=1,
        decisions=3,
        prev_decisions=2,
        funnel_counts={"outreach_enrolled": 10, "lead_qualified": 4},
    )
    args.update(kw)
    return aggregate_home_reports(**args)


def test_normalize_attributes_jobs_to_agents_and_workflows_to_their_own_series():
    jobs = [
        {"status": "completed", "created_at": _iso(NOW), "started_at": _iso(NOW),
         "finished_at": _iso(NOW + timedelta(seconds=4)), "agent_id": "a1"},
        {"status": "failed", "created_at": _iso(NOW), "operator_id": "op1"},
        {"status": "completed", "created_at": _iso(NOW)},
    ]
    wf = [{"status": "completed", "created_at": _iso(NOW), "completed_at": _iso(NOW + timedelta(seconds=10))}]
    rows = normalize_runs(jobs, wf)
    assert [r["key"] for r in rows] == ["a1", "op1", WORKFLOWS_KEY, WORKFLOWS_KEY]
    assert rows[0]["duration"] == 4
    assert rows[3]["duration"] == 10


def test_aggregate_buckets_series_success_and_deltas():
    runs = normalize_runs(
        [
            {"status": "completed", "created_at": _iso(NOW - timedelta(days=1)), "started_at": _iso(NOW),
             "finished_at": _iso(NOW + timedelta(seconds=6)), "agent_id": "a1"},
            {"status": "failed", "created_at": _iso(NOW), "agent_id": "a1"},
        ],
        [{"status": "completed", "created_at": _iso(NOW), "completed_at": _iso(NOW + timedelta(seconds=2))}],
    )
    prev = normalize_runs([], [{"status": "completed", "created_at": _iso(NOW - timedelta(days=8))}])
    body = _aggregate(runs, prev)

    assert len(body["buckets"]) == 7
    assert body["buckets"][-1]["label"] == "Wed"
    assert body["buckets"][-1]["bySeries"] == {"a1": 1, WORKFLOWS_KEY: 1}
    assert body["buckets"][-2]["bySeries"] == {"a1": 1}
    assert body["totals"]["runs"] == 3
    assert body["totals"]["successRate"] == pytest.approx(66.7)
    assert body["totals"]["hoursSaved"] == round(2 * 4 / 60, 1)
    assert body["deltas"]["runs"] == 200.0
    assert body["deltas"]["modelSpendUsd"] == 50.0

    sales, workflows = body["series"]
    assert sales["name"] == "Sales Agent" and sales["model"] == "gpt-4.1"
    assert sales["runs"] == 2 and sales["successRate"] == 50.0 and sales["latencyP50Sec"] == 6
    assert workflows["name"] == "Workflows" and workflows["agentId"] is None

    # Wednesday 14:00-16:00 UTC block holds the two runs created "now".
    assert body["heat"][2]["day"] == "Wed" and body["heat"][2]["cells"][7] == 2
    # 6s of agent execution over 2 agents x 7 days.
    assert body["utilization"]["executingHours"] == 0.0
    assert body["utilization"]["percent"] == 0.0
    assert [s["value"] for s in body["funnel"]] == [10, 0, 4, 0]


def test_empty_org_reports_nulls_not_invented_numbers():
    body = _aggregate([], [], agent_count=0, spend=0, prev_spend=0, decisions=0, prev_decisions=0, funnel_counts={})
    assert body["totals"]["runs"] == 0
    assert body["totals"]["successRate"] is None
    assert body["totals"]["medianDurationSec"] is None
    assert body["deltas"]["runs"] is None
    assert body["utilization"]["percent"] is None
    assert body["series"] == []


def test_ninety_days_buckets_weekly_and_viewer_timezone_shifts_days():
    body = _aggregate([], range_key="90d")
    assert len(body["buckets"]) == 13 and body["weekly"] is True
    late = normalize_runs([{"status": "completed", "created_at": _iso(NOW.replace(hour=23, minute=30)), "agent_id": "a1"}], [])
    shifted = _aggregate(late, now=NOW.replace(hour=23, minute=45), tz_offset_min=120)
    # 23:30 UTC is 01:30 Thursday at UTC+2.
    assert shifted["buckets"][-1]["label"] == "Thu"
    assert shifted["buckets"][-1]["total"] == 1
    assert shifted["heat"][3]["cells"][0] == 1


def _db(tables: dict[str, list[dict]]):
    db = MagicMock()

    def _table(name: str):
        t = MagicMock()
        t.select.return_value = chain_mock(data=tables.get(name, []))
        return t

    db.table.side_effect = _table
    return db


@patch("app.routers.metrics.create_client")
def test_route_returns_report_and_caches_per_org(mock_create):
    now = datetime.now(timezone.utc)
    db = _db(
        {
            "agent_jobs": [{"id": "j1", "status": "completed", "created_at": _iso(now), "agent_id": "a1"}],
            "agents": [{"id": "a1", "name": "Marketing Agent", "model": "claude-sonnet-4-6"}],
            "model_calls": [{"id": "m1", "cost_usd": 0.25, "model_name": "gpt-4.1", "created_at": _iso(now)}],
        }
    )
    mock_create.return_value = db
    authenticate()
    res = client.get("/api/metrics/home-reports?range=7d&tz=-420")
    assert res.status_code == 200
    body = res.json()
    assert body["totals"]["runs"] == 1
    assert body["totals"]["modelSpendUsd"] == 0.25
    assert body["series"][0]["name"] == "Marketing Agent"
    calls = db.table.call_count
    assert client.get("/api/metrics/home-reports?range=7d&tz=-420").status_code == 200
    assert db.table.call_count == calls

    assert client.get("/api/metrics/home-reports?range=1y").status_code == 400


def test_build_rejects_unknown_range():
    with pytest.raises(ValueError):
        build_home_reports(MagicMock(), "org", "1y")
