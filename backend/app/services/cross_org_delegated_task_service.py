"""Cross-org delegated sub-tasks with status sync (STA-118).

Prime contractor (delegator org) assigns work to subcontractor (delegate org).
Delegate accepts, executes, and reports completion; delegator polls for status updates.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.operators import agent_jobs as agent_jobs_mod
from app.services.b2b_handoff_service import get_active_partnership
from app.services.handoff_service import get_agent
from app.workflows.audit import write_audit_event

logger = logging.getLogger(__name__)

AUDIT_TASK_DELEGATED = "federation.task.delegated"
AUDIT_TASK_ACCEPTED = "federation.task.accepted"
AUDIT_TASK_STARTED = "federation.task.started"
AUDIT_TASK_COMPLETED = "federation.task.completed"
AUDIT_TASK_REJECTED = "federation.task.rejected"
AUDIT_TASK_CANCELLED = "federation.task.cancelled"
AUDIT_TASK_FAILED = "federation.task.failed"

TASK_PENDING = "pending_delegate"
TASK_ACCEPTED = "accepted"
TASK_IN_PROGRESS = "in_progress"
TASK_COMPLETED = "completed"
TASK_REJECTED = "rejected"
TASK_CANCELLED = "cancelled"
TASK_FAILED = "failed"

TERMINAL_STATUSES = {TASK_COMPLETED, TASK_REJECTED, TASK_CANCELLED, TASK_FAILED}


class DelegatedTaskError(Exception):
    code = "DELEGATED_TASK_ERROR"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        if code:
            self.code = code


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _serialize_task(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "partnershipId": str(row["partnership_id"]),
        "delegatorOrgId": str(row["delegator_org_id"]),
        "delegateOrgId": str(row["delegate_org_id"]),
        "delegatorAgentId": str(row["delegator_agent_id"]) if row.get("delegator_agent_id") else None,
        "delegateAgentId": str(row["delegate_agent_id"]) if row.get("delegate_agent_id") else None,
        "delegateAgentJobId": str(row["delegate_agent_job_id"]) if row.get("delegate_agent_job_id") else None,
        "title": row["title"],
        "instructions": row.get("instructions"),
        "payload": row.get("payload") or {},
        "parentReference": row.get("parent_reference") or {},
        "status": row["status"],
        "result": row.get("result"),
        "statusMessage": row.get("status_message"),
        "syncVersion": int(row.get("sync_version") or 1),
        "createdAt": row.get("created_at"),
        "updatedAt": row.get("updated_at"),
        "acceptedAt": row.get("accepted_at"),
        "startedAt": row.get("started_at"),
        "completedAt": row.get("completed_at"),
        "rejectedAt": row.get("rejected_at"),
        "cancelledAt": row.get("cancelled_at"),
        "statusSyncedAt": row.get("status_synced_at"),
    }


def _get_task_row(client: Any, task_id: str) -> dict[str, Any] | None:
    result = (
        client.table("cross_org_delegated_tasks")
        .select("*")
        .eq("id", task_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        return None
    return dict(result.data[0])


def _assert_org_on_task(task: dict[str, Any], org_id: str) -> None:
    if org_id not in {str(task["delegator_org_id"]), str(task["delegate_org_id"])}:
        raise DelegatedTaskError("Delegated task not found", code="NOT_FOUND")


def _bump_sync(update: dict[str, Any], current_version: int) -> dict[str, Any]:
    now = _now()
    update["sync_version"] = current_version + 1
    update["updated_at"] = now
    update["status_synced_at"] = now
    return update


def delegate_task_to_partner(
    client: Any,
    *,
    delegator_org_id: str,
    delegate_org_id: str,
    title: str,
    delegator_user_id: str,
    instructions: str | None = None,
    payload: dict[str, Any] | None = None,
    parent_reference: dict[str, Any] | None = None,
    delegator_agent_id: str | None = None,
    delegate_agent_id: str | None = None,
) -> dict[str, Any]:
    if not title.strip():
        raise DelegatedTaskError("Task title is required", code="VALIDATION_ERROR")
    if delegator_org_id == delegate_org_id:
        raise DelegatedTaskError("Cannot delegate a task to the same organization", code="VALIDATION_ERROR")

    partnership = get_active_partnership(client, delegator_org_id, delegate_org_id)
    if not partnership:
        raise DelegatedTaskError(
            "Active B2B partnership required before delegating tasks",
            code="PARTNERSHIP_REQUIRED",
        )

    if delegator_agent_id:
        agent = get_agent(client, delegator_org_id, delegator_agent_id)
        if not agent:
            raise DelegatedTaskError("Delegator agent not found in your organization", code="NOT_FOUND")
    if delegate_agent_id:
        agent = get_agent(client, delegate_org_id, delegate_agent_id)
        if not agent:
            raise DelegatedTaskError("Delegate agent not found in partner organization", code="NOT_FOUND")

    row = {
        "partnership_id": str(partnership["id"]),
        "delegator_org_id": delegator_org_id,
        "delegate_org_id": delegate_org_id,
        "delegator_agent_id": delegator_agent_id,
        "delegate_agent_id": delegate_agent_id,
        "title": title.strip(),
        "instructions": instructions,
        "payload": payload or {},
        "parent_reference": parent_reference or {},
        "status": TASK_PENDING,
        "delegator_user_id": delegator_user_id,
    }
    result = client.table("cross_org_delegated_tasks").insert(row).execute()
    if not result.data:
        raise RuntimeError("cross_org_delegated_tasks insert returned no row")
    task = dict(result.data[0])
    write_audit_event(
        client,
        org_id=delegator_org_id,
        actor_id=delegator_user_id,
        action=AUDIT_TASK_DELEGATED,
        resource_type="cross_org_delegated_task",
        resource_id=str(task["id"]),
        metadata={
            "delegateOrgId": delegate_org_id,
            "title": title.strip(),
        },
    )
    logger.info(
        "delegated_task_created delegator_org=%s delegate_org=%s task_id=%s",
        delegator_org_id,
        delegate_org_id,
        task["id"],
    )
    return _serialize_task(task)


def list_delegated_tasks(
    client: Any,
    org_id: str,
    *,
    direction: str = "all",
    status: str | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if direction in {"all", "outbound"}:
        query = (
            client.table("cross_org_delegated_tasks")
            .select("*")
            .eq("delegator_org_id", org_id)
            .order("created_at", desc=True)
        )
        if status:
            query = query.eq("status", status)
        rows.extend(dict(row) for row in (query.execute().data or []))
    if direction in {"all", "inbound"}:
        query = (
            client.table("cross_org_delegated_tasks")
            .select("*")
            .eq("delegate_org_id", org_id)
            .order("created_at", desc=True)
        )
        if status:
            query = query.eq("status", status)
        rows.extend(dict(row) for row in (query.execute().data or []))
    deduped = {str(row["id"]): row for row in rows}
    return [_serialize_task(row) for row in deduped.values()]


def get_delegated_task(client: Any, org_id: str, task_id: str) -> dict[str, Any]:
    task = _get_task_row(client, task_id)
    if not task:
        raise DelegatedTaskError("Delegated task not found", code="NOT_FOUND")
    _assert_org_on_task(task, org_id)
    return _serialize_task(task)


def accept_delegated_task(
    client: Any,
    *,
    org_id: str,
    task_id: str,
    actor_id: str,
    delegate_agent_id: str | None = None,
    spawn_agent_job: bool = False,
) -> dict[str, Any]:
    task = _get_task_row(client, task_id)
    if not task:
        raise DelegatedTaskError("Delegated task not found", code="NOT_FOUND")
    if str(task["delegate_org_id"]) != org_id:
        raise DelegatedTaskError("Only the delegate organization can accept this task", code="FORBIDDEN")
    if task["status"] != TASK_PENDING:
        raise DelegatedTaskError(f"Task is not pending (status={task['status']})", code="CONFLICT")

    agent_id = delegate_agent_id or task.get("delegate_agent_id")
    if agent_id:
        agent = get_agent(client, org_id, str(agent_id))
        if not agent:
            raise DelegatedTaskError("Delegate agent not found in your organization", code="NOT_FOUND")

    delegate_job_id: str | None = None
    if spawn_agent_job and agent_id:
        job = agent_jobs_mod.create_job(
            client,
            org_id,
            kind="delegated_task",
            payload={
                "delegatedTaskId": task_id,
                "title": task["title"],
                "instructions": task.get("instructions"),
                "payload": task.get("payload") or {},
                "delegatorOrgId": str(task["delegator_org_id"]),
            },
            created_by=actor_id,
        )
        delegate_job_id = str(job["id"])

    update = _bump_sync(
        {
            "status": TASK_ACCEPTED,
            "delegate_user_id": actor_id,
            "accepted_at": _now(),
            "delegate_agent_id": agent_id,
            "delegate_agent_job_id": delegate_job_id,
        },
        int(task.get("sync_version") or 1),
    )
    updated = (
        client.table("cross_org_delegated_tasks")
        .update(update)
        .eq("id", task_id)
        .execute()
    )
    row = dict((updated.data or [task])[0])
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=actor_id,
        action=AUDIT_TASK_ACCEPTED,
        resource_type="cross_org_delegated_task",
        resource_id=task_id,
        metadata={"delegatorOrgId": str(task["delegator_org_id"])},
    )
    return _serialize_task(row)


def reject_delegated_task(
    client: Any,
    *,
    org_id: str,
    task_id: str,
    actor_id: str,
    reason: str | None = None,
) -> dict[str, Any]:
    task = _get_task_row(client, task_id)
    if not task:
        raise DelegatedTaskError("Delegated task not found", code="NOT_FOUND")
    if str(task["delegate_org_id"]) != org_id:
        raise DelegatedTaskError("Only the delegate organization can reject this task", code="FORBIDDEN")
    if task["status"] != TASK_PENDING:
        raise DelegatedTaskError(f"Task is not pending (status={task['status']})", code="CONFLICT")

    update = _bump_sync(
        {
            "status": TASK_REJECTED,
            "delegate_user_id": actor_id,
            "status_message": reason,
            "rejected_at": _now(),
        },
        int(task.get("sync_version") or 1),
    )
    updated = (
        client.table("cross_org_delegated_tasks")
        .update(update)
        .eq("id", task_id)
        .execute()
    )
    row = dict((updated.data or [task])[0])
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=actor_id,
        action=AUDIT_TASK_REJECTED,
        resource_type="cross_org_delegated_task",
        resource_id=task_id,
        metadata={"reason": reason},
    )
    return _serialize_task(row)


def start_delegated_task(
    client: Any,
    *,
    org_id: str,
    task_id: str,
    actor_id: str,
) -> dict[str, Any]:
    task = _get_task_row(client, task_id)
    if not task:
        raise DelegatedTaskError("Delegated task not found", code="NOT_FOUND")
    if str(task["delegate_org_id"]) != org_id:
        raise DelegatedTaskError("Only the delegate organization can start this task", code="FORBIDDEN")
    if task["status"] not in {TASK_ACCEPTED, TASK_IN_PROGRESS}:
        raise DelegatedTaskError("Task must be accepted before starting work", code="CONFLICT")

    update = _bump_sync(
        {
            "status": TASK_IN_PROGRESS,
            "delegate_user_id": actor_id,
            "started_at": task.get("started_at") or _now(),
        },
        int(task.get("sync_version") or 1),
    )
    updated = (
        client.table("cross_org_delegated_tasks")
        .update(update)
        .eq("id", task_id)
        .execute()
    )
    row = dict((updated.data or [task])[0])
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=actor_id,
        action=AUDIT_TASK_STARTED,
        resource_type="cross_org_delegated_task",
        resource_id=task_id,
        metadata={},
    )
    return _serialize_task(row)


def complete_delegated_task(
    client: Any,
    *,
    org_id: str,
    task_id: str,
    actor_id: str,
    result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    task = _get_task_row(client, task_id)
    if not task:
        raise DelegatedTaskError("Delegated task not found", code="NOT_FOUND")
    if str(task["delegate_org_id"]) != org_id:
        raise DelegatedTaskError("Only the delegate organization can complete this task", code="FORBIDDEN")
    if task["status"] not in {TASK_ACCEPTED, TASK_IN_PROGRESS}:
        raise DelegatedTaskError("Task must be accepted or in progress before completion", code="CONFLICT")

    update = _bump_sync(
        {
            "status": TASK_COMPLETED,
            "delegate_user_id": actor_id,
            "result": result or {},
            "completed_at": _now(),
        },
        int(task.get("sync_version") or 1),
    )
    updated = (
        client.table("cross_org_delegated_tasks")
        .update(update)
        .eq("id", task_id)
        .execute()
    )
    row = dict((updated.data or [task])[0])
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=actor_id,
        action=AUDIT_TASK_COMPLETED,
        resource_type="cross_org_delegated_task",
        resource_id=task_id,
        metadata={"delegatorOrgId": str(task["delegator_org_id"])},
    )
    write_audit_event(
        client,
        org_id=str(task["delegator_org_id"]),
        actor_id=actor_id,
        action=AUDIT_TASK_COMPLETED,
        resource_type="cross_org_delegated_task",
        resource_id=task_id,
        metadata={"delegateOrgId": org_id, "syncVersion": row.get("sync_version")},
    )
    return _serialize_task(row)


def fail_delegated_task(
    client: Any,
    *,
    org_id: str,
    task_id: str,
    actor_id: str,
    reason: str | None = None,
) -> dict[str, Any]:
    task = _get_task_row(client, task_id)
    if not task:
        raise DelegatedTaskError("Delegated task not found", code="NOT_FOUND")
    if str(task["delegate_org_id"]) != org_id:
        raise DelegatedTaskError("Only the delegate organization can fail this task", code="FORBIDDEN")
    if task["status"] in TERMINAL_STATUSES:
        raise DelegatedTaskError(f"Task is already terminal (status={task['status']})", code="CONFLICT")
    if task["status"] == TASK_PENDING:
        raise DelegatedTaskError("Accept or reject pending tasks before marking failed", code="CONFLICT")

    update = _bump_sync(
        {
            "status": TASK_FAILED,
            "delegate_user_id": actor_id,
            "status_message": reason,
            "completed_at": _now(),
        },
        int(task.get("sync_version") or 1),
    )
    updated = (
        client.table("cross_org_delegated_tasks")
        .update(update)
        .eq("id", task_id)
        .execute()
    )
    row = dict((updated.data or [task])[0])
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=actor_id,
        action=AUDIT_TASK_FAILED,
        resource_type="cross_org_delegated_task",
        resource_id=task_id,
        metadata={"reason": reason},
    )
    return _serialize_task(row)


def cancel_delegated_task(
    client: Any,
    *,
    org_id: str,
    task_id: str,
    actor_id: str,
    reason: str | None = None,
) -> dict[str, Any]:
    task = _get_task_row(client, task_id)
    if not task:
        raise DelegatedTaskError("Delegated task not found", code="NOT_FOUND")
    if str(task["delegator_org_id"]) != org_id:
        raise DelegatedTaskError("Only the delegator organization can cancel this task", code="FORBIDDEN")
    if task["status"] in TERMINAL_STATUSES:
        raise DelegatedTaskError(f"Task is already terminal (status={task['status']})", code="CONFLICT")
    if task["status"] == TASK_IN_PROGRESS:
        raise DelegatedTaskError("Cannot cancel a task that is in progress", code="CONFLICT")

    update = _bump_sync(
        {
            "status": TASK_CANCELLED,
            "status_message": reason,
            "cancelled_at": _now(),
        },
        int(task.get("sync_version") or 1),
    )
    updated = (
        client.table("cross_org_delegated_tasks")
        .update(update)
        .eq("id", task_id)
        .execute()
    )
    row = dict((updated.data or [task])[0])
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=actor_id,
        action=AUDIT_TASK_CANCELLED,
        resource_type="cross_org_delegated_task",
        resource_id=task_id,
        metadata={"reason": reason},
    )
    return _serialize_task(row)
