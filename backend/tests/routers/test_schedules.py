"""Tests for GET /api/schedules aggregation endpoint."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from app.auth.dependencies import get_current_user, get_org_context
from app.config import Settings, get_settings
from app.main import app
from app.services import schedules_aggregation_service as service_module


def _settings(**overrides) -> Settings:
    base = dict(
        app_env="dev",
        supabase_url="https://test.supabase.co",
        supabase_anon_key="anon-test",
        supabase_service_role_key="service-role-test",
        supabase_jwt_secret="jwt-secret-test",
        openai_api_key="sk-test-openai",
    )
    base.update(overrides)
    return Settings(**base)


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


def _authenticate(org_id: str = "org-1") -> None:
    app.dependency_overrides[get_current_user] = lambda: {"user_id": "user-1", "email": "u@example.com"}
    app.dependency_overrides[get_org_context] = lambda: org_id
    app.dependency_overrides[get_settings] = lambda: _settings()


async def test_list_schedules_requires_org(async_client):
    app.dependency_overrides[get_current_user] = lambda: {"user_id": "user-1", "email": "u@example.com"}
    app.dependency_overrides[get_org_context] = lambda: None
    app.dependency_overrides[get_settings] = lambda: _settings()

    resp = await async_client.get("/api/schedules")
    assert resp.status_code == 403


async def test_list_schedules_returns_merged_items(async_client, monkeypatch):
    _authenticate("org-schedules")
    captured: dict[str, object] = {}

    def fake_list_scheduled_items(client, org_id, environment_name, **kwargs):
        captured["org_id"] = org_id
        captured["environment_name"] = environment_name
        captured["kwargs"] = kwargs
        return [
            {
                "kind": "workflow",
                "id": "sched-1",
                "title": "Weekly sync",
                "status": "enabled",
                "cron": "0 8 * * 1",
                "workflowId": "wf-1",
                "occurrences": ["2026-06-09T08:00:00+00:00"],
            },
            {
                "kind": "task",
                "id": "run-1",
                "title": "Weekly sync",
                "status": "completed",
                "workflowId": "wf-1",
            },
        ]

    monkeypatch.setattr("app.routers.schedules.list_scheduled_items", fake_list_scheduled_items)
    monkeypatch.setattr("app.routers.schedules.get_supabase_client", lambda settings: MagicMock())

    resp = await async_client.get("/api/schedules?workflow_id=wf-1&kinds=workflow,task")
    assert resp.status_code == 200
    payload = resp.json()
    assert len(payload["items"]) == 2
    assert captured["org_id"] == "org-schedules"
    assert captured["kwargs"]["workflow_id"] == "wf-1"
    assert captured["kwargs"]["kinds"] == frozenset({"workflow", "task"})


async def test_list_schedules_rejects_invalid_kinds(async_client, monkeypatch):
    _authenticate()
    monkeypatch.setattr("app.routers.schedules.get_supabase_client", lambda settings: MagicMock())
    resp = await async_client.get("/api/schedules?kinds=workflow,unknown")
    assert resp.status_code == 400


def test_expand_cron_occurrences_respects_window():
    from app.workflows.cron import expand_cron_occurrences

    start = datetime(2026, 6, 1, tzinfo=timezone.utc)
    end = datetime(2026, 6, 8, tzinfo=timezone.utc)
    occurrences = expand_cron_occurrences("0 8 * * 1", start, end)
    assert occurrences
    assert all(start.isoformat() <= value < end.isoformat() for value in occurrences)


def test_default_projection_window_covers_month_plus_slack():
    start, end = service_module.default_projection_window(datetime(2026, 6, 15, tzinfo=timezone.utc))
    assert start.month == 5 and start.day == 25
    assert end.month == 7


def test_task_runs_are_the_requested_months_runs_with_failure_detail(monkeypatch):
    """A month view shows that month's runs, with duration and why a run failed."""
    from tests.services.fake_supabase_db import FakeSupabaseDB

    db = FakeSupabaseDB(range_filters=True)
    base = {"org_id": "org-1", "environment": "production", "workflow_id": "wf-1", "run_type": "execute"}
    db.tables["workflow_runs"] = [
        {**base, "id": "run-sept", "status": "completed", "created_at": "2026-09-20T08:00:00+00:00"},
        {**base, "id": "run-oct-ok", "status": "completed", "created_at": "2026-10-06T06:10:00+00:00", "duration_ms": 147000},
        {
            **base,
            "id": "run-oct-fail",
            "status": "failed",
            "created_at": "2026-10-13T02:00:00+00:00",
            "duration_ms": 19000,
            "error_message": "HubSpot   token expired\nreconnect required",
        },
        {**base, "id": "run-nov", "status": "completed", "created_at": "2026-11-02T08:00:00+00:00"},
    ]
    monkeypatch.setattr(service_module, "workflow_names_for_ids", lambda client, org_id, ids: {"wf-1": "Lead enrichment"})

    items = service_module.list_scheduled_items(
        db,
        "org-1",
        "production",
        window_start=datetime(2026, 10, 1, tzinfo=timezone.utc),
        window_end=datetime(2026, 11, 1, tzinfo=timezone.utc),
        kinds=frozenset({"task"}),
    )
    by_id = {item["id"]: item for item in items}
    assert set(by_id) == {"run-oct-ok", "run-oct-fail"}
    failed = by_id["run-oct-fail"]
    assert failed["status"] == "failed"
    assert failed["durationMs"] == 19000
    assert failed["error"] == "HubSpot token expired reconnect required"
    assert failed["workflowName"] == "Lead enrichment"
    assert "error" not in by_id["run-oct-ok"]
    assert by_id["run-oct-ok"]["durationMs"] == 147000
