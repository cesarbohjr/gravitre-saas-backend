"""Department pipeline catalog + org status (Katie-style assembly layer)."""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from supabase import create_client

from app.auth.dependencies import get_current_user, get_org_context, require_admin
from app.config import Settings, get_settings
from app.marketplace.department_pipelines.service import DepartmentPipelineService
from app.services.sync_back_policy_service import save_sync_back_policy
from app.workflows.audit import write_audit_event

router = APIRouter(prefix="/api/department-pipelines", tags=["department-pipelines"])


class SyncBackPolicyUpdate(BaseModel):
    department: str = Field(..., min_length=1)
    sync_timing: str = Field(..., pattern="^(immediate|defer_to_milestone)$")
    defer_milestone_stage_id: str | None = None


def _client(settings: Settings):
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


def _org_settings(client: Any, org_id: str) -> dict[str, Any]:
    row = client.table("organizations").select("settings").eq("id", org_id).limit(1).execute()
    data = (row.data or [{}])[0]
    settings = data.get("settings")
    return settings if isinstance(settings, dict) else {}


@router.get("")
async def list_pipelines(
    current_user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    _ = current_user
    if org_id is None:
        raise HTTPException(status_code=403, detail="Organization context required")
    svc = DepartmentPipelineService()
    return {"pipelines": svc.list_catalog()}


@router.get("/{pipeline_id}")
async def get_pipeline(
    pipeline_id: str,
    current_user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    _ = current_user
    if org_id is None:
        raise HTTPException(status_code=403, detail="Organization context required")
    client = _client(settings)
    org_settings = _org_settings(client, org_id)
    view = DepartmentPipelineService().get_pipeline_view(
        client,
        org_id=org_id,
        pipeline_id=pipeline_id,
        org_settings=org_settings,
    )
    if view is None:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    return {"pipeline": view}


@router.get("/by-department/{department}")
async def get_pipeline_by_department(
    department: str,
    current_user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    _ = current_user
    if org_id is None:
        raise HTTPException(status_code=403, detail="Organization context required")
    client = _client(settings)
    org_settings = _org_settings(client, org_id)
    view = DepartmentPipelineService().get_pipeline_view(
        client,
        org_id=org_id,
        department=department,
        org_settings=org_settings,
    )
    if view is None:
        raise HTTPException(status_code=404, detail="No pipeline for department")
    return {"pipeline": view}


@router.put("/sync-back-policy")
async def update_sync_back_policy(
    body: SyncBackPolicyUpdate,
    current_user: Annotated[dict, Depends(require_admin)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=403, detail="Organization context required")
    client = _client(settings)
    existing = _org_settings(client, org_id)
    updated = save_sync_back_policy(
        existing,
        department=body.department,
        sync_timing=body.sync_timing,  # type: ignore[arg-type]
        defer_milestone_stage_id=body.defer_milestone_stage_id,
    )
    client.table("organizations").update({"settings": updated}).eq("id", org_id).execute()
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=str(current_user.get("user_id") or ""),
        action="department_pipeline.sync_back_policy.updated",
        resource_type="org_settings",
        resource_id=org_id,
        metadata={
            "department": body.department,
            "syncTiming": body.sync_timing,
            "deferMilestoneStageId": body.defer_milestone_stage_id,
        },
    )
    from app.services.sync_back_policy_service import get_sync_back_policy

    return {
        "policy": get_sync_back_policy(updated, department=body.department),
    }
