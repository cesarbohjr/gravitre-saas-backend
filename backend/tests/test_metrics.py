"""Metrics dashboard regression tests (BUILD/INSIGHTS audit spec)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.metrics.service import weekly_throughput_metrics
from tests.support.build_insights import authenticate, chain_mock, clear_overrides, client, make_test_settings


@pytest.fixture(autouse=True)
def _reset_deps():
    yield
    clear_overrides()


def _metrics_client(*, workflow_defs=None, runs=None, connectors=None) -> MagicMock:
    client = MagicMock()

    def _table(name: str) -> MagicMock:
        table = MagicMock()
        if name == "workflow_defs":
            table.select.return_value = workflow_defs or chain_mock(data=[])
        elif name == "workflow_runs":
            table.select.return_value = runs or chain_mock(data=[])
        elif name == "connectors":
            table.select.return_value = connectors or chain_mock(data=[])
        return table

    client.table.side_effect = _table
    return client


@patch("app.routers.metrics.create_client")
def test_summary_calculates_from_real_data(mock_create):
    mock_create.return_value = _metrics_client(
        workflow_defs=chain_mock(data=[{"id": "wf-1", "status": "active"}]),
        runs=chain_mock(
            data=[
                {"id": "r1", "status": "completed", "duration_ms": 100},
                {"id": "r2", "status": "failed", "duration_ms": 200},
            ]
        ),
        connectors=chain_mock(
            data=[
                {"id": "c1", "status": "active"},
                {"id": "c2", "status": "inactive"},
            ]
        ),
    )

    with patch("app.routers.metrics.overview_metrics", return_value={"range": "7d", "ingestion": {"chunks_embedded_total": 1200}, "rag": {"retrieval_requests_total": 0}}):
        authenticate()
        response = client.get("/api/metrics/overview?range=7d")

    assert response.status_code == 200
    body = response.json()
    assert body["totalRuns"] == 2
    assert body["successRate"] == 50.0
    assert body["recordsProcessed"] == 1200
    assert body["avgLatency"] == 150.0
    assert body["activeConnectors"] == 1
    assert body["totalConnectors"] == 2


@patch("app.routers.metrics.create_client")
def test_no_hardcoded_values_in_insights(mock_create):
    mock_create.return_value = _metrics_client(
        runs=chain_mock(data=[]),
        connectors=chain_mock(
            data=[
                {"id": "c1", "status": "active"},
                {"id": "c2", "status": "inactive"},
            ]
        ),
    )
    authenticate()
    response = client.get("/api/metrics/insights?range=7d")
    assert response.status_code == 200
    titles = [item["title"] for item in response.json()["insights"]]
    assert "Latency spike detected at 14:32" not in titles


@patch("app.routers.metrics.create_client")
def test_execution_volume_returns_time_series(mock_create):
    mock_create.return_value = _metrics_client(
        runs=chain_mock(
            data=[
                {"created_at": "2026-06-07T10:00:00+00:00", "status": "completed"},
                {"created_at": "2026-06-07T11:00:00+00:00", "status": "failed"},
            ]
        ),
    )
    authenticate()
    response = client.get("/api/metrics/runs?range=7d")
    assert response.status_code == 200
    body = response.json()
    assert "series" in body
    assert "runVolume" in body
    assert body["runVolume"][0]["time"] == "2026-06-07"
    assert body["runVolume"][0]["completed"] == 1


@patch("app.routers.metrics.create_client")
def test_metrics_export_csv(mock_create):
    mock_create.return_value = _metrics_client(
        workflow_defs=chain_mock(data=[]),
        runs=chain_mock(data=[]),
        connectors=chain_mock(data=[]),
    )
    with patch("app.routers.metrics.overview_metrics", return_value={"range": "7d", "ingestion": {}, "rag": {}}):
        authenticate()
        response = client.get("/api/metrics/export?range=7d&format=csv")

    assert response.status_code == 200
    assert "text/csv" in response.headers.get("content-type", "")
    assert "Total Runs" in response.text


@patch("app.routers.metrics.weekly_throughput_metrics")
def test_weekly_throughput_endpoint(mock_weekly):
    mock_weekly.return_value = {
        "weekStart": "2026-06-08",
        "target": 100,
        "days": [{"day": "Mon", "records": 50, "target": 100}],
    }
    authenticate()
    response = client.get("/api/metrics/weekly-throughput")
    assert response.status_code == 200
    assert response.json()["days"][0]["records"] == 50


@patch("app.metrics.service._client")
@patch("app.metrics.service._start_of_week_utc")
def test_meson_insights_generated_from_operational_data(mock_week_start, mock_client):
    from datetime import datetime, timezone
    from types import SimpleNamespace

    mock_week_start.return_value = datetime(2026, 6, 8, 0, 0, tzinfo=timezone.utc)

    def _table(_name: str) -> MagicMock:
        chain = MagicMock()
        chain.select.return_value = chain
        chain.eq.return_value = chain
        chain.gte.return_value = chain
        chain.execute.return_value = SimpleNamespace(data=[])
        return chain

    mock_client.return_value = MagicMock()
    mock_client.return_value.table.side_effect = _table

    result = weekly_throughput_metrics(make_test_settings(), "org-1")
    assert len(result["days"]) == 7
    assert result["target"] == 0
