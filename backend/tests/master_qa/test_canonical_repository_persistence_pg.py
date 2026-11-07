"""P27 persistence certification: real repository methods and SQL readback.

This proves durable run/approval/step/contract mirrors and once-only consumer
redelivery across independent SQL clients. It does not replace the separate
router-to-handler journey and it does not test external vendor readback.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from tests.db.pg_harness import requires_pg
from tests.db.test_domain_event_outbox_pg import ORG, _PsqlRpcClient
from tests.master_qa.canonical_pg_repository import (
    PgRepositoryClient, canonical_pg_cluster,
)

pytestmark = requires_pg

def test_real_repository_approval_step_and_reconnect_consumer():
    from app.workflows import repository
    from app.services import domain_events

    workflow_id = "22222222-2222-4222-8222-222222222222"
    definition = {"steps": [
        {"id": "crm-read", "name": "CRM read", "type": "invoke_tool",
         "config": {"action": "hubspot.contacts.search", "limit": 1}}
    ]}
    with canonical_pg_cluster() as pg:
        client = PgRepositoryClient(pg)
        pg.psql(f"INSERT INTO public.workflows (id, org_id, name) "
                f"VALUES ('{workflow_id}', '{ORG}', 'P27 synthetic workflow')")
        created = repository.create_execute_run(
            client=client, org_id=ORG, workflow_id=workflow_id,
            triggered_by="synthetic-actor", definition_snapshot=definition,
            parameters={"play": {"key": "customer-rescue"}}, run_hash="synthetic-p27-hash",
            status="pending_approval", approval_status="pending_approval",
            required_approvals=1, approver_roles=["admin"],
            environment_name="synthetic")
        run_id = created["id"]
        assert repository.get_run_with_steps(client, ORG, run_id, "synthetic")["status"] == "pending_approval"
        assert pg.value(f"SELECT status FROM public.runs WHERE id='{run_id}'") == "needs_approval"
        assert pg.value("SELECT count(*) FROM public.domain_event_outbox") == "0"

        first_step = repository.create_step(
            client=client, run_id=run_id, org_id=ORG,
            step_id="crm-read", step_index=0,
            step_name="CRM read", step_type="invoke_tool")
        step_id = first_step["id"]
        assert first_step["status"] == "pending"

        # The canonical approval store is written by production repository code.
        approval = repository.insert_run_approval(
            client, run_id, ORG, "synthetic-approver", "approved",
            "Approved against disposable database")
        repeated = repository.insert_run_approval(
            client, run_id, ORG, "synthetic-approver", "approved",
            "Duplicate approval callback")
        assert approval["id"] == repeated["id"]
        assert repository.get_approval_counts(client, run_id) == (1, False)
        assert pg.value(f"SELECT count(*) FROM public.run_approvals WHERE run_id='{run_id}'") == "1"

        # No unapproved or cross-tenant claim can start another run.
        foreign_org = "33333333-3333-4333-8333-333333333333"
        assert repository.try_mark_run_running(client, run_id, foreign_org) is False
        assert pg.value(f"SELECT status FROM public.workflow_runs WHERE id='{run_id}'") == "pending_approval"
        assert repository.try_mark_run_running(client, run_id, ORG) is True
        assert repository.try_mark_run_running(client, run_id, ORG) is False
        assert pg.value(f"SELECT approval_status FROM public.workflow_runs WHERE id='{run_id}'") == "approved"

        # Reconnect using a new client and read persisted approval, run and step.
        restarted = PgRepositoryClient(pg)
        assert repository.get_approval_counts(restarted, run_id) == (1, False)
        assert repository.get_run_with_steps(restarted, ORG, run_id, "synthetic")["status"] == "running"
        assert repository.get_run_with_steps(restarted, foreign_org, run_id, "synthetic") is None
        repository.set_step_running(restarted, step_id, datetime.now(timezone.utc).isoformat())
        repository.update_step(
            restarted, step_id, "completed",
            output_snapshot={"verified": True, "contact_id": "synthetic-contact-1"},
            completed_at=datetime.now(timezone.utc).isoformat())
        repository.update_run(
            restarted, run_id, "completed",
            completed_at=datetime.now(timezone.utc).isoformat(),
            approval_status="approved")
        actual = repository.get_run_with_steps(PgRepositoryClient(pg), ORG, run_id, "synthetic")
        assert actual["status"] == "completed"
        assert actual["steps"][0]["status"] == "completed"
        assert actual["steps"][0]["output_snapshot"]["verified"] is True
        assert pg.value(f"SELECT status FROM public.runs WHERE id='{run_id}'") == "completed"
        assert pg.value(f"SELECT status FROM public.run_steps WHERE id='{step_id}'") == "completed"
        assert pg.value(f"SELECT count(*) FROM public.domain_event_outbox WHERE aggregate_id='{run_id}'") == "1"

        pg.psql("CREATE TABLE public.qa_p27_restarted_consumer ("
                "event_id bigint PRIMARY KEY, org_id uuid NOT NULL, "
                "run_id uuid NOT NULL)")
        def durable_consumer(_client, event):
            assert event["aggregate_id"] == run_id and event["org_id"] == ORG
            pg.psql("INSERT INTO public.qa_p27_restarted_consumer "
                    "(event_id,org_id,run_id) "
                    f"VALUES ({int(event['id'])},'{ORG}','{run_id}') "
                    "ON CONFLICT (event_id) DO NOTHING")
        domain_events.reset_domain_event_handlers_for_tests()
        domain_events.register_domain_event_handler(
            domain_events.EVENT_EXECUTION_OUTCOME_FINALIZED,
            "qa_p27_restarted_consumer", durable_consumer)
        try:
            first = domain_events.DomainEventRelay(
                _PsqlRpcClient(pg), worker_id="p27-before-restart").run_once()
            second = domain_events.DomainEventRelay(
                _PsqlRpcClient(pg), worker_id="p27-after-restart").run_once()
        finally:
            domain_events.reset_domain_event_handlers_for_tests()
        assert first.delivered == 1
        assert second.claimed == 0
        assert pg.value("SELECT count(*) FROM public.qa_p27_restarted_consumer") == "1"
        # Terminal replay and another repository instance cannot produce a
        # second durable event or consumer side effect.
        repository.update_run(PgRepositoryClient(pg), run_id, "completed")
        assert pg.value(f"SELECT count(*) FROM public.domain_event_outbox WHERE aggregate_id='{run_id}'") == "1"
