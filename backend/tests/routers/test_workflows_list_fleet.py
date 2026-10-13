"""GET /api/workflows carries the run facts the Workflows page shows.

The list used to report whichever run row came back first as the last run and
never said whether a workflow was running, so "Running now" was always 0.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user, get_environment_context, get_org_context
from app.config import Settings, get_settings
from app.main import app
from tests.services.fake_supabase_db import FakeSupabaseDB

client = TestClient(app, raise_server_exceptions=False)


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


def _auth() -> None:
    app.dependency_overrides[get_current_user] = lambda: {"user_id": "user-1", "email": "u@example.com"}
    app.dependency_overrides[get_org_context] = lambda: "org-1"
    app.dependency_overrides[get_environment_context] = lambda: "production"
    app.dependency_overrides[get_settings] = lambda: _settings()


def _workflow(wid: str, name: str) -> dict:
    return {
        "id": wid,
        "name": name,
        "description": f"{name} description",
        "status": "active",
        "schema_version": "1",
        "updated_at": "2026-10-01T00:00:00+00:00",
    }


def test_list_reports_newest_run_live_state_recent_runs_and_departments():
    _auth()
    db = FakeSupabaseDB()
    db.tables["workflow_runs"] = [
        {"org_id": "org-1", "environment": "production", "workflow_id": "wf-1", "status": "completed", "created_at": "2026-10-10T08:00:00+00:00"},
        {"org_id": "org-1", "environment": "production", "workflow_id": "wf-1", "status": "failed", "created_at": "2026-10-12T08:00:00+00:00"},
        {"org_id": "org-1", "environment": "production", "workflow_id": "wf-2", "status": "running", "created_at": "2026-10-13T09:58:00+00:00"},
    ]
    db.tables["department_resource_assignments"] = [
        {"org_id": "org-1", "resource_type": "workflow", "resource_id": "wf-2", "department_id": "d-ops"},
    ]
    db.tables["departments"] = [{"org_id": "org-1", "id": "d-ops", "name": "Operations"}]
    with patch("app.routers.workflows.get_supabase_client", return_value=db), patch(
        "app.routers.workflows.list_workflows",
        return_value=[_workflow("wf-1", "SEO digest"), _workflow("wf-2", "Uptime watch")],
    ), patch("app.billing.seat_context.resolve_seat_context", return_value={"is_lite": False}):
        response = client.get("/api/workflows")

    assert response.status_code == 200, response.text
    rows = {row["id"]: row for row in response.json()["workflows"]}
    seo, uptime = rows["wf-1"], rows["wf-2"]
    assert seo["lastRun"] == "2026-10-12T08:00:00+00:00"
    assert seo["lastRunStatus"] == "failed"
    assert seo["isRunning"] is False
    assert [run["status"] for run in seo["recentRuns"]] == ["completed", "failed"]
    assert seo["runCount"] == 2
    assert seo["successRate"] == 50.0
    assert seo["departments"] == []
    assert uptime["isRunning"] is True
    assert uptime["departments"] == ["Operations"]


def test_list_without_runs_reports_nothing_invented():
    _auth()
    db = FakeSupabaseDB()
    with patch("app.routers.workflows.get_supabase_client", return_value=db), patch(
        "app.routers.workflows.list_workflows", return_value=[_workflow("wf-1", "Draft flow")]
    ), patch("app.billing.seat_context.resolve_seat_context", return_value={"is_lite": False}):
        response = client.get("/api/workflows")

    assert response.status_code == 200, response.text
    row = response.json()["workflows"][0]
    assert row["runCount"] == 0
    assert row["successRate"] == 0
    assert row["lastRun"] is None
    assert row["lastRunStatus"] is None
    assert row["isRunning"] is False
    assert row["recentRuns"] == []


def test_truncated_history_without_stored_totals_withholds_the_success_rate():
    """When the history read is cut short, a rate from part of the history is not published."""
    _auth()
    db = FakeSupabaseDB()
    db.tables["workflow_runs"] = [
        {"org_id": "org-1", "environment": "production", "workflow_id": "wf-1", "status": "completed", "created_at": "2026-10-10T08:00:00+00:00"},
    ]
    stored = {**_workflow("wf-2", "Counted by runtime"), "run_count": 50000, "success_rate": 97.5}
    with patch("app.routers.workflows.get_supabase_client", return_value=db), patch(
        "app.routers.workflows.list_workflows", return_value=[_workflow("wf-1", "Derived"), stored]
    ), patch("app.billing.seat_context.resolve_seat_context", return_value={"is_lite": False}), patch(
        "app.services.workflow_fleet.read_run_history", return_value=(db.tables["workflow_runs"], True)
    ):
        response = client.get("/api/workflows")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["runHistoryTruncated"] is True
    rows = {row["id"]: row for row in body["workflows"]}
    assert rows["wf-1"]["successRate"] is None
    assert rows["wf-1"]["runCount"] == 1
    assert rows["wf-1"]["runStatsComplete"] is False
    # Stored totals are complete whatever the read ceiling.
    assert rows["wf-2"]["successRate"] == 97.5
    assert rows["wf-2"]["runCount"] == 50000
    assert rows["wf-2"]["runStatsComplete"] is True
