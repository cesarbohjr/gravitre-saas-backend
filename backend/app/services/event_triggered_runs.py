"""Start a workflow run from an external event under the same governance as a manual run.

Event triggers (the generic signed webhook, HubSpot, Salesforce, Segment and
PagerDuty) used to create runs already marked ``approved`` with
``required_approvals=0`` and no policy check. The canvas write gate only lets
writes run when a run *required and received* approval, so any write step in an
event-triggered workflow failed silently every time.

Every trigger now resolves the org's workflow policy and the write-approval
floor exactly like a manual or scheduled run. A read-only workflow runs
immediately; a workflow with writes opens a pending approval through the same
``_open_pending_approval_run`` the canonical runner uses, and executes once a
person approves it.
"""
from __future__ import annotations

from typing import Any

from app.config import Settings
from app.core.logging import get_logger
from app.services.execution_service import ExecutionService, get_execution_service
from app.workflows.repository import create_execute_run
from app.workflows.schema import compute_run_hash

logger = get_logger(__name__)

WEBHOOK_EVENT_RECEIPTS_TABLE = "webhook_event_receipts"
_receipts_table_missing_logged = False


def _is_missing_table_error(exc: Exception) -> bool:
    text = str(exc)
    return "42P01" in text or "PGRST205" in text or (
        WEBHOOK_EVENT_RECEIPTS_TABLE in text and "does not exist" in text.lower()
    )


CLAIMED = "claimed"
DUPLICATE = "duplicate"
UNAVAILABLE = "unavailable"


def claim_webhook_event(client: Any, *, org_id: str, provider: str, event_id: str) -> str:
    """Record a provider event once.

    Insert-on-conflict-do-nothing on (org_id, provider, event_id). Returns CLAIMED
    for the first delivery, DUPLICATE for a retry, and UNAVAILABLE when the receipt
    could not be written (table missing or the write failed). Callers fail closed
    on UNAVAILABLE: no run starts and the provider is told to retry.
    """
    global _receipts_table_missing_logged
    try:
        resp = (
            client.table(WEBHOOK_EVENT_RECEIPTS_TABLE)
            .upsert(
                {"org_id": org_id, "provider": provider, "event_id": event_id},
                on_conflict="org_id,provider,event_id",
                ignore_duplicates=True,
            )
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        if _is_missing_table_error(exc):
            if not _receipts_table_missing_logged:
                _receipts_table_missing_logged = True
                logger.error("webhook_event_receipts_missing triggers_refused error=%s", exc)
        else:
            logger.error(
                "webhook_event_receipt_failed org_id=%s provider=%s event_id=%s error=%s",
                org_id,
                provider,
                event_id,
                exc,
            )
        return UNAVAILABLE
    return CLAIMED if resp.data else DUPLICATE


def raise_if_retryable(results: list[dict[str, Any]]) -> None:
    """Answer 503 so the provider redelivers when an event could not be recorded."""
    if any(r.get("retryable") for r in results):
        from fastapi import HTTPException

        raise HTTPException(status_code=503, detail="Event could not be recorded; retry later")


def release_webhook_event(client: Any, *, org_id: str, provider: str, event_id: str) -> None:
    """Forget a receipt so a provider retry can start the run that failed to start."""
    try:
        (
            client.table(WEBHOOK_EVENT_RECEIPTS_TABLE)
            .delete()
            .eq("org_id", org_id)
            .eq("provider", provider)
            .eq("event_id", event_id)
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "webhook_event_receipt_release_failed org_id=%s provider=%s event_id=%s error=%s",
            org_id,
            provider,
            event_id,
            exc,
        )


# Postgres rejected the statement, so no row exists: check, not-null, foreign key,
# unique (another receipt path already created it is handled by the receipt),
# invalid text representation, string too long.
_REJECTED_SQLSTATES = frozenset({"23514", "23502", "23503", "22P02", "22001"})


def _definitely_not_written(exc: BaseException) -> bool:
    """True when the run insert was refused by the database (the row was not created)."""
    code = str(getattr(exc, "code", "") or "")
    if code in _REJECTED_SQLSTATES:
        return True
    text = str(exc)
    return any(f"'{c}'" in text or f'"{c}"' in text or f"code: {c}" in text for c in _REJECTED_SQLSTATES) or (
        "violates check constraint" in text
    )


async def start_event_triggered_run(
    settings: Settings,
    client: Any,
    *,
    org_id: str,
    workflow_id: str,
    definition: dict[str, Any],
    parameters: dict[str, Any],
    actor_id: str,
    trigger_type: str,
    source: str,
    execution_service: ExecutionService | None = None,
    environment_name: str = "production",
    provider_event_id: str | None = None,
) -> dict[str, Any]:
    """Return ``{workflow_id, run_id?, status, error?, reason?}`` for one triggered run.

    With ``provider_event_id`` a provider retry of the same event does not start a
    second run of the same workflow (receipt key: ``<event id>:<workflow id>``).
    """
    receipt_id = f"{provider_event_id}:{workflow_id}" if provider_event_id else None
    if receipt_id:
        claim = claim_webhook_event(client, org_id=org_id, provider=trigger_type, event_id=receipt_id)
        if claim == DUPLICATE:
            logger.info(
                "%s_duplicate_event_skipped workflow_id=%s event_id=%s",
                source,
                workflow_id,
                provider_event_id,
            )
            return {"workflow_id": workflow_id, "status": "skipped", "reason": "duplicate_event"}
        if claim == UNAVAILABLE:
            return {
                "workflow_id": workflow_id,
                "status": "failed",
                "reason": "event_receipt_unavailable",
                "retryable": True,
            }
    # Set just before the first write that can create a run row. Once set, the
    # outcome is ambiguous (the row may exist), so the receipt is kept and a
    # provider retry is skipped rather than risking a second run.
    progress = {"run_write_attempted": False}
    try:
        result = await _start_event_triggered_run(
            settings,
            client,
            org_id=org_id,
            workflow_id=workflow_id,
            definition=definition,
            parameters=parameters,
            actor_id=actor_id,
            trigger_type=trigger_type,
            source=source,
            execution_service=execution_service,
            environment_name=environment_name,
            progress=progress,
        )
    except Exception as exc:
        if receipt_id and (not progress["run_write_attempted"] or _definitely_not_written(exc)):
            # Nothing was created, so a provider retry must be able to start the
            # run. (A rejected insert used to keep the receipt and lose the event.)
            release_webhook_event(client, org_id=org_id, provider=trigger_type, event_id=receipt_id)
        raise
    if receipt_id and not progress["run_write_attempted"] and not result.get("run_id"):
        release_webhook_event(client, org_id=org_id, provider=trigger_type, event_id=receipt_id)
    return result


async def _start_event_triggered_run(
    settings: Settings,
    client: Any,
    *,
    org_id: str,
    workflow_id: str,
    definition: dict[str, Any],
    parameters: dict[str, Any],
    actor_id: str,
    trigger_type: str,
    source: str,
    execution_service: ExecutionService | None = None,
    environment_name: str = "production",
    progress: dict[str, bool] | None = None,
) -> dict[str, Any]:
    from fastapi import HTTPException

    progress = progress if progress is not None else {}

    # app.routers.workflows must load after app.operators (pre-existing import order).
    import app.operators  # noqa: F401
    from app.billing.service import get_plan_for_org
    from app.routers.workflows import _evaluate_run_policy, _open_pending_approval_run
    from app.workflows.policy import PolicyResolutionError, resolve_policy

    run_hash = compute_run_hash(definition, parameters, str(definition.get("schema_version") or "v1"))
    try:
        required, roles = resolve_policy(client, org_id, workflow_id, "execute")
    except PolicyResolutionError as exc:
        # Fail closed: without a policy we cannot know who must approve.
        logger.error("%s_policy_resolution_failed workflow_id=%s error=%s", source, workflow_id, exc)
        return {"workflow_id": workflow_id, "status": "failed", "error": "Policy resolution failed"}

    decision = _evaluate_run_policy(
        settings,
        org_id=org_id,
        workflow_id=workflow_id,
        definition=definition,
        required_approvals=required,
        approver_roles=roles,
        environment_name=environment_name,
    )
    if not decision.allowed:
        return {"workflow_id": workflow_id, "status": "blocked", "reason": decision.message or "Policy denied"}

    if decision.required_approvals > 0:
        progress["run_write_attempted"] = True
        try:
            pending = _open_pending_approval_run(
                client=client,
                plan=get_plan_for_org(client, org_id),
                org_id=org_id,
                environment_name=environment_name,
                workflow_id=workflow_id,
                definition=definition,
                parameters=parameters,
                run_hash=run_hash,
                actor_id=actor_id,
                required_approvals=decision.required_approvals,
                approver_roles=decision.approver_roles,
                approval_floor_applied=decision.approval_floor_applied,
                trigger_type=trigger_type,
            )
        except HTTPException as exc:
            return {"workflow_id": workflow_id, "status": "skipped", "reason": str(exc.detail)}
        logger.info("%s_run_pending_approval workflow_id=%s run_id=%s", source, workflow_id, pending["run_id"])
        return {"workflow_id": workflow_id, "run_id": pending["run_id"], "status": pending["status"]}

    progress["run_write_attempted"] = True
    created_run = create_execute_run(
        client=client,
        org_id=org_id,
        workflow_id=workflow_id,
        triggered_by=actor_id,
        definition_snapshot=definition,
        parameters=parameters,
        run_hash=run_hash,
        status="running",
        approval_status="approved",
        required_approvals=0,
        approver_roles=[],
        environment_name=environment_name,
        trigger_type=trigger_type,
    )
    run_id = str(created_run["id"])
    svc = execution_service or get_execution_service()
    try:
        result = await svc.execute_workflow(
            org_id=org_id,
            workflow_id=workflow_id,
            run_id=run_id,
            parameters=parameters,
            user_id=actor_id,
            definition=definition,
            environment_name=environment_name,
        )
        # execute_workflow_steps already finalized the run row.
        return {"workflow_id": workflow_id, "run_id": run_id, "status": result.status}
    except Exception as exc:  # noqa: BLE001
        logger.error("%s_workflow_execution_failed workflow_id=%s run_id=%s error=%s", source, workflow_id, run_id, exc)
        from app.services.trigger_run_finalize import finalize_trigger_exception

        finalize_trigger_exception(
            client,
            org_id=org_id,
            run_id=run_id,
            actor_id=actor_id,
            workflow_id=workflow_id,
            error=str(exc),
            source=source,
        )
        return {"workflow_id": workflow_id, "run_id": run_id, "status": "failed", "error": str(exc)}
