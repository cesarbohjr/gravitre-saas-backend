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
            "required_approvals": 1, "environment": "synthetic",
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
