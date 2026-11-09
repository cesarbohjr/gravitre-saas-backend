"""Evidence boundary: canonical Play -> approval -> independently verified write -> outcome.

Fixture-backed persisted records. Production connection and live provider
consent are separate exact-head release gates.
"""
from __future__ import annotations

from copy import deepcopy

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user, get_environment_context, get_org_context
from app.config import get_settings
from app.routers import goals
from app.services import outcome_verification
from app.services.opportunity_acceptance_service import (
    AcceptanceEvidenceBlocked, inspect_opportunity_play_run,
)
from tests.master_qa.test_authenticated_sales_run_diagnosis import FakeClient

ORG = "tenant-A"
PLAY_RUN = "11111111-1111-4111-8111-111111111111"
RUN = "22222222-2222-4222-8222-222222222222"
WF = "33333333-3333-4333-8333-333333333333"
INSTALL = "44444444-4444-4444-8444-444444444444"
STAMP = "2026-11-08T20:00:00+00:00"
CRM_SOURCE_RUN = "66666666-6666-4666-8666-666666666666"
GA_SOURCE_RUN = "77777777-7777-4777-8777-777777777777"


def records():
    return {
        "play_runs": [{
            "id": PLAY_RUN, "org_id": ORG, "play_key": "revenue-leak-hunter",
            "installation_id": INSTALL, "operating_mode": "ACT WITH APPROVAL",
            "workflow_run_ids": [RUN], "status": "completed",
            "metadata": {"opportunity_id": "sales_pipeline_review",
                         "source_run_ids": {"crm": CRM_SOURCE_RUN, "analytics": GA_SOURCE_RUN}},
        }],
        "play_installations": [{
            "id": INSTALL, "org_id": ORG, "environment_name": "synthetic",
            "play_key": "revenue-leak-hunter", "status": "ready",
        }],
        "workflow_runs": [{
            "id": RUN, "org_id": ORG, "environment": "synthetic",
            "workflow_id": WF, "run_type": "execute", "status": "completed",
            "required_approvals": 1,
            "parameters": {"play": {
                "run_id": PLAY_RUN, "key": "revenue-leak-hunter",
                "installation_id": INSTALL,
                "execution_authority": "canonical_workflow_runtime",
                "opportunity_id": "sales_pipeline_review",
                "source_run_ids": {"crm": CRM_SOURCE_RUN, "analytics": GA_SOURCE_RUN},
            }},
        }],
        "workflow_steps": [{
            "run_id": RUN, "org_id": ORG, "step_id": "update-deal",
            "step_index": 0, "status": "completed",
            "output_snapshot": {
                "invoke_action": "hubspot.deals.update_stage",
                "success": True, "outcome_verified": True,
                "verification": {
                    "verified": True, "method": "source_record_get",
                    "resource_id": "deal-1", "verified_at": STAMP,
                },
            },
        }],
        "run_approvals": [{
            "org_id": ORG, "run_id": RUN, "approver_id": "human-1",
            "status": "approved",
        }],
        "agent_action_outcomes": [{
            "org_id": ORG, "workflow_run_id": RUN,
            "action_type": "hubspot.deals.update_stage",
            "target_entity_id": "deal-1",
            "metric_name": "deal_amount",
            "metric_value_before": 100.0, "metric_value_after": 120.0,
            "action_taken_at": "2026-11-01T20:00:00+00:00",
            "measured_at": STAMP,
        }],
    }


@pytest.fixture(autouse=True)
def classified_write(monkeypatch):
    from app.workflows import sales_growth_recipe
    from app.services import analytics_metric_evidence

    monkeypatch.setattr(outcome_verification, "is_write_action",
                        lambda action: action == "hubspot.deals.update_stage")
    monkeypatch.setattr(sales_growth_recipe, "diagnose_authenticated_sales_run",
                        lambda **kw: {"diagnosis": {"status": "OBSERVATIONS_AVAILABLE",
                                                    "observations": [{"value": 1}]}}
                        if kw["run_id"] == CRM_SOURCE_RUN else None)
    monkeypatch.setattr(analytics_metric_evidence, "diagnose_ga4_run",
                        lambda **kw: {"status": "GA4_DAILY_ROWS_OBSERVED_NOT_AGGREGATED",
                                      "rows": [{"date": "2026-11-08", "value": 12}]}
                        if kw["run_id"] == GA_SOURCE_RUN else None)


def inspect(rows=None, org=ORG, env="synthetic"):
    return inspect_opportunity_play_run(
        client=FakeClient(rows if rows is not None else records()),
        org_id=org, environment_name=env, play_run_id=PLAY_RUN,
    )


def test_complete_chain_reports_measured_correlational_not_caused():
    result = inspect()
    assert result["status"] == "OBSERVED_CHAIN_COMPLETE"
    assert result["certified"] is True
    assert result["humanApprovalVerified"] is True
    assert result["independentWriteReadbackVerified"] is True
    assert result["measurableOutcomeObserved"] is True
    assert result["workflowRuns"][0]["observedOutcomes"][0]["delta"] == 20.0
    assert result["businessOutcome"] == "MEASURED_CORRELATIONAL_ONLY"
    assert result["causalAttribution"] == "NOT_ESTABLISHED"


@pytest.mark.parametrize("field,update", [
    ("run_approvals", {"status": "rejected"}),
    ("workflow_runs", {"status": "awaiting_approval"}),
    ("workflow_steps", {"status": "failed"}),
    ("agent_action_outcomes", {"metric_value_after": None}),
    ("agent_action_outcomes", {"measured_at": None}),
])
def test_unsettled_approval_execution_or_outcome_cannot_certify(field, update):
    rows = records()
    rows[field][0].update(update)
    result = inspect(rows)
    assert result["status"] == "ACCEPTANCE_INCOMPLETE"
    assert result["certified"] is False


@pytest.mark.parametrize("update", [
    {"outcome_verified": False},
    {"verification": {"verified": True}},
    {"verification": {"verified": False, "method": "source_record_get",
                      "resource_id": "deal-1", "verified_at": STAMP}},
])
def test_provider_receipt_must_name_independent_verifier_and_record(update):
    rows = records()
    rows["workflow_steps"][0]["output_snapshot"].update(update)
    result = inspect(rows)
    assert result["certified"] is False
    assert result["independentWriteReadbackVerified"] is False


def test_wrong_tenant_or_environment_must_not_return_records():
    assert inspect(org="tenant-B") is None
    assert inspect(env="production") is None


def test_unbound_workflow_run_cannot_be_copied_between_plays():
    rows = records()
    rows["workflow_runs"][0]["parameters"]["play"]["run_id"] = "another-play"
    with pytest.raises(AcceptanceEvidenceBlocked, match="unbound_canonical_play_run"):
        inspect(rows)


def test_no_execution_start_is_not_a_certification():
    rows = records()
    rows["play_runs"][0]["workflow_run_ids"] = []
    result = inspect(rows)
    assert result["status"] == "NO_CANONICAL_WORKFLOW_RUNS"
    assert result["certified"] is False


def test_analytics_metric_cannot_be_claimed_as_verified_hubspot_write_impact():
    rows = records()
    rows["agent_action_outcomes"][0]["target_entity_id"] = "other-deal"
    assert inspect(rows)["certified"] is False


def test_authenticated_acceptance_api_reads_exact_tenant_only(monkeypatch):
    from app.workflows import repository
    monkeypatch.setattr(repository, "get_supabase_client",
                        lambda _settings: FakeClient(records()))
    app = FastAPI()
    app.include_router(goals.router)
    app.dependency_overrides[get_current_user] = lambda: {"user_id": "user-A"}
    app.dependency_overrides[get_org_context] = lambda: ORG
    app.dependency_overrides[get_environment_context] = lambda: "synthetic"
    app.dependency_overrides[get_settings] = lambda: object()
    with TestClient(app) as http:
        url = f"/api/goals/diagnostics/opportunities/play-runs/{PLAY_RUN}/acceptance"
        resp = http.get(url)
        assert resp.status_code == 200
        assert resp.json()["certified"] is True
        app.dependency_overrides[get_org_context] = lambda: "tenant-B"
        denied = http.get(url)
        assert denied.status_code == 404
        assert "deal-1" not in denied.text


def test_missing_source_run_lineage_never_certifies_completed_play():
    rows = records()
    rows["play_runs"][0]["metadata"] = {}
    rows["workflow_runs"][0]["parameters"]["play"].pop("opportunity_id")
    rows["workflow_runs"][0]["parameters"]["play"].pop("source_run_ids")
    result = inspect(rows)
    assert result["sourceEvidenceVerified"] is False
    assert result["certified"] is False


def test_spoofed_workflow_source_lineage_fails_closed():
    rows = records()
    rows["workflow_runs"][0]["parameters"]["play"]["source_run_ids"]["crm"] = "forged"
    with pytest.raises(AcceptanceEvidenceBlocked, match="play_source_lineage_mismatch"):
        inspect(rows)


@pytest.mark.parametrize("status", ["cancelled", "failed", "partial_success"])
def test_cancelled_or_failed_play_cannot_be_certified(status):
    rows = records()
    rows["play_runs"][0]["status"] = status
    result = inspect(rows)
    assert result["playNotFailed"] is False
    assert result["certified"] is False
