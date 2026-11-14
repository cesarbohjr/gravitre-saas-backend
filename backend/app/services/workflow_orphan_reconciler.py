"""P27-06: automatic, fenced orphan graph recovery on the existing workflow worker.

A PostgreSQL function atomically elects one owner AND parks a stale graph run
before any provider reconciliation. No unconstrained scan/replay is permitted.
All outbound attempts still run through the original graph execution gates.
"""
from __future__ import annotations

import logging
import threading
from uuid import uuid4

from app.workflows.repository import get_supabase_client

logger = logging.getLogger(__name__)


def _rpc_bool(client, name: str, params: dict) -> bool:
    result = client.rpc(name, params).execute().data
    return result is True or result == "true"


def recover_one_stale_graph_run(settings) -> dict:
    """Claim at most one old in-flight graph; never retry an unverified action."""
    from app.workflows.execution_engine_runtime import resume_paused_workflow_graph

    client = get_supabase_client(settings)
    owner = f"workflow-orphan-worker:{uuid4().hex}"
    stale_seconds = max(300, int(getattr(settings, "workflow_orphan_stale_seconds", 3600)))
    lease_seconds = max(60, min(3600, int(getattr(settings, "workflow_orphan_lease_seconds", 600))))
    claim_result = client.rpc("claim_stale_graph_recovery", {
        "p_owner": owner,
        "p_stale_seconds": stale_seconds,
        "p_lease_seconds": lease_seconds,
    }).execute().data
    rows = claim_result if isinstance(claim_result, list) else ([claim_result] if isinstance(claim_result, dict) else [])
    if not rows:
        return {"state": "no_candidate"}

    claim = rows[0]
    run_id, org_id, token = (str(claim[k]) for k in ("run_id", "org_id", "claim_token"))
    if not _rpc_bool(client, "assert_graph_recovery_lease", {
        "p_run_id": run_id, "p_token": token,
    }):
        raise RuntimeError("graph recovery claim was lost before resume")

    stopped = threading.Event()
    lost = threading.Event()

    def heartbeat() -> None:
        # A separate client avoids sharing a PostgREST session across threads.
        interval = max(10, lease_seconds // 3)
        while not stopped.wait(interval):
            try:
                check = get_supabase_client(settings)
                if not _rpc_bool(check, "renew_graph_recovery_lease", {
                    "p_run_id": run_id, "p_token": token, "p_seconds": lease_seconds,
                }):
                    lost.set()
                    logger.error("graph_recovery_lease_lost run_id=%s", run_id)
                    return
            except Exception:
                lost.set()
                logger.exception("graph_recovery_lease_renewal_failed run_id=%s", run_id)
                return

    thread = threading.Thread(target=heartbeat, daemon=True)
    thread.start()
    try:
        # Graph resume checks the SQL token before each uncheckpointed node;
        # a stale replica cannot proceed after ownership loss.
        final_status, _, errors, _ = resume_paused_workflow_graph(
            settings,
            org_id,
            str(claim.get("actor_id") or "system"),
            run_id,
            client=client,
            environment_name=str(claim.get("environment_name") or "default"),
            recovery_token=token,
        )
        if lost.is_set():
            raise RuntimeError("graph recovery lease expired while resuming")
        return {"state": "resumed", "run_id": run_id, "status": final_status,
                "errors": len(errors)}
    except Exception as exc:
        # The run remains paused with checkpoint if reconciliation is uncertain.
        # Do not enqueue a second job or bypass the current executor.
        logger.warning("graph_recovery_blocked run_id=%s reason=%s",
                       run_id, type(exc).__name__)
        return {"state": "blocked", "run_id": run_id, "reason": type(exc).__name__}
    finally:
        stopped.set()
        thread.join(timeout=2)
        try:
            client.rpc("release_graph_recovery_lease", {
                "p_run_id": run_id, "p_token": token,
            }).execute()
        except Exception:
            logger.exception("graph_recovery_release_failed run_id=%s", run_id)
