"""P27 graph process-loss recovery with persisted PostgreSQL checkpoint.

The child process records a committed, uniquely keyed synthetic provider effect,
persists the actual graph checkpoint through production repository methods,
and exits abruptly. A new process context invokes the real
resume_paused_workflow_graph scheduler with a fresh SQL client.

This tests *checkpointed* actions only. A crash after an external provider
write but before receipt/checkpoint persistence remains an UNCERTAIN outcome,
never a claim of exactly-once external delivery.
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
from tests.master_qa.canonical_pg_repository import (
    PgRepositoryClient, canonical_pg_cluster,
)

pytestmark = requires_pg


def test_graph_resume_after_crashed_process_skips_checkpointed_write(monkeypatch):
    from app.workflows import repository
    from app.workflows import execution_engine_runtime as runtime

    workflow_id = "22222222-2222-4222-8222-222222222222"
    nodes = [
        {"id": "trigger", "node_type": "source", "title": "Trigger"},
        {"id": "write", "node_type": "agent", "title": "Approved action",
         "metadata": {"agent_id": "qa-write", "task": "Synthetic write"}},
        {"id": "resume", "node_type": "agent", "title": "Resume",
         "metadata": {"agent_id": "qa-resume", "task": "Continue"}},
    ]
    edges = [
        {"from_node_id": "trigger", "to_node_id": "write"},
        {"from_node_id": "write", "to_node_id": "resume"},
    ]
    definition = {"graph": {"nodes": nodes, "edges": edges}}
    with canonical_pg_cluster() as pg:
        client = PgRepositoryClient(pg)
        pg.psql(f"INSERT INTO public.workflows (id,org_id,name) "
                f"VALUES ('{workflow_id}','{ORG}','Graph restart fixture')")
        run = repository.create_execute_run(
            client=client, org_id=ORG, workflow_id=workflow_id,
            triggered_by="synthetic-owner", definition_snapshot=definition,
            parameters={}, run_hash="checkpoint-recovery",
            status="running", approval_status="approved",
            required_approvals=0, approver_roles=[], environment_name="synthetic")
        run_id = run["id"]
        pg.psql("CREATE TABLE public.qa_checkpointed_provider_effects ("
                "action_key text PRIMARY KEY, run_id uuid NOT NULL, "
                "provider_id text NOT NULL)")
        checkpoint = {
            "paused_at_node": "resume", "batch_index": 2, "step_index": 2,
            "node_outputs": {
                "trigger": {"passthrough": True},
                "write": {"outcome_verified": True, "provider_id": "sandbox-fixture-1",
                          "idempotency_key": f"{run_id}:write"},
            },
            "skipped_nodes": [], "approval_context": {}, "nodes": nodes, "edges": edges,
            "pause_reason": "operator_interrupt",
        }
        # A separate OS process writes the committed provider receipt and
        # checkpoint. os._exit simulates abrupt interpreter termination.
        child_script = """
import os, json, psycopg
from types import SimpleNamespace
from app.workflows import repository
from tests.master_qa.canonical_pg_repository import PgRepositoryClient
with psycopg.connect(host=os.environ["P27_SOCK"], port=os.environ["P27_PORT"],
                     user="postgres", dbname="postgres") as conn:
    with conn.cursor() as cursor:
        cursor.execute(
            "INSERT INTO public.qa_checkpointed_provider_effects "
            "(action_key,run_id,provider_id) VALUES (%s,%s,%s)",
            (os.environ["P27_KEY"],os.environ["P27_RUN"],"sandbox-fixture-1"))
pg = SimpleNamespace(sock=os.environ["P27_SOCK"], port=os.environ["P27_PORT"])
client = PgRepositoryClient(pg)
repository.merge_run_parameters(
    client, os.environ["P27_RUN"],
    {"_graph_execution":json.loads(os.environ["P27_CHECKPOINT"])})
repository.update_run(client, os.environ["P27_RUN"], "paused")
os._exit(79)
"""
        env = {
            **os.environ, "P27_SOCK": str(pg.sock), "P27_PORT": pg.port,
            "P27_KEY": f"{run_id}:write", "P27_RUN": run_id,
            "P27_ORG": ORG, "P27_CHECKPOINT": json.dumps(checkpoint),
        }
        child = subprocess.run(
            [sys.executable, "-c", child_script],
            env=env, capture_output=True, text=True, timeout=20)
        assert child.returncode == 79, child.stderr
        assert pg.value(f"SELECT status FROM public.workflow_runs WHERE id='{run_id}'") == "paused"
        assert pg.value("SELECT count(*) FROM public.qa_checkpointed_provider_effects") == "1"

        invoked = []
        # Keep the scheduler and production SQL repository real. Only the
        # downstream agent executor and terminal notification fanout are local.
        def resumed_node(ctx, node_id, index):
            invoked.append(node_id)
            assert node_id == "resume", "checkpointed write was replayed"
            with ctx.lock:
                ctx.node_outputs[node_id] = {"continued": True}
            return runtime._NodeRunResult(node_id, index + 1)
        monkeypatch.setattr(runtime, "_execute_graph_node", resumed_node)
        monkeypatch.setattr(runtime, "get_run_with_steps", repository.get_run_with_steps)
        monkeypatch.setattr(runtime, "merge_run_parameters", repository.merge_run_parameters)
        monkeypatch.setattr(runtime, "update_run", repository.update_run)
        monkeypatch.setattr(runtime, "_finalize_run",
                            lambda ctx, *, final_status, errors, run_error_message,
                                   rate_limited: (final_status, [], errors, rate_limited))
        status, _, errors, _ = runtime.resume_paused_workflow_graph(
            SimpleNamespace(), ORG, "synthetic-approver", run_id,
            client=PgRepositoryClient(pg), environment_name="synthetic")
        assert status == "completed" and errors == []
        assert invoked == ["resume"]
        assert pg.value("SELECT count(*) FROM public.qa_checkpointed_provider_effects") == "1"
        assert repository.get_run_with_steps(
            PgRepositoryClient(pg), ORG, run_id, "synthetic")["parameters"].get(
                "_graph_execution") is None
