"""Cross-layer QA: real canonical Play router, guard and PostgreSQL outbox.

The real Play's preflight/routing and write-authority gate are exercised. A
synthetic workflow executor and mock connector provide deterministic outcomes,
while the real SQL terminal trigger, application relay, and durable consumer
write run against throwaway PostgreSQL. No claim of a complete live workflow
executor, real agent selection, or external provider readback.
"""
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock

import pytest

from tests.db.pg_harness import requires_pg
from tests.db.test_domain_event_outbox_pg import (
    ORG, _PsqlRpcClient, _new_run, pg,
)

pytestmark = requires_pg


@pytest.mark.asyncio
async def test_canonical_play_handoff_to_guarded_synthetic_connector_and_durable_consumer(pg, monkeypatch):
    from app.routers import plays, workflows
    from app.services import domain_events, outcome_verification
    from app.services.write_authority import (
        WriteAuthorityError, check_write_authority, write_authority,
    )
    from app.services import work_loop_links

    # Real Play router preflight; only its backend data dependencies are local
    # fixtures, never production records. Identifiers are synthetic UUIDs.
    db = MagicMock()
    monkeypatch.setattr(plays, "get_supabase_client", lambda _settings: db)
    monkeypatch.setattr(plays, "_load_installation", lambda *args, **kwargs: {
        "id": "fixture-install", "operating_mode": "ACT WITH APPROVAL",
    })
    monkeypatch.setattr(work_loop_links, "resolve_run_links", lambda *args, **kwargs: (None, None))
    monkeypatch.setattr(plays, "connected_vendors", lambda *args, **kwargs: {"hubspot"})
    monkeypatch.setattr(plays, "resolve_play_readiness", lambda *args, **kwargs: SimpleNamespace(
        act_with_approval_ready=True,
    ))
    monkeypatch.setattr(plays, "_observed_signals", lambda *args, **kwargs: set())
    monkeypatch.setattr(plays, "list_play_workflow_bindings", lambda *args, **kwargs: [
        {"workflowId": "22222222-2222-4222-8222-222222222222"},
    ])
    monkeypatch.setattr(plays, "get_workflow_def", lambda *args, **kwargs: {"id": "22222222-2222-4222-8222-222222222222"})
    monkeypatch.setattr(plays, "resolve_policy", lambda *args, **kwargs: (1, ["admin"]))
    monkeypatch.setattr(plays, "write_audit_event", lambda *args, **kwargs: None)

    # Fake provider must not be invoked without the real write gate. The
    # workflow's *executor* is intentionally a stub: scope is Play dispatch.
    provider = Mock(return_value={"id": "local-vendor-fixture-1"})
    monkeypatch.setattr(outcome_verification, "is_write_action",
                        lambda action: action == "synthetic.qa.write")
    cfg = SimpleNamespace(write_authority_mode="enforce")
    execution_arguments = []

    async def offline_executor(body, *, current_user, org_id, environment_name, settings):
        execution_arguments.append((body, org_id))
        assert body.workflow_id == "22222222-2222-4222-8222-222222222222"
        assert body.play_key == "customer-rescue"
        assert body.parameters["play"]["execution_authority"] == "canonical_workflow_runtime"
        assert org_id == ORG
        assert environment_name == "synthetic"
        with pytest.raises(WriteAuthorityError):
            check_write_authority("synthetic.qa.write", settings=cfg)
        provider.assert_not_called()
        with write_authority("human", "fixture-explicit-human-approval"):
            assert check_write_authority("synthetic.qa.write", settings=cfg).kind == "human"
            receipt = provider()
            assert receipt["id"] == "local-vendor-fixture-1"
            run_id = _new_run(pg)
            pg.psql(f"UPDATE public.workflow_runs SET status='completed' WHERE id='{run_id}';")
        return {"run_id": run_id, "status": "completed", "approval_required": True}

    monkeypatch.setattr(workflows, "execute_workflow", offline_executor)
    response = await plays.run_play(
        "customer-rescue",
        plays.RunPlayRequest(installationId="fixture-install"),
        ({"user_id": "synthetic-owner"}, ORG, "admin"),
        "synthetic",
        cfg,
    )
    assert len(execution_arguments) == 1
    assert provider.call_count == 1
    assert response["executionAuthority"] == "canonical_workflow_runtime"
    assert response["workflowRuns"][0]["approvalRequired"] is True
    assert response["workflowRuns"][0]["runId"]
    run_id = response["workflowRuns"][0]["runId"]

    # Actual database outbox and registered application relay, durable effect
    # keyed by event id; repeated relay invocation cannot double-apply it.
    assert pg.value("SELECT count(*) FROM public.domain_event_outbox;") == "1"
    pg.psql("CREATE TABLE public.qa_master_play_consumer_effects ("
            "event_id bigint PRIMARY KEY, org_id uuid NOT NULL, run_id uuid NOT NULL);")

    def consumer(_client, event):
        assert event["org_id"] == ORG
        assert event["aggregate_id"] == run_id
        pg.psql("INSERT INTO public.qa_master_play_consumer_effects "
                "(event_id,org_id,run_id) "
                f"VALUES ({int(event['id'])},'{ORG}','{run_id}') "
                "ON CONFLICT (event_id) DO NOTHING;")

    domain_events.reset_domain_event_handlers_for_tests()
    domain_events.register_domain_event_handler(
        domain_events.EVENT_EXECUTION_OUTCOME_FINALIZED,
        "master_qa_play_consumer",
        consumer,
    )
    try:
        relay = domain_events.DomainEventRelay(_PsqlRpcClient(pg), worker_id="qa-play-worker")
        first, replay = relay.run_once(), relay.run_once()
    finally:
        domain_events.reset_domain_event_handlers_for_tests()
    assert first.delivered == 1
    assert replay.claimed == 0
    assert pg.value("SELECT count(*) FROM public.qa_master_play_consumer_effects;") == "1"
    row = json.loads(pg.value("SELECT row_to_json(e) FROM public.qa_master_play_consumer_effects e;"))
    assert row["org_id"] == ORG
    assert row["run_id"] == run_id
