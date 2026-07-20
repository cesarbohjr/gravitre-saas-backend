"""Shared post-execute handling for connector/webhook trigger services (Module A).

execute_workflow_steps / ExecutionService already call finalize_execution_outcome()
on terminal success/failure. Trigger callers must NOT re-write workflow_runs status.

On crash *before* the execute stack finalizes, call finalize_trigger_exception()
so the run still gets the full Module A fanout.
"""
from __future__ import annotations

from typing import Any

from app.core.logging import get_logger
from app.services.execution_outcome import VerifiedOutputRef, finalize_execution_outcome

logger = get_logger(__name__)


def finalize_trigger_exception(
    client: Any,
    *,
    org_id: str,
    run_id: str,
    actor_id: str | None,
    workflow_id: str | None,
    error: str,
    source: str = "api",
) -> None:
    """Terminal fanout when a trigger's execute_workflow call raises."""
    try:
        finalize_execution_outcome(
            client,
            org_id=org_id,
            status="failed",
            source="api" if source not in {
                "chat_orch", "assistant_chat", "canvas", "api", "worker", "assignment"
            } else source,  # type: ignore[arg-type]
            actor_id=actor_id,
            run_id=run_id,
            workflow_id=workflow_id,
            error_summary=str(error)[:2000],
            verified_output=VerifiedOutputRef(
                summary=str(error)[:2000],
                result_url=f"/runs/{run_id}",
                entity_type="workflow_run",
                entity_id=run_id,
            ),
            metadata={"path": "trigger_exception", "trigger_source": source},
        )
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "trigger_exception_finalize_failed org_id=%s run_id=%s error=%s",
            org_id,
            run_id,
            exc,
        )
