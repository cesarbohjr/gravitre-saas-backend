"""Regression tests for BUILD/ACTIVITY/INSIGHTS aggregate endpoints."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user, get_environment_context, get_org_context
from app.billing.service import DEFAULT_PLANS, require_feature
from app.config import Settings, get_settings
from app.main import app
from app.routers import metrics as metrics_module
from app.routers import workflows as workflows_module

client = TestClient(app)


def _settings() -> Settings:
    return Settings(
        app_env="dev",
        supabase_url="https://test.supabase.co",
        supabase_anon_key="anon-test",
        supabase_service_role_key="service-role-test",
        supabase_jwt_secret="jwt-secret-test",
    )


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


def _authenticate(*, org_id: str = "org-1", environment: str = "production") -> None:
    app.dependency_overrides[get_current_user] = lambda: {"user_id": "user-1", "email": "u@example.com"}
    app.dependency_overrides[get_org_context] = lambda: org_id
    app.dependency_overrides[get_environment_context] = lambda: environment
    app.dependency_overrides[get_settings] = lambda: _settings()


def _mock_table(client: MagicMock, *, select_data: list | None = None) -> None:
    table = MagicMock()
    chain = MagicMock()
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.gte.return_value = chain
    chain.execute.return_value = SimpleNamespace(data=select_data or [])
    client.table.return_value = table
    table.select.return_value = chain


def test_node_plan_includes_basic_audit_logs_entitlement():
    plan = DEFAULT_PLANS["node"]
    require_feature(plan, "audit_logs")


def test_workflow_stats_returns_zeros_without_runs(monkeypatch: pytest.MonkeyPatch):
    mock_client = MagicMock()
    _mock_table(mock_client, select_data=[])

    monkeypatch.setattr(workflows_module, "get_supabase_client", lambda _settings: mock_client)
    monkeypatch.setattr(workflows_module, "list_workflows", lambda _client, _org: [{"status": "active"}])

    _authenticate()
    response = client.get("/api/workflows/stats")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["totalRunsThisWeek"] == 0
    assert body["overallSuccessRate"] is None


def test_metrics_insights_derived_from_real_state(monkeypatch: pytest.MonkeyPatch):
    mock_client = MagicMock()

    def table_side_effect(name: str):
        table = MagicMock()
        chain = MagicMock()
        chain.select.return_value = chain
        chain.eq.return_value = chain
        chain.gte.return_value = chain
        if name == "workflow_runs":
            chain.execute.return_value = SimpleNamespace(data=[])
        elif name == "connectors":
            chain.execute.return_value = SimpleNamespace(
                data=[{"id": "c1", "type": "hubspot", "status": "inactive"}]
            )
        else:
            chain.execute.return_value = SimpleNamespace(data=[])
        table.select.return_value = chain
        return table

    mock_client.table.side_effect = table_side_effect
    monkeypatch.setattr(metrics_module, "create_client", lambda *_a, **_k: mock_client)

    _authenticate()
    response = client.get("/api/metrics/insights?range=7d")

    assert response.status_code == 200
    insights = response.json()["insights"]
    assert isinstance(insights, list)
    assert len(insights) >= 1
    titles = {item["title"] for item in insights}
    assert any("connector" in title.lower() for title in titles)
    assert all("Latency spike detected at 14:32" not in item["title"] for item in insights)


def test_weekly_throughput_returns_seven_days(monkeypatch: pytest.MonkeyPatch):
    from datetime import datetime, timezone

    mock_client = MagicMock()
    monday = datetime(2026, 6, 9, 12, 0, tzinfo=timezone.utc)

    def table_side_effect(name: str):
        table = MagicMock()
        chain = MagicMock()
        chain.select.return_value = chain
        chain.eq.return_value = chain
        chain.gte.return_value = chain
        if name == "rag_ingest_jobs":
            chain.execute.return_value = SimpleNamespace(
                data=[{"created_at": monday.isoformat(), "chunk_count": 42, "status": "completed"}]
            )
        else:
            chain.execute.return_value = SimpleNamespace(data=[])
        table.select.return_value = chain
        return table

    mock_client.table.side_effect = table_side_effect
    monkeypatch.setattr(metrics_module, "weekly_throughput_metrics", lambda _settings, _org: {
        "weekStart": "2026-06-09",
        "target": 46,
        "days": [
            {"day": "Mon", "records": 42, "target": 46},
            {"day": "Tue", "records": 0, "target": 46},
            {"day": "Wed", "records": 0, "target": 46},
            {"day": "Thu", "records": 0, "target": 46},
            {"day": "Fri", "records": 0, "target": 46},
            {"day": "Sat", "records": 0, "target": 46},
            {"day": "Sun", "records": 0, "target": 46},
        ],
    })

    _authenticate()
    response = client.get("/api/metrics/weekly-throughput")

    assert response.status_code == 200
    body = response.json()
    assert len(body["days"]) == 7
    assert body["days"][0]["day"] == "Mon"
    assert body["days"][0]["records"] == 42
    assert body["target"] == 46
