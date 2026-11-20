"""P27-06 deterministic proof of SQL orphan detection, atomic ownership and fencing."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from tests.db.pg_harness import requires_pg
from tests.db.test_domain_event_outbox_pg import ORG
from tests.master_qa.canonical_pg_repository import PgRepositoryClient, canonical_pg_cluster

pytestmark = requires_pg


def _orphan(pg):
    from app.workflows import repository
    client = PgRepositoryClient(pg)
    workflow_id = "22222222-2222-4222-8222-222222222222"
    pg.psql(f"INSERT INTO public.workflows (id,org_id,name) "
            f"VALUES ('{workflow_id}','{ORG}','P27 SQL lease test')")
    run = repository.create_execute_run(
        client, ORG, workflow_id, "synthetic-owner",
        {"graph": {"nodes": [{"id": "write", "node_type": "connector",
            "config": {"action": "hubspot.contacts.create"}}], "edges": []}},
        {}, "orphan-hash", "running", "approved", 0, [],
        environment_name="synthetic")
    run_id = run["id"]
    step = repository.create_step(client, run_id, ORG, "write", 0,
                                  "Create CRM", "invoke_tool")
    repository.set_step_running(client, step["id"], "2026-01-01T00:00:00+00:00")
    repository.merge_run_parameters(client, run_id, {
        "_graph_execution": {
            "paused_at_node": "write", "batch_index": 0, "step_index": 0,
            "node_outputs": {}, "nodes": [{"id": "write", "node_type": "connector",
                "config": {"action": "hubspot.contacts.create"}}], "edges": [],
        },
    })
    return run_id


def test_atomic_claim_elects_only_one_recovery_owner_for_stale_running_graph():
    with canonical_pg_cluster() as pg:
        run_id = _orphan(pg)
        assert pg.value(
            "SELECT has_function_privilege('authenticated',"
            "'public.claim_stale_graph_recovery(text,integer,integer)','EXECUTE')"
        ) == "f"
        def claimant(n):
            return PgRepositoryClient(pg).rpc("claim_stale_graph_recovery", {
                "p_owner": f"orphan-recoverer-{n}",
                "p_stale_seconds": 300, "p_lease_seconds": 600,
            }).execute().data
        with ThreadPoolExecutor(max_workers=6) as pool:
            all_claims = list(pool.map(claimant, range(6)))
        winners = [r[0] for r in all_claims if r]
        assert len(winners) == 1
        claim = winners[0]
        assert claim["run_id"] == run_id and claim["org_id"] == ORG
        assert claim["environment_name"] == "synthetic"
        assert pg.value(f"SELECT status FROM public.workflow_runs WHERE id='{run_id}'") == "paused"
        owner = PgRepositoryClient(pg)
        assert owner.rpc("assert_graph_recovery_lease", {
            "p_run_id": run_id, "p_token": claim["claim_token"],
        }).execute().data is True
        assert owner.rpc("assert_graph_recovery_lease", {
            "p_run_id": run_id, "p_token": str(uuid4()),
        }).execute().data is False
        assert owner.rpc("release_graph_recovery_lease", {
            "p_run_id": run_id, "p_token": str(uuid4()),
        }).execute().data is False
        assert owner.rpc("renew_graph_recovery_lease", {
            "p_run_id": run_id, "p_token": claim["claim_token"],
            "p_seconds": 600,
        }).execute().data is True
        assert owner.rpc("release_graph_recovery_lease", {
            "p_run_id": run_id, "p_token": claim["claim_token"],
        }).execute().data is True
        # A second recovery is NOT possible simply because lease was released:
        # ownership transitions the run out of running atomically.
        assert claimant(99) == []
        assert pg.value(f"SELECT status FROM public.workflow_runs WHERE id='{run_id}'") == "paused"


def test_recent_active_step_never_claimed_even_when_run_created_long_ago():
    from app.workflows import repository
    with canonical_pg_cluster() as pg:
        run_id = _orphan(pg)
        pg.psql("UPDATE public.workflow_steps SET started_at=now() "
                f"WHERE run_id='{run_id}'")
        row = PgRepositoryClient(pg).rpc("claim_stale_graph_recovery", {
            "p_owner": "orphan-recoverer-new", "p_stale_seconds": 300,
            "p_lease_seconds": 600,
        }).execute().data
        assert row == []
        assert pg.value(f"SELECT status FROM public.workflow_runs WHERE id='{run_id}'") == "running"


def test_recovery_worker_invokes_original_resume_once_with_lease(monkeypatch):
    from app.services import workflow_orphan_reconciler as service
    from app.workflows import execution_engine_runtime as runtime, repository
    with canonical_pg_cluster() as pg:
        run_id = _orphan(pg)
        monkeypatch.setattr(service, "get_supabase_client", lambda settings: PgRepositoryClient(pg))
        actions = []
        def resume(settings, org_id, actor, rid, *, client, environment_name, recovery_token):
            assert (org_id, rid, environment_name) == (ORG, run_id, "synthetic")
            assert client.rpc("assert_graph_recovery_lease", {
                "p_run_id": rid, "p_token": recovery_token,
            }).execute().data is True
            actions.append(rid)
            return "paused", [], [], False
        monkeypatch.setattr(runtime, "resume_paused_workflow_graph", resume)
        result = service.recover_one_stale_graph_run(SimpleNamespace(
            workflow_orphan_stale_seconds=300, workflow_orphan_lease_seconds=600))
        assert result["state"] == "resumed"
        assert actions == [run_id]
        assert pg.value("SELECT count(*) FROM public.workflow_recovery_leases") == "0"
        assert service.recover_one_stale_graph_run(SimpleNamespace(
            workflow_orphan_stale_seconds=300))["state"] == "no_candidate"


def test_crashed_recovery_owner_can_be_reclaimed_only_after_lease_expires():
    from app.workflows import repository
    with canonical_pg_cluster() as pg:
        run_id = _orphan(pg)
        client = PgRepositoryClient(pg)
        state = repository.get_run_with_steps(client, ORG, run_id, "synthetic")
        checkpoint = state["parameters"]["_graph_execution"]
        repository.merge_run_parameters(client, run_id, {
            "_graph_execution": {**checkpoint, "pause_reason": "executor_in_flight"},
        })
        def claim(owner):
            return client.rpc("claim_stale_graph_recovery", {
                "p_owner": owner, "p_stale_seconds": 300,
                "p_lease_seconds": 600,
            }).execute().data
        first = claim("first-owner")[0]
        assert claim("overlapping-owner") == []
        assert pg.value(f"SELECT status FROM public.workflow_runs WHERE id='{run_id}'") == "paused"
        # The first owner's process exits without releasing its lease.
        # The database remains up and the lease is forcibly aged.
        pg.psql("UPDATE public.workflow_recovery_leases "
                "SET lease_expires_at=now()-interval '1 second' "
                f"WHERE run_id='{run_id}'")
        second = claim("replacement-owner")[0]
        assert second["run_id"] == run_id
        assert second["claim_token"] != first["claim_token"]
        assert pg.value(
            f"SELECT attempts FROM public.workflow_recovery_leases "
            f"WHERE run_id='{run_id}'") == "2"
        assert client.rpc("assert_graph_recovery_lease", {
            "p_run_id": run_id, "p_token": first["claim_token"],
        }).execute().data is False
        assert client.rpc("assert_graph_recovery_lease", {
            "p_run_id": run_id, "p_token": second["claim_token"],
        }).execute().data is True
        assert claim("third-overlap") == []
        # A stale process cannot release the replacement owner's claim.
        assert client.rpc("release_graph_recovery_lease", {
            "p_run_id": run_id, "p_token": first["claim_token"],
        }).execute().data is False
        assert pg.value(f"SELECT count(*) FROM public.workflow_recovery_leases "
                        f"WHERE run_id='{run_id}'") == "1"
