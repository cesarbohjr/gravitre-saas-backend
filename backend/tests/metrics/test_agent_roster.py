"""Agents roster aggregation: real job rows in, per-agent daily work out."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from app.metrics.agent_roster import (
    DAYS,
    agent_roster_cache,
    aggregate_agent_roster,
    blocked_reason,
    needs_approval_gate,
)
from tests.support.build_insights import (
    authenticate,
    chain_mock,
    clear_overrides,
    client,
)

NOW = datetime(2026, 10, 7, 15, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _reset():
    agent_roster_cache.clear()
    yield
    clear_overrides()
    agent_roster_cache.clear()


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _job(status: str, at: datetime, agent: str = "a1", **extra):
    return {"id": extra.pop("id", f"j-{status}-{at.isoformat()}"), "status": status,
            "created_at": _iso(at), "finished_at": _iso(at) if status in ("completed", "failed") else None,
            "agent_id": agent, **extra}


def _aggregate(jobs, **kw):
    args = {"now": NOW, "tz_offset_min": 0, "jobs": list(jobs), "identities": {}, "goals": [], "plans": []}
    args.update(kw)
    return aggregate_agent_roster(**args)


def test_counts_today_daily_bars_success_and_last_active():
    body = _aggregate(
        [
            _job("completed", NOW - timedelta(hours=1)),
            _job("completed", NOW - timedelta(hours=2)),
            _job("failed", NOW - timedelta(hours=3), error="Apollo plan lacks search access"),
            _job("completed", NOW - timedelta(days=2)),
            _job("completed", NOW - timedelta(days=9)),
            _job("running", NOW - timedelta(minutes=5), agent="op1"),
        ]
    )
    a1 = body["agents"]["a1"]
    assert a1["tasksToday"] == 2 and a1["failedToday"] == 1
    assert a1["successRateToday"] == pytest.approx(66.7)
    # 9-day-old job is outside the 7-day success window but still on the 14-day bars.
    assert a1["successRate7d"] == pytest.approx(75.0)
    assert len(a1["daily"]) == DAYS and a1["daily"][-1] == 2 and a1["daily"][-3] == 1 and a1["daily"][-10] == 1
    assert a1["lastActiveAt"] == _iso(NOW - timedelta(hours=1))
    # The latest job succeeded, so an earlier failure does not block the agent.
    assert a1["blocked"] is None
    assert body["agents"]["op1"]["runningNow"] == 1
    assert body["agents"]["op1"]["successRate7d"] is None
    assert len(body["days"]) == DAYS


def test_latest_failed_or_paused_job_blocks_with_a_plain_reason():
    body = _aggregate(
        [
            _job("completed", NOW - timedelta(hours=5)),
            _job("failed", NOW - timedelta(hours=1), id="j9", error="Waiting on an Apollo plan with search access."),
            _job("paused", NOW - timedelta(hours=1), agent="a2"),
            _job("failed", NOW - timedelta(days=10), agent="a3", error="old"),
        ]
    )
    assert body["agents"]["a1"]["blocked"]["reason"] == "Waiting on an Apollo plan with search access"
    assert body["agents"]["a1"]["blocked"]["jobId"] == "j9"
    assert body["agents"]["a2"]["blocked"]["kind"] == "paused"
    assert body["agents"]["a3"]["blocked"] is None


def test_technical_errors_are_never_shown_raw():
    assert blocked_reason("failed", "KeyError: 'x'") == "Its last task did not finish"
    assert blocked_reason("failed", "HTTP 403 from {\"detail\": 1}") == "Its last task did not finish"
    assert blocked_reason("failed", None) == "Its last task did not finish"


def test_viewer_timezone_moves_a_late_task_to_tomorrow():
    late = _job("completed", NOW.replace(hour=23, minute=30))
    body = _aggregate([late], now=NOW.replace(hour=23, minute=45), tz_offset_min=120)
    assert body["agents"]["a1"]["tasksToday"] == 1
    utc = _aggregate([_job("completed", NOW - timedelta(days=1, hours=1))], now=NOW, tz_offset_min=0)
    assert utc["agents"]["a1"]["tasksToday"] == 0 and utc["agents"]["a1"]["daily"][-2] == 1


def test_approval_gate_fails_closed_and_follows_policy():
    assert needs_approval_gate(None) is True
    assert needs_approval_gate({"trust_level": "write_with_approval"}) is True
    assert needs_approval_gate({"trust_level": "read_only"}) is False
    assert needs_approval_gate({"trust_level": "autonomous", "approval_rule_overrides": {"write": "auto_run"}}) is False
    assert needs_approval_gate({"trust_level": "autonomous"}) is True
    assert needs_approval_gate({"trust_level": "write_with_approval", "allowed_action_kinds": ["read"]}) is False


def test_goals_use_the_latest_plan_and_skip_closed_goals():
    body = _aggregate(
        [],
        goals=[
            {"id": "g1", "objective": "Get 100 MSP leads", "status": "draft", "department": "Sales"},
            {"id": "g2", "objective": "Done", "status": "completed"},
        ],
        plans=[
            {"goal_id": "g1", "required_agents": ["a1"], "created_at": "2026-10-01T00:00:00+00:00"},
            {"goal_id": "g1", "required_agents": ["a1", "a2"], "created_at": "2026-10-02T00:00:00+00:00"},
        ],
    )
    assert [g["id"] for g in body["goals"]] == ["g1"]
    assert body["goals"][0]["agentIds"] == ["a1", "a2"]


def test_empty_org_reports_nothing_invented():
    body = _aggregate([])
    assert body["agents"] == {} and body["goals"] == [] and body["approvalGate"] == {}


def _db(tables: dict[str, list[dict]]):
    db = MagicMock()

    def _table(name: str):
        t = MagicMock()
        t.select.return_value = chain_mock(data=tables.get(name, []))
        return t

    db.table.side_effect = _table
    return db


@patch("app.routers.metrics.create_client")
def test_route_returns_roster_and_caches_per_org(mock_create):
    now = datetime.now(UTC)
    db = _db(
        {
            "agent_jobs": [{"id": "j1", "status": "completed", "created_at": _iso(now), "finished_at": _iso(now), "agent_id": "a1"}],
            "agent_identity_records": [{"id": "i1", "agent_id": "a1", "trust_level": "read_only"}],
            "goals": [{"id": "g1", "objective": "Grow signups", "status": "active"}],
        }
    )
    mock_create.return_value = db
    authenticate()
    res = client.get("/api/metrics/agent-roster?tz=0")
    assert res.status_code == 200
    body = res.json()
    assert body["agents"]["a1"]["tasksToday"] == 1
    assert body["approvalGate"] == {"a1": False}
    assert body["goals"][0]["objective"] == "Grow signups"
    calls = db.table.call_count
    assert client.get("/api/metrics/agent-roster?tz=0").status_code == 200
    assert db.table.call_count == calls
    assert client.get("/api/metrics/agent-roster?tz=9999").status_code == 422
