"""Isolated P27 worker-process crash/restart actor.

Invoked only by a disposable PostgreSQL integration test. The parent creates
the graph, SQL provider stand-in and initial in-flight step. This subprocess
uses the *production* SQL claim and orphan-recovery service, with only the
provider API and terminal fanout replaced by local deterministic adapters.
"""
from __future__ import annotations

import json
import os
import sys
from types import SimpleNamespace

from tests.master_qa.canonical_pg_repository import PgRepositoryClient


def main() -> None:
    from app.services import workflow_orphan_reconciler as service
    from app.services.outcome_reconciliation import ReconciliationResult
    from app.workflows import execution_engine_runtime as runtime, repository

    pg = SimpleNamespace(sock=os.environ["P27_PG_SOCK"], port=os.environ["P27_PG_PORT"])
    run_id = os.environ["P27_RUN_ID"]
    org_id = os.environ["P27_ORG_ID"]
    key = f"{run_id}:write"
    service.get_supabase_client = lambda _: PgRepositoryClient(pg)

    if sys.argv[1] == "crash":
        # The original provider has already committed, but the workflow still
        # has no receipt. Kill a *real recovery process* after the atomic SQL
        # claim/parking transaction and before provider reconciliation.
        runtime.resume_paused_workflow_graph = lambda *args, **kwargs: os._exit(93)
        service.recover_one_stale_graph_run(SimpleNamespace(
            workflow_orphan_stale_seconds=300, workflow_orphan_lease_seconds=600))
        raise AssertionError("crash worker must exit abruptly")

    if sys.argv[1] != "restart":
        raise RuntimeError("unsupported subprocess mode")

    def provider_readback(*, ctx, invoke_action, args):
        assert invoke_action == "hubspot.contacts.create"
        assert args["email"] == "qa-restart@example.invalid"
        from psycopg import connect
        with connect(host=str(pg.sock), port=pg.port, user="postgres",
                     dbname="postgres") as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT record_id FROM public.qa_p27_restart_provider "
                    "WHERE action_key=%s", (key,))
                row = cursor.fetchone()
        assert row == ("provider-contact-1",)
        return ReconciliationResult(
            "applied", "independent_source_of_record", row[0],
            "hubspot.contacts.get",
            {"verified": True, "method": "provider_authoritative_get",
             "resource_id": row[0]})

    import app.services.outcome_reconciliation as reconciliation
    import app.services.tool_service as tool_service

    reconciliation.reconcile_uncertain_write = provider_readback
    tool_service.tool_context_from_step = (
        lambda ctx: SimpleNamespace(org_id=ctx.org_id))
    runtime._execute_graph_node = lambda *args, **kwargs: (
        _ for _ in ()).throw(
        AssertionError("an already-applied connector was invoked again"))

    def finalize(ctx, *, final_status, errors, run_error_message, rate_limited):
        repository.update_run(ctx.client, ctx.run_id, final_status)
        return final_status, [], errors, rate_limited
    runtime._finalize_run = finalize
    outcome = service.recover_one_stale_graph_run(SimpleNamespace(
        workflow_orphan_stale_seconds=300, workflow_orphan_lease_seconds=600))
    print(json.dumps(outcome, sort_keys=True), flush=True)
    if outcome.get("state") != "resumed" or outcome.get("status") != "completed":
        sys.exit(4)


if __name__ == "__main__":
    main()
