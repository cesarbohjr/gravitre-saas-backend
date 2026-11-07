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


@pytest.mark.asyncio
async def test_canonical_postgres_denied_approval_has_no_writes(monkeypatch):
    """Actual approval route denial on the same tables, not a fake approval list."""
    from uuid import UUID
    from fastapi import HTTPException
    from app.workflows import repository
    from app.routers import workflows

    workflow_id = "22222222-2222-4222-8222-222222222222"
    with canonical_pg_cluster() as pg:
        client = PgRepositoryClient(pg)
        pg.psql(f"INSERT INTO public.workflows (id, org_id, name) "
                f"VALUES ('{workflow_id}', '{ORG}', 'P27 denied workflow')")
        run = repository.create_execute_run(
            client=client, org_id=ORG, workflow_id=workflow_id,
            triggered_by="synthetic-owner", definition_snapshot={"steps": []},
            parameters={}, run_hash="deny-test", status="pending_approval",
            approval_status="pending_approval", required_approvals=1,
            approver_roles=["admin"], environment_name="synthetic")
        run_id = run["id"]
        monkeypatch.setattr(workflows, "get_supabase_client", lambda _: client)
        monkeypatch.setattr(workflows, "get_plan_for_org", lambda *_: {})
        monkeypatch.setattr(workflows, "require_feature", lambda *_: None)
        monkeypatch.setattr(workflows, "get_run_with_steps", repository.get_run_with_steps)
        monkeypatch.setattr(workflows, "get_user_role", lambda *_: "member")
        monkeypatch.setattr(workflows, "has_capability", lambda *_: False)
        # Approval store and claim remain unpatched: any unauthorized access
        # would be visible in the underlying SQL tables.
        outbox_before = pg.value("SELECT count(*) FROM public.domain_event_outbox")
        with pytest.raises(HTTPException) as exc:
            await workflows.approve_run(
                UUID(run_id), workflows.ApproveRejectRequest(),
                {"user_id": "synthetic-unprivileged"}, ORG, "synthetic",
                type("Settings", (), {"disable_execute": False})())
        assert exc.value.status_code == 403
        assert repository.get_approval_counts(PgRepositoryClient(pg), run_id) == (0, False)
        assert pg.value(f"SELECT status FROM public.workflow_runs WHERE id='{run_id}'") == "pending_approval"
        assert pg.value("SELECT count(*) FROM public.domain_event_outbox") == outbox_before


def test_crashed_outbox_worker_lease_recovered_by_new_worker_process():
    """Actual subprocess exits after SQL claim; new relay reclaims expired lease.

    This validates the domain outbox crash boundary, not graph executor restart.
    """
    import subprocess
    import sys
    from app.workflows import repository
    from app.services import domain_events

    workflow_id = "22222222-2222-4222-8222-222222222222"
    with canonical_pg_cluster() as pg:
        client = PgRepositoryClient(pg)
        pg.psql(f"INSERT INTO public.workflows (id,org_id,name) "
                f"VALUES ('{workflow_id}','{ORG}','Crash recovery fixture')")
        created = repository.create_execute_run(
            client, ORG, workflow_id, "synthetic-actor",
            {"steps": []}, {}, "crash-recovery-hash",
            "pending_approval", "pending_approval", 1, ["admin"],
            environment_name="synthetic")
        run_id = created["id"]
        assert repository.try_mark_run_running(client, run_id, ORG)
        repository.update_run(client, run_id, "completed")
        assert pg.value(f"SELECT count(*) FROM public.domain_event_outbox "
                        f"WHERE aggregate_id='{run_id}'") == "1"

        # Simulate an abruptly killed worker process after claiming the event,
        # without acknowledging/committing delivery. PostgreSQL is independent
        # and survives the child process termination.
        script = """
import os
import psycopg
with psycopg.connect(host=os.environ['P27_PG_SOCK'],
                     port=os.environ['P27_PG_PORT'],
                     user='postgres', dbname='postgres') as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM public.claim_domain_events('crashed-worker', 1, 60)")
        row = cur.fetchone()
        assert row is not None, "expected one claim"
os._exit(73)
"""
        import os
        env = {**os.environ, "P27_PG_SOCK": str(pg.sock), "P27_PG_PORT": pg.port}
        child = subprocess.run([sys.executable, "-c", script], env=env,
                               capture_output=True, text=True, timeout=20)
        assert child.returncode == 73, child.stderr
        assert pg.value("SELECT status FROM public.domain_event_outbox") == "processing"
        assert pg.value("SELECT lease_owner FROM public.domain_event_outbox") == "crashed-worker"

        # The lease must expire before another process can claim the event.
        pg.psql("UPDATE public.domain_event_outbox "
                "SET lease_expires_at=now()-interval '1 second' "
                "WHERE lease_owner='crashed-worker'")
        pg.psql("CREATE TABLE public.qa_p27_crash_effects ("
                "event_id bigint PRIMARY KEY, run_id uuid NOT NULL)")
        def consumer(_client, event):
            assert event["aggregate_id"] == run_id
            pg.psql("INSERT INTO public.qa_p27_crash_effects (event_id,run_id) "
                    f"VALUES ({int(event['id'])},'{run_id}') "
                    "ON CONFLICT(event_id) DO NOTHING")
        domain_events.reset_domain_event_handlers_for_tests()
        domain_events.register_domain_event_handler(
            domain_events.EVENT_EXECUTION_OUTCOME_FINALIZED,
            "qa_p27_crash_recovery", consumer)
        try:
            relay = domain_events.DomainEventRelay(
                _PsqlRpcClient(pg), worker_id="replacement-worker")
            recovered = relay.run_once()
            replay = relay.run_once()
        finally:
            domain_events.reset_domain_event_handlers_for_tests()
        assert recovered.delivered == 1
        assert replay.claimed == 0
        assert pg.value("SELECT count(*) FROM public.qa_p27_crash_effects") == "1"
        assert pg.value("SELECT status FROM public.domain_event_outbox") == "delivered"
