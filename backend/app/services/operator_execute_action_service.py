"""Execute operator suggested actions from /ai Execute mode."""
from __future__ import annotations

import re
from typing import Any

from supabase import Client

from app.core.supabase_response import response_error


def _pick_workflow_id(client: Client, org_id: str, title: str, description: str) -> str | None:
    haystack = f"{title} {description}".lower()
    response = (
        client.table("workflow_defs")
        .select("id, name, description")
        .eq("org_id", org_id)
        .order("updated_at", desc=True)
        .limit(50)
        .execute()
    )
    for row in response.data or []:
        name = str(row.get("name") or "").lower()
        if name and name in haystack:
            return str(row.get("id"))
    for row in response.data or []:
        if re.search(r"\b(workflow|sync|remediation|fix)\b", haystack):
            return str(row.get("id"))
    first = (response.data or [None])[0]
    return str(first.get("id")) if first and first.get("id") else None


def _pick_connector(client: Client, org_id: str, environment: str, hint: str) -> dict[str, Any] | None:
    response = (
        client.table("connectors")
        .select("id, type, vendor, status")
        .eq("org_id", org_id)
        .eq("environment", environment)
        .execute()
    )
    rows = list(response.data or [])
    hint_lower = hint.lower()
    for row in rows:
        vendor = str(row.get("type") or row.get("vendor") or "").lower()
        status = str(row.get("status") or "").lower()
        if status not in {"connected", "healthy", "active"}:
            continue
        if vendor and vendor in hint_lower:
            return row
    for row in rows:
        status = str(row.get("status") or "").lower()
        if status in {"connected", "healthy", "active"}:
            return row
    return None


def _run_workflow(
    client: Client,
    org_id: str,
    user_id: str,
    environment: str,
    workflow_id: str,
    parameters: dict[str, Any] | None = None,
    *,
    settings: Any = None,
) -> dict[str, Any]:
    """Start the workflow through the canonical run path (policy, approvals, queue).

    This used to insert a bare ``workflow_runs`` row and call the step runner
    directly, which skipped ``resolve_policy`` and the approval decision (and
    raised TypeError on both calls). An operator suggestion is a UI entry
    surface, not its own execution engine, so it now starts the same run a
    manual, scheduled or Play-triggered execution would.
    """
    from fastapi import HTTPException

    from app.config import get_settings
    from app.routers.workflows import _execute_workflow_with_context

    try:
        result = _execute_workflow_with_context(
            client=client,
            settings=settings or get_settings(),
            org_id=org_id,
            environment_name=environment,
            workflow_id=workflow_id,
            parameters=parameters or {},
            actor_id=user_id,
            trigger_type="manual",
        )
    except HTTPException as exc:
        raise ValueError(str(exc.detail)) from exc
    run_id = str(result.get("run_id") or "")
    run_status = str(result.get("status") or "")
    pending = run_status == "pending_approval"
    return {
        "success": True,
        "message": "Workflow run is waiting for approval." if pending else "Workflow run started.",
        "entityType": "workflow_run",
        "entityId": run_id,
        "status": run_status,
        "url": f"/workflows/runs/{run_id}",
    }


def execute_operator_action(
    *,
    client: Client,
    org_id: str,
    user_id: str,
    environment: str,
    payload: dict[str, Any],
    settings: Any = None,
) -> dict[str, Any]:
    action_type = str(payload.get("action_type") or "immediate").lower()
    title = str(payload.get("title") or "Suggested action")
    description = str(payload.get("description") or title)
    job_result = payload.get("job_result") if isinstance(payload.get("job_result"), dict) else {}
    combined = f"{title} {description} {job_result.get('action_title', '')} {job_result.get('action_description', '')}"

    if action_type in {"auto_fix", "immediate", "requires-approval"}:
        workflow_id = str(job_result.get("workflow_id") or "").strip() or _pick_workflow_id(
            client, org_id, title, combined
        )
        if workflow_id:
            return _run_workflow(
                client,
                org_id,
                user_id,
                environment,
                workflow_id,
                {"source": "operator_execute_action", "action_title": title},
                settings=settings,
            )

    if action_type == "scheduled" or "schedule" in combined.lower():
        workflow_id = _pick_workflow_id(client, org_id, title, combined)
        if workflow_id:
            # Bug fix (2026-09-12): same two stacked bugs as _run_workflow
            # above — no .select()/.single() on .insert()'s return type, and
            # no .error attribute on APIResponse in this postgrest-py
            # version. See response_error() import/usage above.
            schedule_resp = (
                client.table("workflow_schedules")
                .insert(
                    {
                        "org_id": org_id,
                        "workflow_id": workflow_id,
                        "cron_expression": "0 2 * * *",
                        "enabled": True,
                        "environment": environment,
                    }
                )
                .execute()
            )
            if not response_error(schedule_resp) and schedule_resp.data:
                schedule_id = str(schedule_resp.data[0].get("id"))
                return {
                    "success": True,
                    "message": "Workflow scheduled for nightly execution.",
                    "entityType": "workflow_schedule",
                    "entityId": schedule_id,
                    "url": f"/workflows/{workflow_id}",
                }

    if "sync" in combined.lower():
        connector = _pick_connector(client, org_id, environment, combined)
        if connector:
            connector_id = str(connector.get("id"))
            return {
                "success": True,
                "message": f"Connector sync queued for {connector.get('type') or connector.get('vendor')}.",
                "entityType": "connector",
                "entityId": connector_id,
                "url": f"/connectors/{connector_id}",
            }

    from app.operators import agent_jobs as jobs_module

    job = jobs_module.create_job(
        client,
        org_id,
        kind="operator_task",
        environment=environment,
        payload={
            "task": description or title,
            "context": {"source": "execute_action", "parent_job_id": payload.get("source_job_id")},
        },
        created_by=user_id,
    )
    job_id = str(job.get("id") or "")
    return {
        "success": True,
        "message": "Follow-up operator task queued.",
        "entityType": "agent_job",
        "entityId": job_id,
        "url": f"/assignments/{job_id}" if job_id else "/assignments",
    }
