"""STA-124: Integration health score service."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from app.services.integration_health_score_service import (
    compute_integration_health_score,
    get_integration_health_score,
    grade_from_score,
    list_integration_health_history,
    record_integration_health_snapshot,
    score_agent_utilization,
    score_approval_latency,
    score_connectors_live,
    score_workflow_success,
)


def _table(select_data: list | None = None) -> MagicMock:
    mock = MagicMock()
    mock.select.return_value = mock
    mock.eq.return_value = mock
    mock.gte.return_value = mock
    mock.order.return_value = mock
    mock.limit.return_value = mock
    mock.execute.return_value = MagicMock(data=select_data or [])

    insert_mock = MagicMock()
    insert_mock.execute.return_value = MagicMock(data=[])
    mock.insert.return_value = insert_mock

    return mock


def test_score_connectors_live_all_active():
    dim = score_connectors_live(
        [
            {"status": "active", "type": "hubspot"},
            {"status": "active", "type": "slack"},
        ]
    )
    assert dim["score"] == 100
    assert dim["activeConnectors"] == 2


def test_score_connectors_live_penalizes_unhealthy():
    dim = score_connectors_live(
        [
            {"status": "active", "type": "hubspot"},
            {"status": "unhealthy", "type": "slack"},
        ]
    )
    assert dim["score"] < 100


def test_score_workflow_success_rate():
    dim = score_workflow_success(
        [
            {"status": "completed"},
            {"status": "completed"},
            {"status": "failed"},
        ]
    )
    assert dim["successRate"] == 66.7
    assert dim["score"] == 50


def test_score_agent_utilization():
    dim = score_agent_utilization(
        [
            {"status": "completed"},
            {"status": "completed"},
            {"status": "completed"},
            {"status": "failed"},
        ]
    )
    assert dim["utilizationRate"] == 75.0
    assert dim["score"] == 100


def test_score_approval_latency_fast():
    run_created = datetime(2026, 6, 1, 10, 0, tzinfo=timezone.utc)
    approval_created = datetime(2026, 6, 1, 10, 30, tzinfo=timezone.utc)
    dim = score_approval_latency(
        [{"id": "run-1", "created_at": run_created.isoformat(), "status": "completed"}],
        [{"run_id": "run-1", "created_at": approval_created.isoformat(), "status": "approved"}],
    )
    assert dim["score"] == 100
    assert dim["p95LatencyMinutes"] == 30.0


def test_compute_integration_health_score_weighted():
    result = compute_integration_health_score(
        connectors=[{"status": "active"}],
        exec_runs=[{"status": "completed"}, {"status": "completed"}],
        agent_jobs=[{"status": "completed"}],
        approvals=[],
    )
    assert 0 <= result["score"] <= 100
    assert result["grade"] in {"healthy", "at_risk", "critical"}
    assert len(result["dimensions"]) == 4


def test_grade_from_score_bands():
    assert grade_from_score(90) == "healthy"
    assert grade_from_score(70) == "at_risk"
    assert grade_from_score(40) == "critical"


@patch("app.services.integration_health_score_service.fetch_health_inputs")
def test_get_integration_health_score(mock_fetch):
    mock_fetch.return_value = {
        "connectors": [{"status": "active"}],
        "execRuns": [{"status": "completed"}],
        "agentJobs": [{"status": "completed"}],
        "approvals": [],
    }
    client = MagicMock()
    health = get_integration_health_score(client, "org-1", lookback_days=30)
    assert "score" in health
    assert health["lookbackDays"] == 30


@patch("app.services.integration_health_score_service.write_audit_event")
@patch("app.services.integration_health_score_service.get_integration_health_score")
def test_record_integration_health_snapshot(mock_health, mock_audit):
    mock_health.return_value = {
        "score": 88,
        "grade": "healthy",
        "dimensions": {},
        "risks": [],
        "weights": {},
        "lookbackDays": 30,
        "computedAt": "2026-06-09T00:00:00+00:00",
    }
    table = _table([])
    table.insert.return_value.execute.return_value = MagicMock(
        data=[
            {
                "id": "snap-1",
                "org_id": "org-1",
                "score": 88,
                "grade": "healthy",
                "dimensions": {},
                "risks": [],
                "lookback_days": 30,
                "recorded_at": "2026-06-09T00:00:00+00:00",
            }
        ]
    )
    client = MagicMock()
    client.table.return_value = table
    result = record_integration_health_snapshot(client, "org-1", actor_id="user-1")
    assert result["snapshot"]["score"] == 88
    mock_audit.assert_called_once()


def test_list_integration_health_history():
    table = _table(
        [
            {
                "id": "snap-1",
                "org_id": "org-1",
                "score": 80,
                "grade": "at_risk",
                "dimensions": {},
                "risks": [],
                "lookback_days": 30,
                "recorded_at": "2026-06-09T00:00:00+00:00",
            }
        ]
    )
    client = MagicMock()
    client.table.return_value = table
    rows = list_integration_health_history(client, "org-1")
    assert rows[0]["grade"] == "at_risk"


def test_list_integration_health_history_missing_table():
    table = _table([])
    table.execute.side_effect = Exception('relation "integration_health_snapshots" does not exist')
    client = MagicMock()
    client.table.return_value = table
    assert list_integration_health_history(client, "org-1") == []
