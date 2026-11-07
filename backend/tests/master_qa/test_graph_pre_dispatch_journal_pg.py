"""The graph runtime must journal a mutating invoke_tool BEFORE calling it."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from tests.db.pg_harness import requires_pg
from tests.db.test_domain_event_outbox_pg import ORG
from tests.master_qa.canonical_pg_repository import PgRepositoryClient, canonical_pg_cluster

pytestmark = requires_pg


def test_mutating_graph_node_has_sql_checkpoint_and_selector_before_dispatch(monkeypatch):
    from app.workflows import repository
    from app.workflows import execution_engine_runtime as runtime
    from app.workflows import graph_model

    workflow_id = "22222222-2222-4222-8222-222222222222"
    email = "p27-contact@example.invalid"
    nodes = [
        {"id": "trigger", "node_type": "source", "title": "Trigger"},
        {"id": "write", "node_type": "connector", "title": "Create test contact",
         "config": {"action": "hubspot.contacts.create",
                    "params": {"email": email}}},
    ]
    edges = [{"from_node_id": "trigger", "to_node_id": "write"}]
    with canonical_pg_cluster() as pg:
        client = PgRepositoryClient(pg)
        pg.psql(f"INSERT INTO public.workflows (id,org_id,name) "
                f"VALUES ('{workflow_id}','{ORG}','Pre-dispatch journal fixture')")
        created = repository.create_execute_run(
            client, ORG, workflow_id, "synthetic-owner",
            {"graph": {"nodes": nodes, "edges": edges}}, {},
            "pre-dispatch-hash", "running", "approved", 0, [],
            environment_name="synthetic")
        run_id = created["id"]
        graph = graph_model.build_execution_graph(nodes, edges)
        context = runtime._GraphRunContext(
            settings=SimpleNamespace(convergence_p5_workflow_child_identity_v1=False),
            org_id=ORG, user_id="synthetic-owner", run_id=run_id,
            graph=graph, edge_dicts=graph_model.graph_edge_dicts(graph),
            parameters={}, client=client, environment_name="synthetic",
            node_outputs={"trigger": {"passthrough": True}},
            skipped_nodes=[], step_index=1,
        )
        captured = []

        class FakeHandler:
            supports_execute = True
            def execute(self, step):
                # Simulates entering the provider transport; no external call.
                source = repository.get_run_with_steps(
                    PgRepositoryClient(pg), ORG, run_id, "synthetic")
                journal = source["parameters"]["_graph_execution"]
                assert journal["paused_at_node"] == "write"
                assert journal["pause_reason"] == "executor_in_flight"
                assert journal["batch_index"] == 1
                assert journal["node_outputs"]["trigger"]["passthrough"] is True
                running = source["steps"]
                assert len(running) == 1 and running[0]["status"] == "running"
                assert running[0]["input_snapshot"]["config"]["params"]["email"] == email
                captured.append(step.step_id)
                return {"outcome_verified": True, "provider_id": "synthetic-only"}

        monkeypatch.setattr(runtime, "get_handler", lambda _: FakeHandler())
        monkeypatch.setattr(runtime, "enforce_interrupt", lambda *a, **kw: None)
        monkeypatch.setattr(runtime, "resolve_active_branch", lambda *_: None)
        monkeypatch.setattr(runtime, "should_skip_for_branch", lambda *a, **kw: False)
        monkeypatch.setattr(runtime, "emit_execute_step_completed", lambda *a: None)
        monkeypatch.setattr(runtime, "write_audit_event", lambda *a, **kw: None)
        outcome = runtime._execute_graph_node(context, "write", 1)
        assert outcome.halt is None
        assert captured == ["write"]
        rows = repository.get_run_with_steps(
            PgRepositoryClient(pg), ORG, run_id, "synthetic")["steps"]
        assert rows[0]["status"] == "completed"


def test_manual_resume_cannot_bypass_active_sql_recovery_lease(monkeypatch):
    from app.workflows import execution_engine_runtime as runtime
    from tests.master_qa.test_orphan_graph_claim_pg import _orphan

    with canonical_pg_cluster() as pg:
        run_id = _orphan(pg)
        client = PgRepositoryClient(pg)
        claim = client.rpc("claim_stale_graph_recovery", {
            "p_owner": "qa-claim-holder", "p_stale_seconds": 300,
            "p_lease_seconds": 600,
        }).execute().data[0]
        assert claim["run_id"] == run_id
        with pytest.raises(runtime.GraphValidationError,
                           match="already owns"):
            runtime.resume_paused_workflow_graph(
                SimpleNamespace(), ORG, "synthetic-owner", run_id,
                client=PgRepositoryClient(pg), environment_name="synthetic")
        assert pg.value(f"SELECT status FROM public.workflow_runs WHERE id='{run_id}'") == "paused"
        assert pg.value(f"SELECT count(*) FROM public.workflow_steps WHERE run_id='{run_id}'") == "1"
