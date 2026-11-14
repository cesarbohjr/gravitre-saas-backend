"""Authenticated sales diagnosis: persisted workflow runs, tenant fences, no writes.

Exercises the real repository query path using a disposable in-memory
Supabase-shaped reader. This is NOT a live HubSpot provider acceptance test.
"""
from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user, get_environment_context, get_org_context
from app.config import get_settings
from app.routers import goals
from app.workflows.sales_growth_recipe import GoalCompilationBlocked, diagnose_authenticated_sales_run


RUN_ID = "11111111-1111-4111-8111-111111111111"
WF_ID = "22222222-2222-4222-8222-222222222222"


def _rows():
    return {
        "workflow_runs": [{
            "id": RUN_ID, "org_id": "tenant-A", "environment": "synthetic",
            "workflow_id": WF_ID, "run_type": "execute", "status": "completed",
            "definition_snapshot": {"schema_version": "2025.1", "steps": [{
                "id": "sales-evidence-1", "type": "invoke_tool",
                "config": {"action": "hubspot.deals.search", "max_records": 250},
            }]},
        }],
        "workflow_steps": [{
            "run_id": RUN_ID, "org_id": "tenant-A",
            "step_id": "sales-evidence-1", "step_index": 0,
            "status": "completed", "completed_at": "2026-11-08T20:00:00+00:00",
            "output_snapshot": {
                "invoke_action": "hubspot.deals.search", "success": True,
                "data": {
                    "results": [{"id": "deal-1"}, {"id": "deal-2"}],
                    "coverage": {"complete": True, "returned": 2, "total_reported": 2},
                },
            },
        }],
        "workflows": [],
        "workflow_defs": [{
            "id": WF_ID, "org_id": "tenant-A", "name": "Sales growth diagnostic",
            "goal": "Increase qualified pipeline",
        }],
    }


class FakeQuery:
    def __init__(self, table, rows, calls):
        self.table = table
        self.rows = list(rows)
        self.calls = calls

    def select(self, *args):
        return self

    def eq(self, key, value):
        self.calls.append((self.table, key, value))
        self.rows = [row for row in self.rows if row.get(key) == value]
        return self

    def limit(self, count):
        self.rows = self.rows[:count]
        return self

    def order(self, *args, **kwargs):
        return self

    def execute(self):
        return SimpleNamespace(data=self.rows)


class FakeClient:
    def __init__(self, rows=None):
        self.rows = rows if rows is not None else _rows()
        self.calls = []

    def table(self, name):
        if name not in self.rows:
            raise AssertionError(f"Unexpected table {name}")
        return FakeQuery(name, self.rows[name], self.calls)


def test_real_repository_path_produces_persisted_hubspot_census():
    client = FakeClient()
    result = diagnose_authenticated_sales_run(
        client=client, org_id="tenant-A",
        environment_name="synthetic", run_id=RUN_ID,
    )
    assert result["workflowId"] == WF_ID
    assert result["diagnosis"]["status"] == "OBSERVATIONS_AVAILABLE"
    assert result["diagnosis"]["observations"][0]["value"] == 2
    assert result["diagnosis"]["business_outcome"] == "NOT_MEASURED"
    assert result["diagnosis"]["recommended_writes"] == []
    assert ("workflow_runs", "org_id", "tenant-A") in client.calls
    assert ("workflow_runs", "environment", "synthetic") in client.calls
    assert ("workflow_steps", "run_id", RUN_ID) in client.calls
    assert ("workflow_defs", "org_id", "tenant-A") in client.calls


@pytest.mark.parametrize("org,env", [
    ("tenant-B", "synthetic"),
    ("tenant-A", "production"),
])
def test_other_tenant_or_environment_cannot_retrieve_run(org, env):
    client = FakeClient()
    assert diagnose_authenticated_sales_run(
        client=client, org_id=org,
        environment_name=env, run_id=RUN_ID,
    ) is None


@pytest.mark.parametrize("field,value", [
    ("run_type", "dry_run"),
    ("status", "running"),
    ("status", "awaiting_approval"),
])
def test_not_completed_real_execution_cannot_be_diagnosed(field, value):
    rows = _rows()
    rows["workflow_runs"][0][field] = value
    with pytest.raises(GoalCompilationBlocked, match="completed_canonical_execution_required"):
        diagnose_authenticated_sales_run(
            client=FakeClient(rows), org_id="tenant-A",
            environment_name="synthetic", run_id=RUN_ID,
        )


def test_analytics_action_not_misrepresented_as_supported_hubspot_metric():
    rows = _rows()
    rows["workflow_runs"][0]["definition_snapshot"]["steps"][0]["config"]["action"] = "google_analytics.reports.run"
    with pytest.raises(GoalCompilationBlocked, match="unsupported_sales_plan_action"):
        diagnose_authenticated_sales_run(
            client=FakeClient(rows), org_id="tenant-A",
            environment_name="synthetic", run_id=RUN_ID,
        )


def test_partial_hubspot_result_remains_incomplete():
    rows = _rows()
    rows["workflow_steps"][0]["output_snapshot"]["data"]["coverage"]["complete"] = False
    result = diagnose_authenticated_sales_run(
        client=FakeClient(rows), org_id="tenant-A",
        environment_name="synthetic", run_id=RUN_ID,
    )
    assert result["diagnosis"]["status"] == "INSUFFICIENT_VERIFIED_EVIDENCE"
    assert result["diagnosis"]["observations"] == []
    assert result["diagnosis"]["findings"][0]["status"] == "PARTIAL_READ_NO_TOTAL"


def _api(monkeypatch, client, *, org="tenant-A", authenticated=True):
    from app.workflows import repository

    monkeypatch.setattr(repository, "get_supabase_client", lambda _settings: client)
    app = FastAPI()
    app.include_router(goals.router)

    if authenticated:
        app.dependency_overrides[get_current_user] = lambda: {"user_id": "reader-A"}
    else:
        def unauthorized():
            raise HTTPException(status_code=401, detail="Authentication required")
        app.dependency_overrides[get_current_user] = unauthorized

    app.dependency_overrides[get_org_context] = lambda: org
    app.dependency_overrides[get_environment_context] = lambda: "synthetic"
    app.dependency_overrides[get_settings] = lambda: object()
    return TestClient(app)


def test_authenticated_goal_api_returns_persisted_diagnosis(monkeypatch):
    with _api(monkeypatch, FakeClient()) as http:
        response = http.get(f"/api/goals/diagnostics/sales/runs/{RUN_ID}")
    assert response.status_code == 200
    assert response.json()["diagnosis"]["observations"][0]["metric_key"] == "deals_record_count"
    assert response.json()["diagnosis"]["business_outcome"] == "NOT_MEASURED"


def test_goal_api_requires_auth_and_org_and_prevents_tenant_leak(monkeypatch):
    for authenticated, org, expected in [
        (False, "tenant-A", 401),
        (True, None, 403),
        (True, "tenant-B", 404),
    ]:
        with _api(monkeypatch, FakeClient(), org=org, authenticated=authenticated) as http:
            response = http.get(f"/api/goals/diagnostics/sales/runs/{RUN_ID}")
        assert response.status_code == expected
        assert "deal-1" not in response.text


def test_goal_api_rejects_bad_run_id(monkeypatch):
    with _api(monkeypatch, FakeClient()) as http:
        response = http.get("/api/goals/diagnostics/sales/runs/not-a-uuid")
    assert response.status_code == 422


def test_canonical_workflow_mirror_can_omit_goal_but_authoring_metadata_is_required(monkeypatch):
    from app.workflows import repository

    def contract_without_goal(client, org_id, workflow_id):
        assert org_id == "tenant-A" and workflow_id == WF_ID
        return {
            "id": WF_ID, "org_id": org_id,
            "name": "Sales growth diagnostic", "goal": None,
        }

    monkeypatch.setattr(repository, "get_workflow_def", contract_without_goal)
    result = diagnose_authenticated_sales_run(
        client=FakeClient(), org_id="tenant-A",
        environment_name="synthetic", run_id=RUN_ID,
    )
    assert result["diagnosis"]["goal"] == "Increase qualified pipeline"


def test_missing_original_goal_provenance_fails_closed(monkeypatch):
    from app.workflows import repository

    monkeypatch.setattr(repository, "get_workflow_def", lambda client, org, wf: {
        "id": wf, "org_id": org, "name": "Sales growth diagnostic",
    })
    rows = _rows()
    rows["workflow_defs"] = []
    with pytest.raises(GoalCompilationBlocked, match="original_goal_metadata_required"):
        diagnose_authenticated_sales_run(
            client=FakeClient(rows), org_id="tenant-A",
            environment_name="synthetic", run_id=RUN_ID,
        )
