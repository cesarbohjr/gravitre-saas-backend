"""Persisted Play-to-measurement acceptance against disposable PostgreSQL.

Uses the canonical repository methods and actual run/approval/step/outcome
tables. Provider readbacks and source-run diagnosis remain deterministic
fixtures; live external provider acceptance is a different release gate.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from tests.db.pg_harness import requires_pg
from tests.db.test_domain_event_outbox_pg import ORG
from tests.master_qa.canonical_pg_repository import (
    PgRepositoryClient, canonical_pg_cluster,
)
from app.services.opportunity_acceptance_service import inspect_opportunity_play_run

pytestmark = requires_pg

PLAY = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
WORKFLOW = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
RUN = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
INSTALL = "dddddddd-dddd-4ddd-8ddd-dddddddddddd"
CRM = "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee"
GA = "ffffffff-ffff-4fff-8fff-ffffffffffff"
AT = "2026-11-08T20:00:00+00:00"

_EXTRA_SQL = """
CREATE TABLE public.play_installations (
    id uuid PRIMARY KEY, org_id uuid NOT NULL, environment_name text NOT NULL,
    play_key text NOT NULL, status text
);
CREATE TABLE public.agent_action_outcomes (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id uuid NOT NULL, workflow_run_id uuid NOT NULL,
    action_type text, target_entity_id text, metric_name text,
    metric_value_before float8, metric_value_after float8,
    action_taken_at timestamptz, measured_at timestamptz
);
"""


@pytest.fixture
def store(monkeypatch):
    from app.workflows import sales_growth_recipe
    from app.services import analytics_metric_evidence, outcome_verification

    with canonical_pg_cluster() as pg:
        pg.psql(_EXTRA_SQL)
        client = PgRepositoryClient(pg)
        monkeypatch.setattr(sales_growth_recipe, "diagnose_authenticated_sales_run",
                            lambda **kwargs: {"diagnosis": {
                                "status": "OBSERVATIONS_AVAILABLE",
                                "observations": [{"value": 1}],
                            }} if kwargs["run_id"] == CRM and kwargs["org_id"] == ORG else None)
        monkeypatch.setattr(analytics_metric_evidence, "diagnose_ga4_run",
                            lambda **kwargs: {
                                "status": "GA4_DAILY_ROWS_OBSERVED_NOT_AGGREGATED",
                                "rows": [{"date": "2026-11-08", "value": 14}],
                            } if kwargs["run_id"] == GA and kwargs["org_id"] == ORG else None)
        monkeypatch.setattr(outcome_verification, "is_write_action",
                            lambda name: name == "hubspot.deals.update_stage")

        client.table("play_installations").insert({
            "id": INSTALL, "org_id": ORG, "environment_name": "synthetic",
            "play_key": "revenue-leak-hunter", "status": "ready",
        }).execute()
        client.table("play_runs").insert({
            "id": PLAY, "org_id": ORG, "installation_id": INSTALL,
            "play_key": "revenue-leak-hunter",
            "operating_mode": "ACT WITH APPROVAL",
            "workflow_run_ids": [RUN], "status": "completed",
            "metadata": {"opportunity_id": "sales_pipeline_review",
                         "source_run_ids": {"crm": CRM, "analytics": GA}},
        }).execute()
        client.table("workflow_runs").insert({
            "id": RUN, "org_id": ORG, "workflow_id": WORKFLOW,
            "run_type": "execute", "status": "completed",
            "required_approvals": 1, "approval_status": "approved", "environment": "synthetic",
            "definition_snapshot": {"steps": [{
                "id": "actual-action", "type": "invoke_tool",
                "config": {"action": "hubspot.deals.update_stage"},
            }]},
            "parameters": {"play": {
                "run_id": PLAY, "installation_id": INSTALL,
                "key": "revenue-leak-hunter",
                "execution_authority": "canonical_workflow_runtime",
                "opportunity_id": "sales_pipeline_review",
                "source_run_ids": {"crm": CRM, "analytics": GA},
            }},
        }).execute()
        client.table("run_approvals").insert({
            "org_id": ORG, "run_id": RUN,
            "approver_id": "qa-human-approver", "status": "approved",
        }).execute()
        client.table("workflow_steps").insert({
            "org_id": ORG, "run_id": RUN, "step_id": "actual-action",
            "step_index": 0, "step_name": "Update deal stage",
            "step_type": "invoke_tool", "status": "completed",
            "output_snapshot": {
                "invoke_action": "hubspot.deals.update_stage",
                "outcome_verified": True,
                "verification": {
                    "verified": True, "method": "source_record_get",
                    "resource_id": "synthetic-deal-1", "verified_at": AT,
                },
            },
        }).execute()
        client.table("agent_action_outcomes").insert({
            "org_id": ORG, "workflow_run_id": RUN,
            "action_type": "hubspot.deals.update_stage",
            "target_entity_id": "synthetic-deal-1",
            "metric_name": "deal_amount",
            "metric_value_before": 100.0,
            "metric_value_after": 120.0,
            "action_taken_at": "2026-10-25T20:00:00+00:00",
            "measured_at": AT,
        }).execute()
        yield pg, client


def test_postgres_canonical_rows_certify_only_correlational_observation(store):
    pg, client = store
    result = inspect_opportunity_play_run(
        client=client, org_id=ORG, environment_name="synthetic",
        play_run_id=PLAY,
    )
    assert result["certified"] is True
    assert result["sourceEvidenceVerified"] is True
    assert result["humanApprovalVerified"] is True
    assert result["independentWriteReadbackVerified"] is True
    assert result["measurableOutcomeObserved"] is True
    assert result["businessOutcome"] == "MEASURED_CORRELATIONAL_ONLY"
    assert result["causalAttribution"] == "NOT_ESTABLISHED"
    assert pg.value("SELECT count(*) FROM public.workflow_steps") == "1"
    assert pg.value("SELECT count(*) FROM public.run_approvals") == "1"


def test_postgres_missing_measurement_blocks_certification(store):
    pg, client = store
    pg.psql("UPDATE public.agent_action_outcomes SET measured_at = NULL")
    result = inspect_opportunity_play_run(
        client=client, org_id=ORG, environment_name="synthetic",
        play_run_id=PLAY,
    )
    assert result["certified"] is False
    assert result["measurableOutcomeObserved"] is False


def test_postgres_other_tenant_and_environment_get_no_play_data(store):
    _pg, client = store
    assert inspect_opportunity_play_run(
        client=client, org_id="99999999-9999-4999-8999-999999999999",
        environment_name="synthetic", play_run_id=PLAY,
    ) is None
    assert inspect_opportunity_play_run(
        client=client, org_id=ORG, environment_name="production",
        play_run_id=PLAY,
    ) is None



def _inspect(client):
    return inspect_opportunity_play_run(client=client, org_id=ORG,
                                        environment_name="synthetic", play_run_id=PLAY)


@pytest.mark.parametrize("status", ["revoked", "pending_approval", "rejected", None])
def test_postgres_current_approval_required_despite_historical_vote(store, status):
    pg, client = store
    client.table("workflow_runs").update({"approval_status": status}).eq("id", RUN).execute()
    assert pg.value("SELECT count(*) FROM public.run_approvals WHERE status='approved'") == "1"
    report = _inspect(client)
    assert report["humanApprovalVerified"] is False
    assert report["certified"] is False


@pytest.mark.parametrize("mode", ["missing", "duplicate", "pending", "wrong_type"])
def test_postgres_requires_complete_unique_completed_steps(store, mode):
    pg, client = store
    if mode == "missing":
        run = client.table("workflow_runs").select("*").eq("id", RUN).execute().data[0]
        definition = run["definition_snapshot"]
        definition["steps"].append({"id": "unobserved", "type": "invoke_tool",
                                    "config": {"action": "hubspot.deals.update_stage"}})
        client.table("workflow_runs").update({"definition_snapshot": definition}).eq("id", RUN).execute()
    elif mode == "duplicate":
        row = client.table("workflow_steps").select("*").eq("run_id", RUN).execute().data[0]
        row.pop("id")
        client.table("workflow_steps").insert(row).execute()
    elif mode == "pending":
        pg.psql("UPDATE public.workflow_steps SET status='pending'")
    else:
        pg.psql("UPDATE public.workflow_steps SET step_type='other', output_snapshot=NULL")
    from app.services.opportunity_acceptance_service import AcceptanceEvidenceBlocked
    if mode in {"duplicate", "wrong_type"}:
        with pytest.raises(AcceptanceEvidenceBlocked, match="duplicate_persisted_workflow_step|workflow_step_type_mismatch"):
            _inspect(client)
    else:
        result = _inspect(client)
        assert result["allDefinedStepsCompleted"] is False
        assert result["executionVerified"] is False
        assert result["independentWriteReadbackVerified"] is False
        assert result["certified"] is False


@pytest.mark.parametrize("mode", ["valid", "projection_mismatch", "missing_job", "wrong_run",
                                  "wrong_actor", "wrong_environment", "wrong_opportunity",
                                  "unfinished_job", "unfinalized_run", "wrong_authority",
                                  "workflow_only", "play_only"])
def test_postgres_independent_agent_lineage_readback(store, mode):
    from tests.db.pg_harness import MIGRATIONS
    from app.operators import agent_jobs
    from app.services.opportunity_acceptance_service import AcceptanceEvidenceBlocked
    pg, client = store
    actor = "22222222-2222-4222-8222-222222222222"
    pg.psql("CREATE TABLE public.agent_jobs (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), "
            "org_id uuid NOT NULL, created_by text, environment text, kind text, session_id text, "
            "payload jsonb, status text, max_attempts integer, queued_at timestamptz, "
            "timeout_at timestamptz, retry_count integer, result jsonb, error text, "
            "finished_at timestamptz, updated_at timestamptz, started_at timestamptz, attempts integer DEFAULT 0, "
            "goal_id uuid, work_object_id uuid);")
    pg.psql((MIGRATIONS / "20261125040000_agent_job_run_binding.sql").read_text())
    pg.psql((MIGRATIONS / "20261125050000_atomic_assignment_tracking_job.sql").read_text())
    requested = {"opportunity_id": "sales_pipeline_review", "source_run_ids": {"crm": CRM, "analytics": GA},
                 "play_key": "revenue-leak-hunter", "installation_id": INSTALL, "workflow_id": WORKFLOW}
    if mode == "wrong_opportunity":
        requested["opportunity_id"] = "different"
    job = agent_jobs.create_job(client, ORG, kind="operator_task",
                                environment="other" if mode == "wrong_environment" else "synthetic",
                                created_by="99999999-9999-4999-8999-999999999999" if mode == "wrong_actor" else actor,
                                create_tracking_run=True,
                                payload={"task": "Assess", "context": {"play_handoff": requested}})
    if mode != "unfinished_job":
        assert agent_jobs.claim_job_by_id(client, job["id"])
        agent_jobs.complete_job(client, job["id"], {"aiStatus": "ok", "react_status": "completed"})
    tracking = client.table("workflow_runs").select("*").eq("id", job["bound_run_id"]).execute().data[0]
    client.table("workflow_runs").update({"status": "completed",
        "parameters": {**tracking["parameters"], "outcome_finalized": mode != "unfinalized_run"}
        }).eq("id", tracking["id"]).execute()
    lineage = {"agent_job_id": job["id"], "agent_run_id": tracking["id"], "authority": "advisory_only"}
    if mode == "missing_job":
        lineage["agent_job_id"] = "99999999-9999-4999-8999-999999999999"
    if mode == "wrong_run":
        lineage["agent_run_id"] = RUN
    if mode == "wrong_authority":
        lineage["authority"] = "approved"
    play = client.table("play_runs").select("*").eq("id", PLAY).execute().data[0]
    run = client.table("workflow_runs").select("*").eq("id", RUN).execute().data[0]
    meta, params = play["metadata"], run["parameters"]
    if mode != "workflow_only":
        meta["agent_lineage"] = dict(lineage)
    if mode != "play_only":
        params["play"]["agent_lineage"] = dict(lineage)
    if mode == "projection_mismatch":
        params["play"]["agent_lineage"]["agent_run_id"] = RUN
    client.table("play_runs").update({"metadata": meta, "created_by": actor}).eq("id", PLAY).execute()
    client.table("workflow_runs").update({"parameters": params, "triggered_by": actor}).eq("id", RUN).execute()
    if mode == "valid":
        report = _inspect(PgRepositoryClient(pg))
        assert report["agentLineageVerified"] is True
        assert report["certified"] is True
        assert report["causalAttribution"] == "NOT_ESTABLISHED"
    else:
        with pytest.raises(AcceptanceEvidenceBlocked, match="agent_play_lineage_mismatch|invalid_agent_play_lineage"):
            _inspect(PgRepositoryClient(pg))
    assert pg.value("SELECT count(*) FROM public.play_runs") == "1"
    assert pg.value("SELECT count(*) FROM public.run_approvals") == "1"
