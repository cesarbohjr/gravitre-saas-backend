"""P27 staging-style OS-process kill/restart in disposable PostgreSQL.

This is *not* a deployed staging or live HubSpot acceptance test. It does
prove that a real child worker dies after SQL ownership, a second worker takes
over the expired lease, and authoritative provider readback prevents replay.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

from tests.db.pg_harness import requires_pg
from tests.db.test_domain_event_outbox_pg import ORG
from tests.master_qa.canonical_pg_repository import (
    PgRepositoryClient, canonical_pg_cluster,
)

pytestmark = requires_pg


def test_worker_process_crash_then_new_worker_recovers_applied_write_once():
    from app.workflows import repository

    wf = "22222222-2222-4222-8222-222222222222"
    nodes = [
        {"id": "trigger", "node_type": "source", "title": "Trigger"},
        {"id": "write", "node_type": "connector", "title": "Create test contact",
         "config": {"action": "hubspot.contacts.create",
                    "params": {"email": "qa-restart@example.invalid"}}},
    ]
    edges = [{"from_node_id": "trigger", "to_node_id": "write"}]
    with canonical_pg_cluster() as pg:
        client = PgRepositoryClient(pg)
        pg.psql(f"INSERT INTO public.workflows (id,org_id,name) "
                f"VALUES ('{wf}','{ORG}','P27 worker restart')")
        run = repository.create_execute_run(
            client, ORG, wf, "synthetic-owner",
            {"graph": {"nodes": nodes, "edges": edges}},
            {}, "p27-process-restart", "running", "approved", 0, [],
            environment_name="synthetic")
        run_id = run["id"]
        step = repository.create_step(
            client, run_id, ORG, "write", 1, "Create test contact",
            "invoke_tool")
        repository.set_step_running(
            client, step["id"], "2026-01-01T00:00:00+00:00")
        repository.update_step(
            client, step["id"], "running",
            input_snapshot={"config": nodes[1]["config"]})
        repository.merge_run_parameters(client, run_id, {
            "_graph_execution": {
                "paused_at_node": "write",
                "batch_index": 1,
                "step_index": 1,
                "node_outputs": {"trigger": {"passthrough": True}},
                "skipped_nodes": [],
                "approval_context": {},
                "nodes": nodes, "edges": edges,
                "pause_reason": "executor_in_flight",
            },
        })
        pg.psql("CREATE TABLE public.qa_p27_restart_provider ("
                "action_key text PRIMARY KEY, record_id text NOT NULL)")
        # The external system commits before the worker has recorded output.
        pg.psql(
            "INSERT INTO public.qa_p27_restart_provider (action_key,record_id) "
            f"VALUES ('{run_id}:write','provider-contact-1')")
        environment = {
            **os.environ,
            "P27_PG_SOCK": str(pg.sock), "P27_PG_PORT": pg.port,
            "P27_RUN_ID": run_id, "P27_ORG_ID": ORG,
        }
        cmd = [sys.executable, "-m", "tests.master_qa._p27_worker_subprocess"]
        first = subprocess.run(
            [*cmd, "crash"], capture_output=True, text=True,
            env=environment, timeout=35)
        assert first.returncode == 93, first.stderr
        assert pg.value(
            f"SELECT status FROM public.workflow_runs WHERE id='{run_id}'"
        ) == "paused"
        old_token = pg.value(
            f"SELECT token FROM public.workflow_recovery_leases WHERE run_id='{run_id}'")
        assert old_token
        # The SQL lease is the durable owner; simulate its actual deadline.
        pg.psql(
            "UPDATE public.workflow_recovery_leases "
            "SET lease_expires_at=now()-interval '1 second' "
            f"WHERE run_id='{run_id}'")
        assert client.rpc("assert_graph_recovery_lease", {
            "p_run_id": run_id, "p_token": old_token,
        }).execute().data is False
        second = subprocess.run(
            [*cmd, "restart"], capture_output=True, text=True,
            env=environment, timeout=35)
        assert second.returncode == 0, second.stderr + second.stdout
        outcome = json.loads(second.stdout.strip().splitlines()[-1])
        assert outcome == {
            "state": "resumed", "status": "completed",
            "run_id": run_id, "errors": 0,
        }
        assert pg.value(
            "SELECT count(*) FROM public.qa_p27_restart_provider"
        ) == "1"
        assert pg.value(
            f"SELECT status FROM public.workflow_steps WHERE run_id='{run_id}'"
        ) == "completed"
        assert pg.value(
            f"SELECT status FROM public.workflow_runs WHERE id='{run_id}'"
        ) == "completed"
        assert pg.value(
            f"SELECT count(*) FROM public.domain_event_outbox WHERE aggregate_id='{run_id}'"
        ) == "1"
        assert pg.value(
            "SELECT count(*) FROM public.workflow_recovery_leases"
        ) == "0"
