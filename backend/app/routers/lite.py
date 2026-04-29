"""Lite mode APIs for department users."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Response, status
from supabase import create_client

from app.auth.dependencies import get_current_user, get_org_context
from app.config import Settings, get_settings

router = APIRouter(prefix="/api/lite", tags=["lite"])


def _is_missing_table_error(error: Exception | None) -> bool:
    if error is None:
        return False
    return "does not exist" in str(error).lower()


def _lite_status(run_status: str | None) -> str:
    status_value = (run_status or "").lower()
    if status_value in {"running"}:
        return "processing"
    if status_value in {"completed"}:
        return "completed"
    if status_value in {"failed", "cancelled", "rejected"}:
        return "failed"
    return "pending"


def _lite_progress(run_status: str | None) -> int:
    mapped = _lite_status(run_status)
    if mapped == "completed":
        return 100
    if mapped == "failed":
        return 100
    if mapped == "processing":
        return 55
    return 10


def _extract_required_inputs(definition: dict[str, Any] | None) -> list[str]:
    if not isinstance(definition, dict):
        return []
    steps = definition.get("steps")
    if not isinstance(steps, list):
        return []
    keys: list[str] = []
    for step in steps:
        if not isinstance(step, dict):
            continue
        inputs = step.get("inputs")
        if isinstance(inputs, list):
            for item in inputs:
                if isinstance(item, str) and item and item not in keys:
                    keys.append(item)
                elif isinstance(item, dict):
                    key = item.get("key") or item.get("name")
                    if isinstance(key, str) and key and key not in keys:
                        keys.append(key)
    return keys


def _build_input_summary(parameters: dict[str, Any] | None) -> str | None:
    if not isinstance(parameters, dict):
        return None
    notes = parameters.get("notes")
    if isinstance(notes, str) and notes.strip():
        return notes.strip()[:200]
    inputs = parameters.get("inputs")
    if isinstance(inputs, dict) and inputs:
        parts = []
        for key, value in list(inputs.items())[:3]:
            parts.append(f"{key}: {value}")
        return "; ".join(parts)[:200]
    return None


def _build_task_out(row: dict[str, Any], workflow_name: str | None) -> dict[str, Any]:
    return {
        "id": str(row.get("id") or ""),
        "workflow_id": str(row.get("workflow_id") or ""),
        "workflow_name": workflow_name or "Workflow",
        "status": _lite_status(row.get("status")),
        "progress": _lite_progress(row.get("status")),
        "input_summary": _build_input_summary(row.get("parameters")),
        "created_at": row.get("created_at"),
        "completed_at": row.get("completed_at"),
        "error": row.get("error_message"),
    }


def _deliverable_from_run(run: dict[str, Any], workflow_name: str | None) -> dict[str, Any]:
    run_id = str(run.get("id") or "")
    payload = {
        "run_id": run_id,
        "workflow_id": str(run.get("workflow_id") or ""),
        "workflow_name": workflow_name or "Workflow",
        "parameters": run.get("parameters") or {},
        "status": run.get("status"),
        "created_at": run.get("created_at"),
        "completed_at": run.get("completed_at"),
        "error_message": run.get("error_message"),
    }
    serialized = json.dumps(payload, default=str)
    return {
        "id": f"dl_{run_id}",
        "task_id": run_id,
        "task_name": workflow_name or "Workflow output",
        "name": f"{(workflow_name or 'workflow').replace(' ', '_').lower()}_output_{run_id[:8]}.json",
        "type": "application/json",
        "size_bytes": len(serialized.encode("utf-8")),
        "download_url": f"/api/lite/deliverables/dl_{run_id}/download",
        "preview_url": f"/lite/tasks?task={run_id}",
        "created_at": run.get("completed_at") or run.get("created_at"),
    }


@router.get("/home")
async def get_lite_home(
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    user_id = _user["user_id"]
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)

    runs_resp = (
        client.table("workflow_runs")
        .select("id, workflow_id, status, parameters, created_at, completed_at, error_message")
        .eq("org_id", org_id)
        .eq("triggered_by", user_id)
        .eq("run_type", "execute")
        .order("created_at", desc=True)
        .limit(20)
        .execute()
    )
    if _is_missing_table_error(runs_resp.error):
        return {
            "recent_tasks": [],
            "pending_deliverables": [],
            "quick_actions": [],
            "stats": {"tasks_this_week": 0, "completed_this_week": 0, "pending_deliverables": 0},
        }
    if runs_resp.error:
        raise HTTPException(status_code=500, detail=str(runs_resp.error))
    runs = list(runs_resp.data or [])

    workflow_ids = list({str(row.get("workflow_id")) for row in runs if row.get("workflow_id")})
    workflow_names: dict[str, str] = {}
    workflows: list[dict[str, Any]] = []
    if workflow_ids:
        wf_resp = (
            client.table("workflow_defs")
            .select("id, name, description")
            .eq("org_id", org_id)
            .in_("id", workflow_ids)
            .execute()
        )
        if wf_resp.error and not _is_missing_table_error(wf_resp.error):
            raise HTTPException(status_code=500, detail=str(wf_resp.error))
        workflows = list(wf_resp.data or [])
        workflow_names = {str(row.get("id")): row.get("name") or "Workflow" for row in workflows}

    recent_tasks = [
        _build_task_out(row, workflow_names.get(str(row.get("workflow_id"))))
        for row in runs[:6]
    ]

    completed_runs = [row for row in runs if row.get("status") == "completed"]
    pending_deliverables = [
        _deliverable_from_run(row, workflow_names.get(str(row.get("workflow_id"))))
        for row in completed_runs[:6]
    ]

    since = datetime.now(timezone.utc) - timedelta(days=7)
    tasks_this_week = 0
    completed_this_week = 0
    for row in runs:
        created_raw = row.get("created_at")
        if not created_raw:
            continue
        try:
            created_dt = datetime.fromisoformat(str(created_raw).replace("Z", "+00:00"))
        except ValueError:
            continue
        if created_dt >= since:
            tasks_this_week += 1
            if row.get("status") == "completed":
                completed_this_week += 1

    quick_actions = [
        {
            "id": str(row.get("id")),
            "name": row.get("name") or "Workflow",
            "description": row.get("description"),
            "workflow_id": str(row.get("id")),
            "icon": "sparkles",
        }
        for row in workflows[:6]
    ]

    return {
        "recent_tasks": recent_tasks,
        "pending_deliverables": pending_deliverables,
        "quick_actions": quick_actions,
        "stats": {
            "tasks_this_week": tasks_this_week,
            "completed_this_week": completed_this_week,
            "pending_deliverables": len(pending_deliverables),
        },
    }


@router.get("/workflows")
async def get_lite_workflows(
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    response = (
        client.table("workflow_defs")
        .select("id, name, description, definition")
        .eq("org_id", org_id)
        .order("updated_at", desc=True)
        .limit(100)
        .execute()
    )
    if _is_missing_table_error(response.error):
        return {"workflows": []}
    if response.error:
        raise HTTPException(status_code=500, detail=str(response.error))
    return {
        "workflows": [
            {
                "id": str(row.get("id")),
                "name": row.get("name") or "Workflow",
                "description": row.get("description"),
                "required_inputs": _extract_required_inputs(row.get("definition")),
            }
            for row in (response.data or [])
        ]
    }


@router.post("/assign")
async def assign_lite_work(
    payload: Annotated[dict, Body(...)],
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    workflow_id = str(payload.get("workflow_id") or "").strip()
    if not workflow_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="workflow_id is required")

    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    wf_resp = (
        client.table("workflow_defs")
        .select("id, definition")
        .eq("org_id", org_id)
        .eq("id", workflow_id)
        .limit(1)
        .execute()
    )
    if wf_resp.error:
        raise HTTPException(status_code=500, detail=str(wf_resp.error))
    if not wf_resp.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")

    definition = wf_resp.data[0].get("definition") or {}
    now_iso = datetime.now(timezone.utc).isoformat()
    run_hash = hashlib.sha256(
        f"{org_id}:{workflow_id}:{_user['user_id']}:{now_iso}".encode("utf-8")
    ).hexdigest()

    insert_payload = {
        "org_id": org_id,
        "workflow_id": workflow_id,
        "run_type": "execute",
        "status": "running",
        "triggered_by": _user["user_id"],
        "definition_snapshot": definition,
        "parameters": {
            "inputs": payload.get("inputs") or {},
            "notes": payload.get("notes"),
            "lite_mode": True,
        },
        "run_hash": run_hash,
        "environment": "production",
        "trigger_type": "manual",
        "started_at": now_iso,
    }
    insert_resp = client.table("workflow_runs").insert(insert_payload).execute()
    if insert_resp.error:
        raise HTTPException(status_code=500, detail=str(insert_resp.error))
    if not insert_resp.data:
        raise HTTPException(status_code=500, detail="Failed to create task")
    return {"task_id": str(insert_resp.data[0].get("id"))}


@router.get("/tasks")
async def list_lite_tasks(
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
    status_filter: str | None = Query(default=None, alias="status"),
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    user_id = _user["user_id"]
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)

    response = (
        client.table("workflow_runs")
        .select("id, workflow_id, status, parameters, created_at, completed_at, error_message")
        .eq("org_id", org_id)
        .eq("triggered_by", user_id)
        .eq("run_type", "execute")
        .order("created_at", desc=True)
        .limit(200)
        .execute()
    )
    if _is_missing_table_error(response.error):
        return {"tasks": []}
    if response.error:
        raise HTTPException(status_code=500, detail=str(response.error))
    rows = list(response.data or [])

    workflow_ids = list({str(row.get("workflow_id")) for row in rows if row.get("workflow_id")})
    workflow_names: dict[str, str] = {}
    if workflow_ids:
        wf_resp = (
            client.table("workflow_defs")
            .select("id, name")
            .eq("org_id", org_id)
            .in_("id", workflow_ids)
            .execute()
        )
        if wf_resp.error and not _is_missing_table_error(wf_resp.error):
            raise HTTPException(status_code=500, detail=str(wf_resp.error))
        workflow_names = {
            str(row.get("id")): row.get("name") or "Workflow"
            for row in (wf_resp.data or [])
        }

    tasks = [
        _build_task_out(row, workflow_names.get(str(row.get("workflow_id"))))
        for row in rows
    ]
    if status_filter:
        tasks = [task for task in tasks if task["status"] == status_filter]
    return {"tasks": tasks}


@router.get("/tasks/{task_id}")
async def get_lite_task(
    task_id: str,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    user_id = _user["user_id"]
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)

    response = (
        client.table("workflow_runs")
        .select("id, workflow_id, status, parameters, created_at, completed_at, error_message")
        .eq("org_id", org_id)
        .eq("triggered_by", user_id)
        .eq("run_type", "execute")
        .eq("id", task_id)
        .limit(1)
        .execute()
    )
    if response.error:
        raise HTTPException(status_code=500, detail=str(response.error))
    if not response.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    row = response.data[0]

    workflow_name = "Workflow"
    workflow_id = row.get("workflow_id")
    if workflow_id:
        wf_resp = (
            client.table("workflow_defs")
            .select("name")
            .eq("org_id", org_id)
            .eq("id", str(workflow_id))
            .limit(1)
            .execute()
        )
        if not wf_resp.error and wf_resp.data:
            workflow_name = wf_resp.data[0].get("name") or workflow_name

    return _build_task_out(row, workflow_name)


@router.post("/tasks/{task_id}/cancel")
async def cancel_lite_task(
    task_id: str,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    user_id = _user["user_id"]
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)

    check = (
        client.table("workflow_runs")
        .select("id, status")
        .eq("org_id", org_id)
        .eq("triggered_by", user_id)
        .eq("run_type", "execute")
        .eq("id", task_id)
        .limit(1)
        .execute()
    )
    if check.error:
        raise HTTPException(status_code=500, detail=str(check.error))
    if not check.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    update = (
        client.table("workflow_runs")
        .update({"status": "failed", "error_message": "Cancelled by user"})
        .eq("org_id", org_id)
        .eq("triggered_by", user_id)
        .eq("id", task_id)
        .execute()
    )
    if update.error:
        raise HTTPException(status_code=500, detail=str(update.error))
    return {"ok": True}


@router.get("/deliverables")
async def list_lite_deliverables(
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    user_id = _user["user_id"]
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)

    response = (
        client.table("workflow_runs")
        .select("id, workflow_id, status, parameters, created_at, completed_at, error_message")
        .eq("org_id", org_id)
        .eq("triggered_by", user_id)
        .eq("run_type", "execute")
        .eq("status", "completed")
        .order("completed_at", desc=True)
        .limit(200)
        .execute()
    )
    if _is_missing_table_error(response.error):
        return {"deliverables": []}
    if response.error:
        raise HTTPException(status_code=500, detail=str(response.error))
    rows = list(response.data or [])

    workflow_ids = list({str(row.get("workflow_id")) for row in rows if row.get("workflow_id")})
    workflow_names: dict[str, str] = {}
    if workflow_ids:
        wf_resp = (
            client.table("workflow_defs")
            .select("id, name")
            .eq("org_id", org_id)
            .in_("id", workflow_ids)
            .execute()
        )
        if wf_resp.error and not _is_missing_table_error(wf_resp.error):
            raise HTTPException(status_code=500, detail=str(wf_resp.error))
        workflow_names = {
            str(row.get("id")): row.get("name") or "Workflow"
            for row in (wf_resp.data or [])
        }

    return {
        "deliverables": [
            _deliverable_from_run(row, workflow_names.get(str(row.get("workflow_id"))))
            for row in rows
        ]
    }


@router.get("/deliverables/{deliverable_id}/download")
async def download_lite_deliverable(
    deliverable_id: str,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    user_id = _user["user_id"]
    if not deliverable_id.startswith("dl_"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deliverable not found")
    run_id = deliverable_id.replace("dl_", "", 1)

    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    run_resp = (
        client.table("workflow_runs")
        .select("id, workflow_id, status, parameters, created_at, completed_at, error_message")
        .eq("org_id", org_id)
        .eq("triggered_by", user_id)
        .eq("id", run_id)
        .eq("run_type", "execute")
        .limit(1)
        .execute()
    )
    if run_resp.error:
        raise HTTPException(status_code=500, detail=str(run_resp.error))
    if not run_resp.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deliverable not found")
    run = run_resp.data[0]

    workflow_name = "workflow"
    workflow_id = run.get("workflow_id")
    if workflow_id:
        wf_resp = (
            client.table("workflow_defs")
            .select("name")
            .eq("org_id", org_id)
            .eq("id", str(workflow_id))
            .limit(1)
            .execute()
        )
        if not wf_resp.error and wf_resp.data:
            workflow_name = (wf_resp.data[0].get("name") or "workflow").strip() or "workflow"

    payload = {
        "task_id": run_id,
        "workflow_id": str(run.get("workflow_id") or ""),
        "workflow_name": workflow_name,
        "status": run.get("status"),
        "parameters": run.get("parameters") or {},
        "created_at": run.get("created_at"),
        "completed_at": run.get("completed_at"),
        "error": run.get("error_message"),
    }
    body = json.dumps(payload, indent=2, default=str)
    filename = f"{workflow_name.replace(' ', '_').lower()}_{run_id[:8]}.json"
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Content-Type": "application/json",
    }
    return Response(content=body, headers=headers, media_type="application/json")


@router.get("/results")
async def get_lite_results(
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
    range: str | None = Query(default="30d"),
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    user_id = _user["user_id"]
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)

    range_value = (range or "30d").lower().strip()
    days_map = {"7d": 7, "30d": 30, "90d": 90}
    days = days_map.get(range_value, 30)
    since = datetime.now(timezone.utc) - timedelta(days=days)

    response = (
        client.table("workflow_runs")
        .select("id, workflow_id, status, parameters, created_at, completed_at, duration_ms, error_message")
        .eq("org_id", org_id)
        .eq("triggered_by", user_id)
        .eq("run_type", "execute")
        .gte("created_at", since.isoformat())
        .order("created_at", desc=True)
        .limit(500)
        .execute()
    )
    if _is_missing_table_error(response.error):
        return {
            "summary": {
                "period": range_value,
                "tasks_completed": 0,
                "success_rate": 0,
                "avg_completion_time_hours": 0,
                "by_workflow": [],
            },
            "recent": [],
        }
    if response.error:
        raise HTTPException(status_code=500, detail=str(response.error))
    rows = list(response.data or [])

    workflow_ids = list({str(row.get("workflow_id")) for row in rows if row.get("workflow_id")})
    workflow_names: dict[str, str] = {}
    if workflow_ids:
        wf_resp = (
            client.table("workflow_defs")
            .select("id, name")
            .eq("org_id", org_id)
            .in_("id", workflow_ids)
            .execute()
        )
        if wf_resp.error and not _is_missing_table_error(wf_resp.error):
            raise HTTPException(status_code=500, detail=str(wf_resp.error))
        workflow_names = {
            str(row.get("id")): row.get("name") or "Workflow"
            for row in (wf_resp.data or [])
        }

    completed = [row for row in rows if row.get("status") == "completed"]
    total = len(rows)
    success_rate = round((len(completed) / total) * 100, 2) if total > 0 else 0

    completed_with_duration = [
        int(row.get("duration_ms") or 0)
        for row in completed
        if int(row.get("duration_ms") or 0) > 0
    ]
    avg_hours = (
        round((sum(completed_with_duration) / len(completed_with_duration)) / 3600000, 2)
        if completed_with_duration
        else 0
    )

    by_workflow_map: dict[str, int] = {}
    for row in completed:
        workflow_name = workflow_names.get(str(row.get("workflow_id")), "Workflow")
        by_workflow_map[workflow_name] = by_workflow_map.get(workflow_name, 0) + 1
    by_workflow = [
        {"workflow_name": name, "count": count}
        for name, count in sorted(by_workflow_map.items(), key=lambda item: item[1], reverse=True)
    ]

    recent = [
        _build_task_out(row, workflow_names.get(str(row.get("workflow_id"))))
        for row in rows[:20]
    ]
    return {
        "summary": {
            "period": range_value,
            "tasks_completed": len(completed),
            "success_rate": success_rate,
            "avg_completion_time_hours": avg_hours,
            "by_workflow": by_workflow,
        },
        "recent": recent,
    }
