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


def _fanout_run(pg):
    """A canonical run plus independently queried, synthetic consumer effects."""
    from app.workflows import repository
    workflow_id = "22222222-2222-4222-8222-222222222222"
    pg.psql(f"INSERT INTO public.workflows (id,org_id,name) VALUES ('{workflow_id}','{ORG}','Receipt recovery')")
    run = repository.create_execute_run(
        PgRepositoryClient(pg), ORG, workflow_id, "synthetic-actor", {"steps": []}, {},
        "receipt-recovery", "running", "approved", 0, [], environment_name="synthetic")
    pg.psql("CREATE TABLE public.qa_fanout_effects (channel text PRIMARY KEY)")
    pg.psql("""
CREATE FUNCTION public.qa_require_output_before_terminal() RETURNS trigger
LANGUAGE plpgsql AS $$ BEGIN
 IF NEW.status = 'completed' AND NEW.parameters->'verified_output' IS NULL THEN
  RAISE EXCEPTION 'terminal transition preceded verified output persistence';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER qa_output_before_terminal BEFORE UPDATE OF status ON public.workflow_runs
FOR EACH ROW EXECUTE FUNCTION public.qa_require_output_before_terminal();
""")
    return run["id"], workflow_id


def _sql_delivery_channel(pg, name):
    def deliver(*_args):
        # No conflict suppression: a duplicate successful callback is a defect.
        pg.psql(f"INSERT INTO public.qa_fanout_effects VALUES ('{name}')")
        return name
    return deliver


@pytest.mark.parametrize("missing_channel", ["audit", "notification", "learning"])
def test_terminal_fanout_retry_reads_independent_postgres_receipts(monkeypatch, missing_channel):
    """Actual repository, mirrors and receipts; external channels use SQL stand-ins."""
    from app.services import execution_outcome as outcome
    with canonical_pg_cluster() as pg:
        run_id, workflow_id = _fanout_run(pg)
        failed = {missing_channel}
        for function, channel in (("_write_audit", "audit"), ("_emit_notification", "notification"),
                                  ("_record_learning", "learning")):
            callback = _sql_delivery_channel(pg, channel)
            def invoke(*args, channel=channel, callback=callback):
                if channel in failed:
                    raise RuntimeError("synthetic delivery outage")
                return callback(*args)
            monkeypatch.setattr(outcome, function, invoke)
        kwargs = dict(org_id=ORG, status="completed", source="api", actor_id="synthetic-actor",
                      run_id=run_id, workflow_id=workflow_id,
                      verified_output=outcome.VerifiedOutputRef(summary="Synthetic internal completion"))
        outcome.finalize_execution_outcome(PgRepositoryClient(pg), **kwargs)
        assert pg.value(f"SELECT parameters->>'outcome_finalized' FROM public.workflow_runs WHERE id='{run_id}'") == "false"
        assert pg.value("SELECT count(*) FROM public.qa_fanout_effects") == "2"
        failed.clear()
        result = outcome.finalize_execution_outcome(PgRepositoryClient(pg), **kwargs)
        assert result.fanout["fanout_checkpoint_persisted"] is True
        assert all(result.fanout[key] for key in outcome._DURABLE_FANOUT_CHANNELS)
        assert pg.value("SELECT count(*) FROM public.qa_fanout_effects") == "3"
        assert pg.value(f"SELECT parameters->'outcome_fanout'->>'complete' FROM public.workflow_runs WHERE id='{run_id}'") == "true"
        assert pg.value(f"SELECT status FROM public.runs WHERE id='{run_id}'") == "completed"
        assert pg.value("SELECT count(*) FROM public.domain_event_outbox") == "1"
        assert outcome.finalize_execution_outcome(PgRepositoryClient(pg), **kwargs).fanout["idempotent_skip"] is True
        assert pg.value("SELECT count(*) FROM public.qa_fanout_effects") == "3"


def test_process_death_after_audit_receipt_resumes_remaining_channels(monkeypatch):
    """Kill the real finalizer process; PostgreSQL and acknowledged effects survive."""
    import os
    import subprocess
    import sys
    from app.services import execution_outcome as outcome
    with canonical_pg_cluster() as pg:
        run_id, workflow_id = _fanout_run(pg)
        script = """
import os
from pathlib import Path
from unittest.mock import patch
from tests.db.pg_harness import Pg
from tests.master_qa.canonical_pg_repository import PgRepositoryClient
from tests.master_qa.test_canonical_repository_persistence_pg import _sql_delivery_channel, ORG
from app.services import execution_outcome as outcome
pg = Pg(Path(os.environ['QA_PG_ROOT']), [])
def die(*args):
    os._exit(91)
with patch.object(outcome, '_write_audit', _sql_delivery_channel(pg, 'audit')), patch.object(outcome, '_emit_notification', die):
    outcome.finalize_execution_outcome(
        PgRepositoryClient(pg), org_id=ORG, status='completed', source='api',
        actor_id='synthetic-actor', run_id=os.environ['QA_RUN'], workflow_id=os.environ['QA_WORKFLOW'],
        verified_output=outcome.VerifiedOutputRef(summary='Synthetic internal completion'))
"""
        child = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=30,
                               env={**os.environ, "QA_PG_ROOT": str(pg.root), "QA_RUN": run_id, "QA_WORKFLOW": workflow_id})
        assert child.returncode == 91, child.stderr
        assert pg.value(f"SELECT parameters->'outcome_fanout'->>'audit_written' FROM public.workflow_runs WHERE id='{run_id}'") == "true"
        assert pg.value(f"SELECT parameters->>'outcome_finalized' FROM public.workflow_runs WHERE id='{run_id}'") == "false"
        for function, channel in (("_write_audit", "audit"), ("_emit_notification", "notification"),
                                  ("_record_learning", "learning")):
            monkeypatch.setattr(outcome, function, _sql_delivery_channel(pg, channel))
        result = outcome.finalize_execution_outcome(
            PgRepositoryClient(pg), org_id=ORG, status="completed", source="api", actor_id="synthetic-actor",
            run_id=run_id, workflow_id=workflow_id,
            verified_output=outcome.VerifiedOutputRef(summary="Synthetic internal completion"))
        assert all(result.fanout[key] for key in outcome._DURABLE_FANOUT_CHANNELS)
        assert pg.value("SELECT count(*) FROM public.qa_fanout_effects") == "3"
        assert pg.value("SELECT count(*) FROM public.domain_event_outbox") == "1"
        assert pg.value(f"SELECT parameters->>'outcome_finalized' FROM public.workflow_runs WHERE id='{run_id}'") == "true"

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


def test_concurrent_parameter_patches_survive_independent_connections():
    """Production repository, simultaneous writers, independent SQL readback."""
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    import time
    import psycopg
    from app.workflows import repository
    with canonical_pg_cluster() as pg:
        run_id, _ = _fanout_run(pg)
        barrier = Barrier(16)
        def write(index):
            barrier.wait(timeout=20)
            return repository.merge_run_parameters(
                PgRepositoryClient(pg), run_id, {f"checkpoint_{index}": {"ack": True}})
        with psycopg.connect(host=str(pg.sock), port=pg.port, dbname="postgres", user="postgres") as blocker:
            blocker.execute("SELECT id FROM public.workflow_runs WHERE id=%s FOR UPDATE", (run_id,))
            with ThreadPoolExecutor(max_workers=16) as pool:
                futures = [pool.submit(write, index) for index in range(16)]
                try:
                    # Hold all writers at the same row. The old read/replace code
                    # reads the same initial document before blocking on UPDATE;
                    # the RPC blocks before reading and preserves every patch.
                    deadline = time.monotonic() + 20
                    while int(pg.value("SELECT count(*) FROM pg_stat_activity WHERE wait_event_type='Lock'")) < 16:
                        assert time.monotonic() < deadline, "writers did not reach database lock"
                        time.sleep(0.01)
                finally:
                    blocker.commit()
                results = [future.result(timeout=20) for future in futures]
        stored = json.loads(pg.value(f"SELECT parameters FROM public.workflow_runs WHERE id='{run_id}'"))
        for index, result in enumerate(results):
            assert result[f"checkpoint_{index}"] == {"ack": True}
            assert stored[f"checkpoint_{index}"] == {"ack": True}
        assert pg.value("SELECT count(*) FROM public.domain_event_outbox") == "0"
        assert pg.value(f"SELECT status FROM public.workflow_runs WHERE id='{run_id}'") == "running"
        assert pg.value(f"SELECT status FROM public.runs WHERE id='{run_id}'") == "running"


@pytest.mark.parametrize("legacy", [None, [], 7, "broken-json", '{"old":true}', {"old": True}])
def test_atomic_parameter_merge_preserves_legacy_normalization(legacy):
    import psycopg
    from psycopg.types.json import Jsonb
    from app.workflows import repository
    with canonical_pg_cluster() as pg:
        run_id, _ = _fanout_run(pg)
        with psycopg.connect(host=str(pg.sock), port=pg.port, dbname="postgres", user="postgres") as conn:
            conn.execute("UPDATE public.workflow_runs SET parameters=%s WHERE id=%s", (Jsonb(legacy), run_id))
        result = repository.merge_run_parameters(PgRepositoryClient(pg), run_id, {"new": 1})
        expected = {"old": True, "new": 1} if legacy in ('{"old":true}', {"old": True}) else {"new": 1}
        assert result == expected
        assert json.loads(pg.value(f"SELECT parameters FROM public.workflow_runs WHERE id='{run_id}'")) == expected


@pytest.mark.parametrize("bad_patch", [None, [], '"string"'])
def test_atomic_parameter_rpc_rejects_nonobjects_without_mutation(bad_patch):
    import psycopg
    from psycopg.types.json import Jsonb
    with canonical_pg_cluster() as pg:
        run_id, _ = _fanout_run(pg)
        before = pg.value(f"SELECT parameters FROM public.workflow_runs WHERE id='{run_id}'")
        with pytest.raises(psycopg.errors.InvalidParameterValue):
            with psycopg.connect(host=str(pg.sock), port=pg.port, dbname="postgres", user="postgres") as conn:
                conn.execute("SELECT public.merge_workflow_run_parameters(%s,%s)", (run_id, Jsonb(bad_patch)))
        assert pg.value(f"SELECT parameters FROM public.workflow_runs WHERE id='{run_id}'") == before


def test_atomic_parameter_rpc_missing_run_role_boundary_and_shallow_merge():
    import psycopg
    from app.workflows import repository
    with canonical_pg_cluster() as pg:
        run_id, _ = _fanout_run(pg)
        with pytest.raises(psycopg.errors.NoDataFound):
            repository.merge_run_parameters(PgRepositoryClient(pg), "99999999-9999-4999-8999-999999999999", {"x": 1})
        for role in ("anon", "authenticated"):
            assert pg.value(f"SELECT has_function_privilege('{role}', 'public.merge_workflow_run_parameters(uuid,jsonb)', 'EXECUTE')") == "f"
        assert pg.value("SELECT has_function_privilege('service_role', 'public.merge_workflow_run_parameters(uuid,jsonb)', 'EXECUTE')") == "t"
        assert pg.value("SELECT prosecdef FROM pg_proc WHERE oid='public.merge_workflow_run_parameters(uuid,jsonb)'::regprocedure") == "f"
        client = PgRepositoryClient(pg)
        repository.merge_run_parameters(client, run_id, {"nested": {"old": True}, "unrelated": 1})
        assert repository.merge_run_parameters(client, run_id, {"nested": {"new": True}}) == {"nested": {"new": True}, "unrelated": 1}


def _atomic_outcome(client, run_id, status="completed", org_id=ORG, **overrides):
    from app.workflows import repository
    kwargs = dict(org_id=org_id, status=status,
        parameters={"verified_output": {"summary": status}},
        completed_at="2026-11-16T00:00:00Z", error_message=None,
        approval_status=None, completion_proven=False, actor_id="synthetic-actor")
    kwargs.update(overrides)
    return repository.persist_run_outcome(client, run_id, **kwargs)


def test_concurrent_terminal_writers_preserve_one_status_proof_and_outbox():
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    with canonical_pg_cluster() as pg:
        run_id, _ = _fanout_run(pg)
        barrier = Barrier(2)
        def write(status):
            barrier.wait(timeout=10)
            return _atomic_outcome(PgRepositoryClient(pg), run_id, status)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(write, ("completed", "cancelled")))
        assert sum(result["accepted"] for result in results) == 1
        winner = next(result["status"] for result in results if result["accepted"])
        assert all(result["status"] == winner for result in results)
        assert pg.value(f"SELECT status FROM public.workflow_runs WHERE id='{run_id}'") == winner
        assert pg.value(f"SELECT parameters->'verified_output'->>'summary' FROM public.workflow_runs WHERE id='{run_id}'") == winner
        assert pg.value("SELECT count(*) FROM public.domain_event_outbox") == "1"


def test_terminal_constraint_failure_rolls_back_proof_and_outbox():
    import psycopg
    with canonical_pg_cluster() as pg:
        run_id, _ = _fanout_run(pg)
        # The existing fixture rejects completed before verified_output exists.
        with pytest.raises(psycopg.errors.RaiseException):
            _atomic_outcome(PgRepositoryClient(pg), run_id, parameters={"uncommitted": True})
        assert pg.value(f"SELECT status FROM public.workflow_runs WHERE id='{run_id}'") == "running"
        assert pg.value(f"SELECT parameters FROM public.workflow_runs WHERE id='{run_id}'") == "{}"
        assert pg.value("SELECT count(*) FROM public.domain_event_outbox") == "0"


def test_same_terminal_retry_preserves_first_proof_actor_and_timestamp():
    with canonical_pg_cluster() as pg:
        run_id, _ = _fanout_run(pg)
        first = _atomic_outcome(PgRepositoryClient(pg), run_id)
        second = _atomic_outcome(PgRepositoryClient(pg), run_id,
            parameters={"verified_output": {"summary": "late"}}, actor_id="different",
            completed_at="2026-11-17T00:00:00Z")
        assert first["parameters"] == second["parameters"]
        assert second["parameters"]["outcome_actor_id"] == "synthetic-actor"
        assert pg.value(f"SELECT completed_at::date FROM public.workflow_runs WHERE id='{run_id}'") == "2026-11-16"
        assert pg.value("SELECT count(*) FROM public.domain_event_outbox") == "1"


def test_uncertain_promotion_requires_proof_and_resets_status_bound_receipts():
    from app.workflows import repository
    with canonical_pg_cluster() as pg:
        run_id, _ = _fanout_run(pg)
        client = PgRepositoryClient(pg)
        _atomic_outcome(client, run_id, "verification_inconclusive")
        repository.checkpoint_outcome_fanout(client, run_id, org_id=ORG,
            status="verification_inconclusive", receipt={"run_persisted": True, "audit_written": True},
            finalize=False, actor_required=True)
        assert _atomic_outcome(client, run_id)["accepted"] is False
        assert _atomic_outcome(client, run_id, completion_proven=True)["accepted"] is True
        assert pg.value(f"SELECT parameters->'outcome_fanout'->>'audit_written' FROM public.workflow_runs WHERE id='{run_id}'") == ""
        assert pg.value(f"SELECT parameters->>'outcome_finalized' FROM public.workflow_runs WHERE id='{run_id}'") == "false"


def test_concurrent_receipts_or_acknowledgements_without_completion_downgrade():
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from app.workflows import repository
    keys = ("run_persisted", "audit_written", "notification_emitted", "learning_recorded")
    with canonical_pg_cluster() as pg:
        run_id, _ = _fanout_run(pg)
        _atomic_outcome(PgRepositoryClient(pg), run_id)
        barrier = Barrier(8)
        def checkpoint(index):
            barrier.wait(timeout=10)
            return repository.checkpoint_outcome_fanout(PgRepositoryClient(pg), run_id,
                org_id=ORG, status="completed", receipt={key: key == keys[index % 4] for key in keys},
                finalize=index == 0, actor_required=True)
        with ThreadPoolExecutor(max_workers=8) as pool:
            assert all(result["accepted"] for result in pool.map(checkpoint, range(8)))
        result = repository.checkpoint_outcome_fanout(PgRepositoryClient(pg), run_id,
            org_id=ORG, status="completed", receipt={key: False for key in keys},
            finalize=False, actor_required=False)
        assert all(result["receipt"][key] for key in (*keys, "complete"))
        assert pg.value(f"SELECT parameters->>'outcome_finalized' FROM public.workflow_runs WHERE id='{run_id}'") == "true"
        assert pg.value("SELECT count(*) FROM public.domain_event_outbox") == "1"


def test_actorless_retry_cannot_weaken_required_channels_or_change_status():
    from app.workflows import repository
    with canonical_pg_cluster() as pg:
        run_id, _ = _fanout_run(pg)
        client = PgRepositoryClient(pg)
        _atomic_outcome(client, run_id)
        result = repository.checkpoint_outcome_fanout(client, run_id, org_id=ORG,
            status="completed", receipt={"run_persisted": True, "learning_recorded": True},
            finalize=True, actor_required=False)
        assert result["receipt"]["complete"] is False
        before = pg.value(f"SELECT parameters FROM public.workflow_runs WHERE id='{run_id}'")
        assert not repository.checkpoint_outcome_fanout(client, run_id, org_id=ORG,
            status="failed", receipt={"audit_written": True}, finalize=True, actor_required=False)["accepted"]
        assert pg.value(f"SELECT parameters FROM public.workflow_runs WHERE id='{run_id}'") == before


@pytest.mark.parametrize("boundary", ["persist", "checkpoint"])
def test_outcome_transactions_reject_cross_tenant_mutations_and_public_roles(boundary):
    import psycopg
    from app.workflows import repository
    with canonical_pg_cluster() as pg:
        run_id, _ = _fanout_run(pg)
        foreign = "33333333-3333-4333-8333-333333333333"
        with pytest.raises(psycopg.errors.NoDataFound):
            if boundary == "persist":
                _atomic_outcome(PgRepositoryClient(pg), run_id, org_id=foreign)
            else:
                repository.checkpoint_outcome_fanout(PgRepositoryClient(pg), run_id,
                    org_id=foreign, status="running", receipt={}, finalize=True, actor_required=False)
        function = ("public.persist_workflow_run_outcome(uuid,uuid,text,jsonb,timestamptz,text,text,boolean,text)"
            if boundary == "persist" else "public.checkpoint_workflow_run_outcome(uuid,uuid,text,jsonb,boolean,boolean)")
        for role in ("anon", "authenticated"):
            assert pg.value(f"SELECT has_function_privilege('{role}','{function}','EXECUTE')") == "f"
        assert pg.value(f"SELECT has_function_privilege('service_role','{function}','EXECUTE')") == "t"
        assert pg.value(f"SELECT prosecdef FROM pg_proc WHERE oid='{function}'::regprocedure") == "f"
        assert pg.value(f"SELECT status FROM public.workflow_runs WHERE id='{run_id}'") == "running"


def test_actual_finalizer_rejects_cancellation_between_preread_and_atomic_write(monkeypatch):
    from app.services import execution_outcome as outcome
    with canonical_pg_cluster() as pg:
        run_id, workflow_id = _fanout_run(pg)
        persist = outcome._persist_run
        def cancel_then_persist(client, event, status, timestamp):
            _atomic_outcome(client, run_id, "cancelled")
            return persist(client, event, status, timestamp)
        monkeypatch.setattr(outcome, "_persist_run", cancel_then_persist)
        for function in ("_write_audit", "_emit_notification", "_record_learning"):
            monkeypatch.setattr(outcome, function, _sql_delivery_channel(pg, function))
        result = outcome.finalize_execution_outcome(PgRepositoryClient(pg), org_id=ORG,
            status="completed", source="api", actor_id="synthetic-actor", run_id=run_id,
            workflow_id=workflow_id, verified_output=outcome.VerifiedOutputRef(summary="late success"))
        assert result.status == "cancelled"
        assert result.fanout["terminal_conflict"] is True
        assert pg.value("SELECT count(*) FROM public.qa_fanout_effects") == "0"
        assert pg.value(f"SELECT parameters->'verified_output'->>'summary' FROM public.workflow_runs WHERE id='{run_id}'") == "cancelled"
        assert pg.value("SELECT count(*) FROM public.domain_event_outbox") == "1"


def test_actual_finalizer_database_failure_suppresses_all_delivery(monkeypatch):
    from app.services import execution_outcome as outcome
    with canonical_pg_cluster() as pg:
        run_id, workflow_id = _fanout_run(pg)
        pg.psql("""
CREATE FUNCTION public.qa_fail_terminal_commit() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'synthetic terminal write outage'; END $$;
CREATE TRIGGER qa_fail_terminal BEFORE UPDATE OF status ON public.workflow_runs
FOR EACH ROW EXECUTE FUNCTION public.qa_fail_terminal_commit();
""")
        for function in ("_write_audit", "_emit_notification", "_record_learning"):
            monkeypatch.setattr(outcome, function, _sql_delivery_channel(pg, function))
        result = outcome.finalize_execution_outcome(PgRepositoryClient(pg), org_id=ORG,
            status="completed", source="api", actor_id="synthetic-actor", run_id=run_id,
            workflow_id=workflow_id, verified_output=outcome.VerifiedOutputRef(summary="uncommitted"))
        assert result.status == "verification_inconclusive"
        assert result.fanout["persistence_failed"] is True
        assert pg.value("SELECT count(*) FROM public.qa_fanout_effects") == "0"
        assert pg.value(f"SELECT status FROM public.workflow_runs WHERE id='{run_id}'") == "running"
        assert pg.value(f"SELECT parameters FROM public.workflow_runs WHERE id='{run_id}'") == "{}"
        assert pg.value("SELECT count(*) FROM public.domain_event_outbox") == "0"


def _core_effect_tables(pg):
    # Actual durable channel writers, using their existing production columns.
    # No external provider, preference service or SIEM delivery is inferred.
    pg.psql("""
CREATE TABLE public.audit_logs(id uuid PRIMARY KEY, org_id uuid, action text,
 resource_type text, resource_id uuid, actor_id uuid, details jsonb);
CREATE TABLE public.audit_events(id uuid PRIMARY KEY, org_id uuid, action text,
 resource_type text, resource_id uuid, actor_id uuid, metadata jsonb);
CREATE TABLE public.notifications(id uuid PRIMARY KEY, org_id uuid, user_id uuid,
 type text, title text, body text, url text, entity_type text, entity_id uuid,
 is_read boolean, is_archived boolean);
CREATE TABLE public.intelligence_outcome_events(id uuid PRIMARY KEY, org_id uuid,
 outcome_event text, entity_type text, entity_id text, workflow_id uuid,
 workflow_run_id uuid, metadata jsonb, measured_at timestamptz,
 measurement_status text, created_at timestamptz);
""")


def _disable_optional_delivery(monkeypatch):
    from app.workflows import audit
    from app.services import notification_preference_service as preferences
    monkeypatch.setattr(audit, "_get_org_pii_mode", lambda *_: "standard")
    monkeypatch.setattr(audit, "_schedule_siem_dispatch", lambda *_: None)
    monkeypatch.setattr(preferences, "channel_enabled", lambda *_: False)


def _real_core_finalize(pg, run_id, workflow_id):
    from app.services import execution_outcome as outcome
    return outcome.finalize_execution_outcome(PgRepositoryClient(pg), org_id=ORG,
        status="completed", source="api", actor_id="44444444-4444-4444-8444-444444444444",
        run_id=run_id, workflow_id=workflow_id, channel_hints={"bell": False, "email": False},
        verified_output=outcome.VerifiedOutputRef(summary="Synthetic internal outcome"))


@pytest.mark.parametrize("channel", ["audit_written", "notification_emitted", "learning_recorded"])
def test_real_channel_commit_process_death_before_receipt_does_not_duplicate(monkeypatch, channel):
    import os
    import subprocess
    import sys
    _disable_optional_delivery(monkeypatch)
    with canonical_pg_cluster() as pg:
        run_id, workflow_id = _fanout_run(pg)
        _core_effect_tables(pg)
        script = """
import os
from pathlib import Path
from unittest.mock import patch
from tests.db.pg_harness import Pg
from tests.master_qa.test_canonical_repository_persistence_pg import _real_core_finalize
from app.services import execution_outcome as outcome
pg=Pg(Path(os.environ['QA_PG_ROOT']), [])
checkpoint=outcome._checkpoint_fanout
def die_after_commit(client, event, fanout, **kwargs):
    if fanout.get(os.environ['QA_CHANNEL']):
        os._exit(92)
    return checkpoint(client, event, fanout, **kwargs)
with patch('app.workflows.audit._get_org_pii_mode', return_value='standard'), patch('app.workflows.audit._schedule_siem_dispatch'), patch('app.services.notification_preference_service.channel_enabled', return_value=False), patch.object(outcome, '_checkpoint_fanout', die_after_commit):
    _real_core_finalize(pg, os.environ['QA_RUN'], os.environ['QA_WORKFLOW'])
"""
        child = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=30,
            env={**os.environ, "QA_PG_ROOT": str(pg.root), "QA_RUN": run_id,
                 "QA_WORKFLOW": workflow_id, "QA_CHANNEL": channel})
        assert child.returncode == 92, child.stderr
        assert pg.value(f"SELECT parameters->'outcome_fanout'->>'{channel}' FROM public.workflow_runs WHERE id='{run_id}'") != "true"
        result = _real_core_finalize(pg, run_id, workflow_id)
        assert all(result.fanout[key] for key in ("run_persisted", "audit_written", "notification_emitted", "learning_recorded"))
        for table in ("audit_logs", "audit_events", "notifications", "intelligence_outcome_events"):
            assert pg.value(f"SELECT count(*) FROM public.{table}") == "1"
        assert pg.value(f"SELECT parameters->>'outcome_finalized' FROM public.workflow_runs WHERE id='{run_id}'") == "true"


def test_concurrent_actual_finalizers_create_one_core_record_per_channel(monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from app.services import execution_outcome as outcome
    _disable_optional_delivery(monkeypatch)
    with canonical_pg_cluster() as pg:
        run_id, workflow_id = _fanout_run(pg)
        _core_effect_tables(pg)
        barrier = Barrier(4)
        persist = outcome._persist_run
        def synchronize(*args):
            barrier.wait(timeout=20)
            return persist(*args)
        monkeypatch.setattr(outcome, "_persist_run", synchronize)
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: _real_core_finalize(pg, run_id, workflow_id), range(4)))
        assert all(result.status == "completed" for result in results)
        assert all(result.fanout["run_persisted"] for result in results)
        for table in ("audit_logs", "audit_events", "notifications", "intelligence_outcome_events"):
            assert pg.value(f"SELECT count(*) FROM public.{table}") == "1"
        assert pg.value(f"SELECT parameters->>'outcome_finalized' FROM public.workflow_runs WHERE id='{run_id}'") == "true"
        assert pg.value("SELECT count(*) FROM public.domain_event_outbox") == "1"


@pytest.mark.parametrize("source", ["pending", "queued", "running", "verifying", "completed", "success", "failed", "error", "verification_inconclusive", "cancelled", "canceled", "pending_approval", "awaiting_approval", "needs_approval", "partial_success", "flagged_for_review", "paused"])
def test_atomic_projection_status_contract_parity(source):
    from app.workflows.run_status_contract import contract_run_status_v2
    from app.workflows.schema_sync import mirror_legacy_run_to_contract
    with canonical_pg_cluster() as pg:
        run_id, _ = _fanout_run(pg)
        # This test exercises legacy alias translation, not source execution
        # admission. Only this disposable fixture's narrower status check is
        # removed; production constraints and the other acceptance cases stay.
        pg.psql("ALTER TABLE public.workflow_runs DROP CONSTRAINT workflow_runs_status_check")
        # Supply proof to the fixture's existing terminal-output guard.
        pg.psql(f"UPDATE public.workflow_runs SET parameters='{{\"verified_output\":{{}}}}',status='{source}' WHERE id='{run_id}'")
        assert mirror_legacy_run_to_contract(PgRepositoryClient(pg), run_id)
        assert pg.value(f"SELECT status FROM public.runs WHERE id='{run_id}'") == contract_run_status_v2(source)
        assert pg.value(f"SELECT metadata->>'execution_lifecycle' FROM public.runs WHERE id='{run_id}'") == source


def test_projection_refresh_serializes_late_caller_after_new_terminal_commit():
    import psycopg
    from concurrent.futures import ThreadPoolExecutor
    import time
    from app.workflows.schema_sync import mirror_legacy_run_to_contract
    with canonical_pg_cluster() as pg:
        run_id, _ = _fanout_run(pg)
        # Hold an uncommitted new source state. The late refresh has no stale
        # snapshot payload; it must block on this lock, then read the new truth.
        with psycopg.connect(host=str(pg.sock), port=pg.port, dbname="postgres", user="postgres") as owner:
            owner.execute("UPDATE public.workflow_runs SET status='cancelled',error_message='cancel won' WHERE id=%s", (run_id,))
            with ThreadPoolExecutor(max_workers=1) as pool:
                pending = pool.submit(mirror_legacy_run_to_contract, PgRepositoryClient(pg), run_id)
                try:
                    deadline = time.monotonic()+15
                    while int(pg.value("SELECT count(*) FROM pg_stat_activity WHERE wait_event_type='Lock'")) < 1:
                        assert time.monotonic() < deadline
                        time.sleep(0.01)
                    assert not pending.done()
                finally:
                    owner.commit()
                assert pending.result(timeout=15)
        assert pg.value(f"SELECT status FROM public.runs WHERE id='{run_id}'") == "cancelled"
        assert pg.value(f"SELECT error_message FROM public.runs WHERE id='{run_id}'") == "cancel won"
        assert pg.value("SELECT count(*) FROM public.domain_event_outbox") == "1"


def test_atomic_projection_uses_real_text_array_logs_and_clears_removed_snapshots():
    from app.workflows import repository
    from app.workflows.schema_sync import mirror_legacy_run_to_contract
    with canonical_pg_cluster() as pg:
        run_id, _ = _fanout_run(pg)
        client = PgRepositoryClient(pg)
        step = repository.create_step(client, run_id, ORG, "step-1", 0, "First step", "invoke_tool")
        pg.psql(f"UPDATE public.runs SET metadata='[]'::jsonb WHERE id='{run_id}'")
        pg.psql(f"UPDATE public.run_steps SET metadata='\"legacy\"'::jsonb WHERE id='{step['id']}'")
        pg.psql(f"UPDATE public.workflow_steps SET status='completed',logs='line one',input_snapshot='{{\"input\":1}}',output_snapshot='{{\"receipt\":true}}',started_at='2026-11-16T00:00:00Z',completed_at='2026-11-16T00:00:00.0019Z' WHERE id='{step['id']}'")
        assert mirror_legacy_run_to_contract(client, run_id)
        assert pg.value(f"SELECT jsonb_typeof(metadata) FROM public.runs WHERE id='{run_id}'") == "object"
        assert pg.value(f"SELECT jsonb_typeof(metadata) FROM public.run_steps WHERE id='{step['id']}'") == "object"
        assert pg.value(f"SELECT pg_typeof(logs) FROM public.run_steps WHERE id='{step['id']}'") == "text[]"
        assert pg.value(f"SELECT logs[1] FROM public.run_steps WHERE id='{step['id']}'") == "line one"
        assert pg.value(f"SELECT duration_ms FROM public.run_steps WHERE id='{step['id']}'") == "1"
        pg.psql(f"UPDATE public.run_steps SET metadata=metadata||'{{\"consumer_note\":\"keep\"}}' WHERE id='{step['id']}'")
        pg.psql(f"UPDATE public.workflow_steps SET logs='',input_snapshot=NULL,output_snapshot=NULL WHERE id='{step['id']}'")
        assert mirror_legacy_run_to_contract(client, run_id)
        assert pg.value(f"SELECT cardinality(logs) FROM public.run_steps WHERE id='{step['id']}'") == "0"
        assert pg.value(f"SELECT metadata ? 'output_snapshot' OR metadata ? 'input_snapshot' FROM public.run_steps WHERE id='{step['id']}'") == "f"
        assert pg.value(f"SELECT metadata->>'consumer_note' FROM public.run_steps WHERE id='{step['id']}'") == "keep"


def test_terminal_projection_failure_rolls_back_source_proof_and_outbox():
    import psycopg
    with canonical_pg_cluster() as pg:
        run_id, _ = _fanout_run(pg)
        pg.psql("""
CREATE FUNCTION public.qa_reject_projection() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'projection unavailable'; END $$;
CREATE TRIGGER qa_reject_projection BEFORE UPDATE ON public.runs
FOR EACH ROW EXECUTE FUNCTION public.qa_reject_projection();
""")
        with pytest.raises(psycopg.errors.RaiseException, match="projection unavailable"):
            _atomic_outcome(PgRepositoryClient(pg), run_id)
        assert pg.value(f"SELECT status FROM public.workflow_runs WHERE id='{run_id}'") == "running"
        assert pg.value(f"SELECT parameters FROM public.workflow_runs WHERE id='{run_id}'") == "{}"
        assert pg.value(f"SELECT status FROM public.runs WHERE id='{run_id}'") == "running"
        assert pg.value("SELECT count(*) FROM public.domain_event_outbox") == "0"


@pytest.mark.parametrize("conflict", ["run_tenant", "step_tenant", "step_parent"])
def test_projection_identity_conflict_rolls_back_entire_refresh(conflict):
    import psycopg
    from app.workflows import repository
    with canonical_pg_cluster() as pg:
        run_id, _ = _fanout_run(pg)
        step = repository.create_step(PgRepositoryClient(pg), run_id, ORG, "step-1", 0, "First", "noop")
        foreign = "99999999-9999-4999-8999-999999999999"
        if conflict == "run_tenant":
            pg.psql(f"UPDATE public.runs SET org_id='{foreign}' WHERE id='{run_id}'")
        elif conflict == "step_tenant":
            pg.psql(f"UPDATE public.run_steps SET org_id='{foreign}' WHERE id='{step['id']}'")
        else:
            pg.psql(f"UPDATE public.run_steps SET run_id='{foreign}' WHERE id='{step['id']}'")
        before = pg.value(f"SELECT row_to_json(r) FROM public.runs r WHERE id='{run_id}'")
        with pytest.raises(psycopg.errors.CheckViolation):
            PgRepositoryClient(pg).rpc("refresh_workflow_run_projection", {"p_run_id": run_id}).execute()
        assert pg.value(f"SELECT row_to_json(r) FROM public.runs r WHERE id='{run_id}'") == before


def test_projection_missing_run_unknown_status_and_privileges_fail_closed():
    import psycopg
    with canonical_pg_cluster() as pg:
        run_id, _ = _fanout_run(pg)
        client = PgRepositoryClient(pg)
        with pytest.raises(psycopg.errors.NoDataFound):
            client.rpc("refresh_workflow_run_projection", {"p_run_id": "99999999-9999-4999-8999-999999999999"}).execute()
        # Reach the projection's own unknown-status guard independently of the
        # fixture's source-status constraint; no production constraint changes.
        pg.psql("ALTER TABLE public.workflow_runs DROP CONSTRAINT workflow_runs_status_check")
        pg.psql(f"UPDATE public.workflow_runs SET status='unknown_state' WHERE id='{run_id}'")
        with pytest.raises(psycopg.errors.InvalidParameterValue):
            client.rpc("refresh_workflow_run_projection", {"p_run_id": run_id}).execute()
        assert pg.value(f"SELECT status FROM public.runs WHERE id='{run_id}'") == "running"
        for role in ('anon','authenticated'):
            assert pg.value(f"SELECT has_function_privilege('{role}','public.refresh_workflow_run_projection(uuid)','EXECUTE')") == 'f'
        assert pg.value("SELECT has_function_privilege('service_role','public.refresh_workflow_run_projection(uuid)','EXECUTE')") == 't'
        assert pg.value("SELECT prosecdef FROM pg_proc WHERE oid='public.refresh_workflow_run_projection(uuid)'::regprocedure") == 'f'


def test_projection_supports_production_source_without_started_at_column():
    from app.workflows.schema_sync import mirror_legacy_run_to_contract
    with canonical_pg_cluster() as pg:
        run_id, _ = _fanout_run(pg)
        pg.psql("ALTER TABLE public.workflow_runs DROP COLUMN started_at")
        assert mirror_legacy_run_to_contract(PgRepositoryClient(pg), run_id)
        assert pg.value(f"SELECT started_at=wr.created_at FROM public.runs r JOIN public.workflow_runs wr USING(id) WHERE r.id='{run_id}'") == 't'
