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
) -> dict[str, Any]:
    """Return ``{workflow_id, run_id?, status, error?, reason?}`` for one triggered run."""
    from fastapi import HTTPException

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
