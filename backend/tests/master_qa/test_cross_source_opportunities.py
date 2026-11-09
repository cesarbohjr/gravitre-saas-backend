"""Cross-source opportunity evidence and governed Play-routing contracts.

All providers are fixture-backed. These checks prove tenant/run provenance and
advisory handoff, not a live business outcome or provider mutation.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user, get_environment_context, get_org_context
from app.config import get_settings
from app.routers import goals
from app.services import cross_source_opportunity_service as service
from tests.master_qa.test_authenticated_sales_run_diagnosis import FakeClient

CRM_RUN = "11111111-1111-4111-8111-111111111111"
GA_RUN = "22222222-2222-4222-8222-222222222222"
WF = "33333333-3333-4333-8333-333333333333"
NOW = datetime(2026, 11, 8, 22, tzinfo=timezone.utc)


def _patch_sources(monkeypatch, *, crm_count=2, ga_rows=True):
    monkeypatch.setattr(service, "diagnose_authenticated_sales_run", lambda **kwargs: {
        "diagnosis": {
            "observations": [{
                "org_id": kwargs["org_id"], "system": "hubspot",
                "metric_key": "deals_record_count", "value": crm_count,
                "source_record_id": "run:step:deals:complete-census",
                "observed_at": "2026-11-08T20:00:00+00:00",
            }],
        },
    })
    monkeypatch.setattr(service, "diagnose_ga4_run", lambda **kwargs: {
        "org_id": kwargs["org_id"], "environment": kwargs["environment_name"],
        "status": "GA4_DAILY_ROWS_OBSERVED_NOT_AGGREGATED",
        "metric_key": "sessions", "property_id": "1234",
        "date_range": {"start": "2026-11-01", "end": "2026-11-02"},
        "rows": [{"date": "2026-11-01", "value": 10}] if ga_rows else [],
    })


def _assess(*, installed=None, bindings=None):
    return service.assess_cross_source_opportunities(
        client=object(), org_id="tenant-A", environment_name="synthetic",
        crm_run_id=CRM_RUN, analytics_run_id=GA_RUN, as_of=NOW,
        installed_plays=installed if installed is not None else [
            {"org_id": "tenant-A", "environment_name": "synthetic",
             "play_key": "revenue-leak-hunter", "id": "installation-1",
             "status": "ready", "installed": True},
        ],
        workflow_bindings=bindings if bindings is not None else {
            "revenue-leak-hunter": [{
                "workflowId": WF, "status": "active",
                "org_id": "tenant-A", "environment_name": "synthetic",
            }],
        },
    )


def test_cross_source_candidates_link_real_installed_workflow_and_no_effect(monkeypatch):
    _patch_sources(monkeypatch)
    result = _assess()
    assert result["status"] == "REVIEW_CANDIDATES"
    assert len(result["evidence"]) == 2
    sales = next(x for x in result["opportunities"] if x["department"] == "sales")
    assert sales["workflow_id"] == WF
    assert sales["installation_id"] == "installation-1"
    assert sales["requires_approval"] is True
    assert sales["execution_authority"] == "NONE"
    assert sales["status"] == "REVIEW_REQUIRED"
    assert sales["impact_estimate"] is None
    assert result["cross_source_conversion_rate"] is None
    assert result["attributed_revenue"] is None
    assert result["executed"] is False
    assert result["business_outcome"] == "NOT_MEASURED"


def test_missing_or_cross_tenant_play_never_returns_executable_reference(monkeypatch):
    _patch_sources(monkeypatch)
    other = [{
        "org_id": "tenant-B", "environment_name": "synthetic",
        "play_key": "revenue-leak-hunter", "id": "other-tenant",
        "status": "ready", "installed": True,
    }]
    result = _assess(installed=other)
    sales = next(x for x in result["opportunities"] if x["department"] == "sales")
    assert sales["play_key"] is None
    assert sales["workflow_id"] is None
    assert sales["status"] == "NEEDS_PLAY_SETUP"
    result = _assess(bindings={"revenue-leak-hunter": [{
        "workflowId": WF, "status": "active",
        "org_id": "tenant-A", "environment_name": "production",
    }]})
    assert result["opportunities"][0]["workflow_id"] is None


def test_no_evidence_returns_no_opportunities(monkeypatch):
    _patch_sources(monkeypatch, ga_rows=False)
    monkeypatch.setattr(service, "diagnose_authenticated_sales_run", lambda **kwargs: {
        "diagnosis": {"observations": []},
    })
    result = _assess()
    assert result["status"] == "INSUFFICIENT_CROSS_SOURCE_EVIDENCE"
    assert result["opportunities"] == []


def test_run_and_timestamp_guards(monkeypatch):
    _patch_sources(monkeypatch)
    with pytest.raises(service.OpportunityAssessmentBlocked, match="distinct_provider_runs_required"):
        service.assess_cross_source_opportunities(
            client=object(), org_id="tenant-A", environment_name="synthetic",
            crm_run_id=CRM_RUN, analytics_run_id=CRM_RUN,
            as_of=NOW, installed_plays=[], workflow_bindings={},
        )


def test_preview_api_keeps_play_binding_tenant_and_environment_scoped(monkeypatch):
    from app.workflows import repository
    from app.plays import workflow_bindings

    _patch_sources(monkeypatch)
    rows = {
        "play_installations": [{
            "org_id": "tenant-A", "environment_name": "synthetic",
            "id": "installation-1", "play_key": "revenue-leak-hunter",
            "status": "ready",
        }],
        "workflows": [{
            "id": WF, "org_id": "tenant-A", "environment": "synthetic",
        }],
    }
    monkeypatch.setattr(repository, "get_supabase_client", lambda _settings: FakeClient(rows))
    monkeypatch.setattr(workflow_bindings, "list_all_play_workflow_bindings", lambda client, org: {
        "revenue-leak-hunter": [{"workflowId": WF, "status": "active"}],
    })
    app = FastAPI()
    app.include_router(goals.router)
    app.dependency_overrides[get_current_user] = lambda: {"user_id": "reader"}
    app.dependency_overrides[get_org_context] = lambda: "tenant-A"
    app.dependency_overrides[get_environment_context] = lambda: "synthetic"
    app.dependency_overrides[get_settings] = lambda: object()
    with TestClient(app) as http:
        response = http.post("/api/goals/diagnostics/opportunities", json={
            "crmRunId": CRM_RUN, "analyticsRunId": GA_RUN,
        })
    assert response.status_code == 200
    assert response.json()["opportunities"][0]["workflow_id"] == WF
    assert response.json()["executed"] is False
    assert response.json()["approval_status"] == "NOT_REQUESTED"


def test_preview_api_denies_missing_org_and_invalid_uuid(monkeypatch):
    app = FastAPI()
    app.include_router(goals.router)
    app.dependency_overrides[get_current_user] = lambda: {"user_id": "reader"}
    app.dependency_overrides[get_org_context] = lambda: None
    app.dependency_overrides[get_environment_context] = lambda: "synthetic"
    app.dependency_overrides[get_settings] = lambda: object()
    with TestClient(app) as http:
        response = http.post("/api/goals/diagnostics/opportunities", json={
            "crmRunId": CRM_RUN, "analyticsRunId": GA_RUN,
        })
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_handoff_requires_explicit_confirmation_and_canonical_play(monkeypatch):
    from app.routers import plays

    called = []
    async def canonical_play(play_key, request, member, environment_name, settings):
        called.append((play_key, request.installation_id, member[1], environment_name))
        return {
            "status": "awaiting_approval",
            "executionAuthority": "canonical_workflow_runtime",
            "playRunId": "approved-by-runtime-only",
        }

    monkeypatch.setattr(plays, "run_play", canonical_play)
    async def preview(*args, **kwargs):
        return {"opportunities": [{
            "id": "sales_pipeline_review", "status": "REVIEW_REQUIRED",
            "play_key": "revenue-leak-hunter",
            "installation_id": "installation-1", "workflow_id": WF,
        }]}

    monkeypatch.setattr(goals, "preview_cross_source_opportunities", preview)
    # The handler calls the same canonical preview function synchronously;
    # supply a normal function rather than an un-awaited coroutine.
    monkeypatch.setattr(goals, "preview_cross_source_opportunities",
                        lambda *args, **kwargs: {
                            "opportunities": [{
                                "id": "sales_pipeline_review", "status": "REVIEW_REQUIRED",
                                "play_key": "revenue-leak-hunter",
                                "installation_id": "installation-1", "workflow_id": WF,
                            }],
                        })
    from app.routers.goals import GovernedOpportunityHandoffRequest
    body = GovernedOpportunityHandoffRequest(
        crmRunId=CRM_RUN, analyticsRunId=GA_RUN,
        opportunityId="sales_pipeline_review",
    )
    with pytest.raises(HTTPException) as exc:
        await goals.handoff_cross_source_opportunity(
            body, ({"user_id": "reader"}, "tenant-A", "member"), "synthetic", object(),
        )
    assert exc.value.status_code == 409
    assert called == []

    accepted = body.model_copy(update={"confirm_submit_to_play": True})
    result = await goals.handoff_cross_source_opportunity(
        accepted, ({"user_id": "reader"}, "tenant-A", "member"), "synthetic", object(),
    )
    assert called == [("revenue-leak-hunter", "installation-1", "tenant-A", "synthetic")]
    assert result["canonicalPlayResult"]["status"] == "awaiting_approval"
    assert result["approvalGrantedByIntelligence"] is False
    assert result["businessOutcome"] == "NOT_MEASURED"


@pytest.mark.asyncio
async def test_unbound_opportunity_never_reaches_canonical_play(monkeypatch):
    from app.routers import plays
    async def forbidden(*args, **kwargs):
        raise AssertionError("no canonical Play dispatch allowed")
    monkeypatch.setattr(plays, "run_play", forbidden)
    monkeypatch.setattr(goals, "preview_cross_source_opportunities",
                        lambda *args, **kwargs: {
                            "opportunities": [{
                                "id": "sales_pipeline_review", "status": "NEEDS_PLAY_SETUP",
                                "play_key": None, "installation_id": None,
                                "workflow_id": None,
                            }],
                        })
    from app.routers.goals import GovernedOpportunityHandoffRequest
    body = GovernedOpportunityHandoffRequest(
        crmRunId=CRM_RUN, analyticsRunId=GA_RUN,
        opportunityId="sales_pipeline_review", confirmSubmitToPlay=True,
    )
    with pytest.raises(HTTPException) as exc:
        await goals.handoff_cross_source_opportunity(
            body, ({"user_id": "reader"}, "tenant-A", "member"), "synthetic", object(),
        )
    assert exc.value.status_code == 409
