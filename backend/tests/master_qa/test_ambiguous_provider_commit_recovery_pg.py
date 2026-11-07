"""P27 ambiguous provider commit across a genuine subprocess crash.

The provider-side effect commits to a separate PostgreSQL table, then the child
process exits before a workflow receipt/step outcome or graph node output is
saved. Recovery invokes the production graph resume and reconciliation path.
The isolated provider readback is SQL-backed, not a live vendor credential.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from types import SimpleNamespace

import pytest

from tests.db.pg_harness import requires_pg
from tests.db.test_domain_event_outbox_pg import ORG
from tests.master_qa.canonical_pg_repository import PgRepositoryClient, canonical_pg_cluster

pytestmark = requires_pg


@pytest.mark.parametrize("provider_result", ["applied", "not_applied", "unknown"])
def test_ambiguous_commit_blocks_or_recovers_after_authoritative_readback(
    monkeypatch, provider_result
):
    from app.workflows import repository
    from app.workflows import execution_engine_runtime as runtime
    from app.services.outcome_reconciliation import ReconciliationResult

    workflow_id = "22222222-2222-4222-8222-222222222222"
    nodes = [
        {"id": "trigger", "node_type": "source", "title": "Start"},
        {"id": "write", "node_type": "connector", "title": "Create CRM fixture",
         "config": {"action": "hubspot.contacts.create",
                    "params": {"email": "qa-p27@example.invalid"}}},
        {"id": "continue", "node_type": "agent", "title": "Continue",
         "metadata": {"agent_id": "qa", "task": "Continue"}},
    ]
    edges = [
        {"from_node_id": "trigger", "to_node_id": "write"},
        {"from_node_id": "write", "to_node_id": "continue"},
    ]
    definition = {"graph": {"nodes": nodes, "edges": edges}}
    with canonical_pg_cluster() as pg:
        client = PgRepositoryClient(pg)
        pg.psql(f"INSERT INTO public.workflows (id,org_id,name) "
                f"VALUES ('{workflow_id}','{ORG}','Ambiguous commit fixture')")
        run = repository.create_execute_run(
            client=client, org_id=ORG, workflow_id=workflow_id,
            triggered_by="synthetic-owner", definition_snapshot=definition,
            parameters={}, run_hash="ambiguous-p27",
            status="running", approval_status="approved",
            required_approvals=0, approver_roles=[], environment_name="synthetic")
        run_id = run["id"]
        step = repository.create_step(
            client=client, run_id=run_id, org_id=ORG, step_id="write",
            step_index=1, step_name="Create CRM fixture", step_type="invoke_tool")
        repository.set_step_running(client, step["id"], "2026-11-07T12:00:00+00:00")
        repository.update_step(client, step["id"], "running",
                               input_snapshot={"config": nodes[1]["config"]})

        checkpoint = {
            "paused_at_node": "write", "batch_index": 1, "step_index": 1,
            "node_outputs": {"trigger": {"passthrough": True}},
            "skipped_nodes": [], "approval_context": {},
            "nodes": nodes, "edges": edges, "pause_reason": "executor_process_lost",
        }
        # Save dispatch checkpoint BEFORE performing the action. The child
        # process must never write the result or update the workflow row.
        repository.merge_run_parameters(client, run_id, {"_graph_execution": checkpoint})
        pg.psql("CREATE TABLE public.qa_p27_authoritative_provider ("
                "action_key text PRIMARY KEY, resource_id text NOT NULL)")
        script = """
import os, psycopg
with psycopg.connect(host=os.environ["P27_SOCK"], port=os.environ["P27_PORT"],
                     user="postgres", dbname="postgres") as conn:
    with conn.cursor() as cur:
        if os.environ["P27_APPLY"] == "yes":
            cur.execute(
                "INSERT INTO public.qa_p27_authoritative_provider "
                "(action_key,resource_id) VALUES (%s,%s)",
                (os.environ["P27_ACTION"], "provider-record-p27"))
os._exit(88)
"""
        action_key = f"{run_id}:write"
        child = subprocess.run(
            [sys.executable, "-c", script], capture_output=True, text=True,
            env={**os.environ, "P27_SOCK": str(pg.sock), "P27_PORT": pg.port,
                 "P27_APPLY": "yes" if provider_result == "applied" else "no",
                 "P27_ACTION": action_key}, timeout=20)
        assert child.returncode == 88, child.stderr
        assert repository.get_run_with_steps(client, ORG, run_id, "synthetic")[
            "steps"][0]["status"] == "running"
        assert "write" not in repository.get_run_with_steps(
            client, ORG, run_id, "synthetic")["parameters"]["_graph_execution"]["node_outputs"]
        # A separate controller recognizes an abandoned worker and parks the
        # workflow without modifying its in-flight step or provider receipt.
        repository.update_run(client, run_id, "paused")

        readbacks = []
        def independent_provider_readback(*, ctx, invoke_action, args):
            readbacks.append((invoke_action, args))
            assert invoke_action == "hubspot.contacts.create"
            if provider_result == "unknown":
                return ReconciliationResult("unknown", "provider_unavailable")
            existing = pg.value(
                "SELECT resource_id FROM public.qa_p27_authoritative_provider "
                f"WHERE action_key='{action_key}'")
            if existing:
                return ReconciliationResult(
                    "applied", "readback_confirmed", existing,
                    "hubspot.contacts.search",
                    {"verified": True, "method": "provider_authoritative_get",
                     "resource_id": existing})
            return ReconciliationResult(
                "not_applied", "provider_filtered_absence", None,
                "hubspot.contacts.search",
                {"verified": True, "method": "provider_authoritative_search",
                 "complete_result_set": True})
        monkeypatch.setattr(
            "app.services.outcome_reconciliation.reconcile_uncertain_write",
            independent_provider_readback)
        monkeypatch.setattr(
            "app.services.tool_service.tool_context_from_step",
            lambda context: SimpleNamespace(org_id=context.org_id))
        # Production graph resumption controls order; synthetic downstream
        # handler stands in for the next external agent.
        invoked = []
        def run_node(ctx, node_id, index):
            invoked.append(node_id)
            if node_id == "write":
                assert provider_result == "not_applied"
                assert pg.value(
                    "SELECT count(*) FROM public.qa_p27_authoritative_provider") == "0"
                pg.psql(
                    "INSERT INTO public.qa_p27_authoritative_provider "
                    f"(action_key,resource_id) VALUES ('{action_key}','replayed-once')")
            with ctx.lock:
                ctx.node_outputs[node_id] = {"ok": True}
            return runtime._NodeRunResult(node_id, index + 1)
        monkeypatch.setattr(runtime, "_execute_graph_node", run_node)
        monkeypatch.setattr(runtime, "_finalize_run",
                            lambda ctx, *, final_status, errors, run_error_message,
                                   rate_limited: (final_status, [], errors, rate_limited))
        reconnect = PgRepositoryClient(pg)
        try:
            status, _, errors, _ = runtime.resume_paused_workflow_graph(
                SimpleNamespace(), ORG, "synthetic-approver", run_id,
                client=reconnect, environment_name="synthetic")
        except runtime.GraphValidationError:
            assert provider_result == "unknown"
            assert invoked == []
            assert pg.value(f"SELECT status FROM public.workflow_runs WHERE id='{run_id}'") == "paused"
            assert repository.get_run_with_steps(
                PgRepositoryClient(pg), ORG, run_id, "synthetic")[
                    "parameters"]["_graph_execution"]["paused_at_node"] == "write"
        else:
            assert provider_result != "unknown"
            assert status == "completed" and errors == []
            assert invoked == (["continue"] if provider_result == "applied"
                               else ["write", "continue"])
            prior = repository.get_run_with_steps(
                PgRepositoryClient(pg), ORG, run_id, "synthetic")["steps"][0]
            assert prior["status"] == ("completed" if provider_result == "applied"
                                      else "failed")
        assert len(readbacks) == 1
        assert pg.value("SELECT count(*) FROM public.qa_p27_authoritative_provider") == (
            "1" if provider_result != "unknown" else "0"
        )
