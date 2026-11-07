"""Joined P27 proof: real stale SQL takeover after provider commit + process death.

The original process exits after its simulated external provider commits, before
updating the workflow step. A worker sweep then claims/parks the orphan,
reconciles against an independent SQL provider stand-in and finishes without
invoking the connector again. Only terminal notification fanout is adapted.
"""
from __future__ import annotations

import os
import subprocess
import sys
from types import SimpleNamespace

import pytest

from tests.db.pg_harness import requires_pg
from tests.db.test_domain_event_outbox_pg import ORG
from tests.master_qa.canonical_pg_repository import PgRepositoryClient, canonical_pg_cluster

pytestmark = requires_pg


def test_auto_orphan_claim_reconciles_prior_commit_without_duplicate_write(monkeypatch):
    from app.services import workflow_orphan_reconciler as service
    from app.services.outcome_reconciliation import ReconciliationResult
    from app.workflows import repository
    from app.workflows import execution_engine_runtime as runtime

    workflow_id = "22222222-2222-4222-8222-222222222222"
    nodes = [
        {"id": "trigger", "node_type": "source", "title": "Trigger"},
        {"id": "write", "node_type": "connector", "title": "CRM create",
         "config": {"action": "hubspot.contacts.create",
                    "params": {"email": "p27-recovery@example.invalid"}}},
    ]
    edges = [{"from_node_id": "trigger", "to_node_id": "write"}]
    with canonical_pg_cluster() as pg:
        client = PgRepositoryClient(pg)
        pg.psql(f"INSERT INTO public.workflows (id,org_id,name) "
                f"VALUES ('{workflow_id}','{ORG}','Orphan crash/reconcile fixture')")
        run = repository.create_execute_run(
            client, ORG, workflow_id, "synthetic-owner",
            {"graph": {"nodes": nodes, "edges": edges}}, {},
            "auto-orphan-crash", "running", "approved", 0, [],
            environment_name="synthetic")
        run_id = run["id"]
        step = repository.create_step(
            client, run_id, ORG, "write", 1, "CRM create", "invoke_tool")
        repository.set_step_running(client, step["id"], "2026-01-01T00:00:00+00:00")
        repository.update_step(
            client, step["id"], "running",
            input_snapshot={"config": nodes[1]["config"]})
        checkpoint = {
            "paused_at_node": "write", "batch_index": 1, "step_index": 1,
            "node_outputs": {"trigger": {"passthrough": True}},
            "skipped_nodes": [], "approval_context": {},
            "nodes": nodes, "edges": edges,
            "pause_reason": "executor_in_flight",
        }
        repository.merge_run_parameters(client, run_id, {
            "_graph_execution": checkpoint,
        })
        pg.psql("CREATE TABLE public.qa_p27_external_effect ("
                "action_key text PRIMARY KEY, record_id text NOT NULL)")
        script = """
import os, psycopg
with psycopg.connect(host=os.environ["PG_SOCK"], port=os.environ["PG_PORT"],
                     user="postgres", dbname="postgres") as connection:
    with connection.cursor() as cursor:
        cursor.execute("INSERT INTO public.qa_p27_external_effect "
                       "(action_key,record_id) VALUES (%s,%s)",
                       (os.environ["ACTION_KEY"],"fixture-contact-1"))
os._exit(91)
"""
        child = subprocess.run(
            [sys.executable, "-c", script], capture_output=True, text=True,
            env={**os.environ, "PG_SOCK": str(pg.sock), "PG_PORT": pg.port,
                 "ACTION_KEY": f"{run_id}:write"}, timeout=20)
        assert child.returncode == 91, child.stderr
        assert pg.value(f"SELECT status FROM public.workflow_runs WHERE id='{run_id}'") == "running"
        assert pg.value(f"SELECT status FROM public.workflow_steps WHERE run_id='{run_id}'") == "running"

        reads = []
        def provider_reconcile(*, ctx, invoke_action, args):
            reads.append(invoke_action)
            assert invoke_action == "hubspot.contacts.create"
            assert args["email"] == "p27-recovery@example.invalid"
            record = pg.value("SELECT record_id FROM public.qa_p27_external_effect "
                              f"WHERE action_key='{run_id}:write'")
            assert record == "fixture-contact-1"
            return ReconciliationResult(
                "applied", "provider_authoritative_readback", record,
                "hubspot.contacts.get",
                {"verified": True, "method": "provider_authoritative_get",
                 "resource_id": record})

        monkeypatch.setattr(
            "app.services.outcome_reconciliation.reconcile_uncertain_write",
            provider_reconcile)
        monkeypatch.setattr(
            "app.services.tool_service.tool_context_from_step",
            lambda ctx: SimpleNamespace(org_id=ctx.org_id))
        monkeypatch.setattr(service, "get_supabase_client",
                            lambda settings: PgRepositoryClient(pg))
        monkeypatch.setattr(
            runtime, "_execute_graph_node",
            lambda *_: (_ for _ in ()).throw(
                AssertionError("orphan recovery replayed an applied connector write")))
        def terminal(ctx, *, final_status, errors, run_error_message, rate_limited):
            repository.update_run(ctx.client, ctx.run_id, final_status)
            return final_status, [], errors, rate_limited
        monkeypatch.setattr(runtime, "_finalize_run", terminal)
        result = service.recover_one_stale_graph_run(SimpleNamespace(
            workflow_orphan_stale_seconds=300,
            workflow_orphan_lease_seconds=600))
        assert result == {
            "state": "resumed", "run_id": run_id,
            "status": "completed", "errors": 0,
        }
        assert reads == ["hubspot.contacts.create"]
        assert pg.value("SELECT count(*) FROM public.qa_p27_external_effect") == "1"
        assert pg.value(f"SELECT status FROM public.workflow_steps WHERE run_id='{run_id}'") == "completed"
        assert pg.value(f"SELECT status FROM public.workflow_runs WHERE id='{run_id}'") == "completed"
        assert pg.value(f"SELECT count(*) FROM public.domain_event_outbox "
                        f"WHERE aggregate_id='{run_id}'") == "1"
        assert pg.value("SELECT count(*) FROM public.workflow_recovery_leases") == "0"
