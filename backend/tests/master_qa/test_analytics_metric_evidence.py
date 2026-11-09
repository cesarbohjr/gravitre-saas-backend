"""GA4 read-only evidence certification using tenant-scoped repository queries.

No provider writes or live OAuth credentials; these are synthetic GA4
responses flowing through the existing persisted workflow repository.
"""
from __future__ import annotations

from copy import deepcopy

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user, get_environment_context, get_org_context
from app.config import get_settings
from app.routers import goals
from app.services.analytics_metric_evidence import AnalyticsEvidenceBlocked, diagnose_ga4_run
from tests.master_qa.test_authenticated_sales_run_diagnosis import FakeClient, RUN_ID, WF_ID


def _rows():
    return {
        "workflow_runs": [{
            "id": RUN_ID, "org_id": "tenant-A", "environment": "synthetic",
            "workflow_id": WF_ID, "run_type": "execute", "status": "completed",
            "definition_snapshot": {"steps": [{
                "id": "ga4-read", "type": "invoke_tool",
                "config": {
                    "action": "analytics.reports.run",
                    "start_date": "2026-11-01", "end_date": "2026-11-02",
                    "dimensions": ["date"], "metrics": ["sessions"],
                },
            }]},
        }],
        "workflow_steps": [{
            "run_id": RUN_ID, "org_id": "tenant-A", "step_id": "ga4-read",
            "step_index": 0, "status": "completed",
            "output_snapshot": {
                "invoke_action": "analytics.reports.run", "success": True,
                "property_id": "123456",
                "report": {
                    "metricHeaders": [{"name": "sessions", "type": "TYPE_INTEGER"}],
                    "dimensionHeaders": [{"name": "date"}],
                    "rowCount": 2,
                    "rows": [
                        {"dimensionValues": [{"value": "20261101"}],
                         "metricValues": [{"value": "20"}]},
                        {"dimensionValues": [{"value": "20261102"}],
                         "metricValues": [{"value": "25"}]},
                    ],
                    "metadata": {"subjectToThresholding": False, "dataLossFromOtherRow": False},
                },
            },
        }],
        "workflows": [],
        "workflow_defs": [],
    }


def _diagnose(rows=None, org="tenant-A", env="synthetic"):
    return diagnose_ga4_run(client=FakeClient(rows or _rows()), org_id=org,
                            environment_name=env, run_id=RUN_ID)


def test_ga4_metric_rows_preserve_property_date_and_provenance():
    result = _diagnose()
    assert result["status"] == "GA4_DAILY_ROWS_OBSERVED_NOT_AGGREGATED"
    assert result["property_id"] == "123456"
    assert result["metric_key"] == "sessions"
    assert result["rows"] == [
        {"date": "2026-11-01", "value": 20},
        {"date": "2026-11-02", "value": 25},
    ]
    assert result["business_outcome"] == "NOT_MEASURED"
    assert result["recommended_writes"] == []


@pytest.mark.parametrize("org,env", [
    ("tenant-B", "synthetic"), ("tenant-A", "production"),
])
def test_ga4_tenant_and_environment_are_isolated(org, env):
    assert _diagnose(org=org, env=env) is None


@pytest.mark.parametrize("field,value", [
    ("status", "running"), ("status", "failed"), ("run_type", "dry_run"),
])
def test_ga4_requires_completed_real_workflow(field, value):
    rows = _rows()
    rows["workflow_runs"][0][field] = value
    with pytest.raises(AnalyticsEvidenceBlocked, match="completed_ga4_execution_required"):
        _diagnose(rows)


@pytest.mark.parametrize("mutation,error", [
    (("metadata", "subjectToThresholding", True), "ga4_privacy_threshold_or_data_loss"),
    (("metadata", "dataLossFromOtherRow", True), "ga4_privacy_threshold_or_data_loss"),
    (("rowCount", None, 3), "ga4_incomplete_report_coverage"),
    (("metricHeaders", None, [{"name": "conversions"}]), "ga4_metric_header_mismatch"),
    (("dimensionHeaders", None, [{"name": "sessionCampaignName"}]), "ga4_dimension_header_mismatch"),
])
def test_ga4_rejects_incomplete_or_misidentified_report(mutation, error):
    rows = _rows()
    report = rows["workflow_steps"][0]["output_snapshot"]["report"]
    field, nested, value = mutation
    if nested:
        report[field][nested] = value
    else:
        report[field] = value
    with pytest.raises(AnalyticsEvidenceBlocked, match=error):
        _diagnose(rows)


def test_ga4_rejects_default_implicit_dimensions_and_unsupported_metrics():
    rows = _rows()
    config = rows["workflow_runs"][0]["definition_snapshot"]["steps"][0]["config"]
    for field, value in [("dimensions", ["sessionCampaignName"]), ("metrics", ["purchaseRevenue"])]:
        modified = deepcopy(rows)
        modified["workflow_runs"][0]["definition_snapshot"]["steps"][0]["config"][field] = value
        with pytest.raises(AnalyticsEvidenceBlocked, match="explicit_ga4_dimension_and_metric_required"):
            _diagnose(modified)


def test_ga4_does_not_accept_hubspot_action_or_output():
    rows = _rows()
    rows["workflow_runs"][0]["definition_snapshot"]["steps"][0]["config"]["action"] = "hubspot.deals.search"
    with pytest.raises(AnalyticsEvidenceBlocked, match="unsupported_ga4_action"):
        _diagnose(rows)


def _http(monkeypatch, rows=None, *, org="tenant-A", authenticated=True):
    from app.workflows import repository
    monkeypatch.setattr(repository, "get_supabase_client", lambda settings: FakeClient(rows or _rows()))
    app = FastAPI()
    app.include_router(goals.router)
    if authenticated:
        app.dependency_overrides[get_current_user] = lambda: {"user_id": "user-A"}
    else:
        def unauthenticated():
            raise HTTPException(status_code=401, detail="Authentication required")
        app.dependency_overrides[get_current_user] = unauthenticated
    app.dependency_overrides[get_org_context] = lambda: org
    app.dependency_overrides[get_environment_context] = lambda: "synthetic"
    app.dependency_overrides[get_settings] = lambda: object()
    return TestClient(app)


def test_ga4_goal_api_is_read_only_and_authenticated(monkeypatch):
    endpoint = f"/api/goals/diagnostics/analytics/runs/{RUN_ID}"
    with _http(monkeypatch) as http:
        response = http.get(endpoint)
    assert response.status_code == 200
    assert response.json()["rows"][0]["value"] == 20
    for authenticated, org, status in [
        (False, "tenant-A", 401), (True, None, 403), (True, "tenant-B", 404),
    ]:
        with _http(monkeypatch, org=org, authenticated=authenticated) as http:
            denied = http.get(endpoint)
        assert denied.status_code == status
        assert "123456" not in denied.text
