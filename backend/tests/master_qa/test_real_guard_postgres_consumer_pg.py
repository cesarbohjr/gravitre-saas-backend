"""Actual Gravitre write fence -> PostgreSQL outcome -> registered relay consumer.

The actor/provider/agent/Play components are NOT exercised here. The guarded
outcome handoff and its durable synthetic consumer effect ARE exercised against
the real application guard, domain relay and throwaway PostgreSQL. This is
offline P27-03/P27-04 *partial* preproduction evidence, not a full P27 pass.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from tests.db.pg_harness import requires_pg
from tests.db.test_domain_event_outbox_pg import ORG, _new_run, _PsqlRpcClient, pg

pytestmark = requires_pg


def test_governed_outcome_flows_through_real_postgres_relay_to_durable_consumer(pg, monkeypatch):
    from app.services import domain_events, outcome_verification
    from app.services.write_authority import (
        WriteAuthorityError, check_write_authority, write_authority,
    )

    monkeypatch.setattr(outcome_verification, "is_write_action", lambda action: action == "synthetic.qa.write")
    cfg = SimpleNamespace(write_authority_mode="enforce")

    # The real application guard must deny a missing approval before any
    # run/outbox/provider effect. No fake success or speculative side effect.
    with pytest.raises(WriteAuthorityError):
        check_write_authority("synthetic.qa.write", settings=cfg)
    assert pg.value("SELECT count(*) FROM public.workflow_runs;") == "0"
    assert pg.value("SELECT count(*) FROM public.domain_event_outbox;") == "0"

    # Synthetic approval scope is used ONLY to exercise the real write fence.
    # It is not a claim that a real user approved an agent/Play/provider action.
    with write_authority("human", "synthetic-approved-for-qa"):
        auth = check_write_authority("synthetic.qa.write", settings=cfg)
        assert auth is not None and auth.kind == "human"
        run_id = _new_run(pg)
        pg.psql(
            f"UPDATE public.workflow_runs SET status='completed' WHERE id='{run_id}';"
        )

    # The actual SQL trigger creates one event atomically with the terminal
    # workflow update; the Python relay uses real PostgreSQL claim/complete RPCs.
    assert pg.value("SELECT count(*) FROM public.domain_event_outbox;") == "1"
    pg.psql(
        "CREATE TABLE IF NOT EXISTS public.qa_master_consumer_effects ("
        "event_id bigint PRIMARY KEY, org_id uuid NOT NULL, run_id uuid NOT NULL);"
    )
    seen = []

    def persist(_client, event):
        assert event["org_id"] == ORG
        assert event["aggregate_id"] == run_id
        seen.append(event["id"])
        pg.psql(
            "INSERT INTO public.qa_master_consumer_effects (event_id, org_id, run_id) "
            f"VALUES ({int(event['id'])}, '{ORG}', '{run_id}') "
            "ON CONFLICT (event_id) DO NOTHING;"
        )

    domain_events.reset_domain_event_handlers_for_tests()
    domain_events.register_domain_event_handler(
        domain_events.EVENT_EXECUTION_OUTCOME_FINALIZED,
        "qa_master_durable_consumer",
        persist,
    )
    try:
        relay = domain_events.DomainEventRelay(_PsqlRpcClient(pg), worker_id="qa-master-worker")
        result = relay.run_once()
        repeat = relay.run_once()
    finally:
        domain_events.reset_domain_event_handlers_for_tests()

    assert result.claimed == result.delivered == 1
    assert repeat.claimed == 0
    assert len(seen) == 1
    assert pg.value("SELECT count(*) FROM public.qa_master_consumer_effects;") == "1"
    assert pg.value("SELECT count(*) FROM public.domain_event_outbox WHERE status='delivered';") == "1"
    row = json.loads(pg.value("SELECT row_to_json(x) FROM public.qa_master_consumer_effects x;"))
    assert row["run_id"] == run_id
    assert row["org_id"] == ORG
