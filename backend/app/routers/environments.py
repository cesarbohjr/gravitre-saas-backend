"""Phase 15: Environments API."""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from supabase import create_client

from app.auth.dependencies import get_current_user, get_org_context, require_admin
from app.config import Settings, get_settings
from app.workflows.audit import write_audit_event
from app.billing.service import get_plan_for_org, require_limit

router = APIRouter(prefix="/api/environments", tags=["environments"])


class EnvironmentCreateRequest(BaseModel):
    name: str = Field(..., min_length=1)


class EnvironmentUpdateRequest(BaseModel):
    is_active: bool | None = Field(default=None, alias="isActive")


@router.get("")
async def list_environments(
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    r = client.table("environments").select("id, name, is_active, created_at").eq("org_id", org_id).execute()
    return {"environments": list(r.data or [])}


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_environment(
    body: EnvironmentCreateRequest,
    _admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    _user, org_id = _admin
    name = body.name.strip().lower()
    if name not in {"production", "staging"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid environment name")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    plan = get_plan_for_org(client, org_id)
    count = client.table("environments").select("id", count="exact").eq("org_id", org_id).execute()
    current = count.count or 0 if hasattr(count, "count") else len(count.data or [])
    require_limit(current, plan.get("environments_limit"), "environments")
    r = client.table("environments").insert({"org_id": org_id, "name": name}).execute()
    if not r.data:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Environment create failed")
    env_id = str(r.data[0]["id"])
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=_user["user_id"],
        action="environment.created",
        resource_type="environment",
        resource_id=env_id,
        metadata={"name": name},
    )
    return {"id": env_id, "name": name}


@router.patch("/{env_id}")
async def update_environment(
    env_id: UUID,
    body: EnvironmentUpdateRequest,
    _admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    _user, org_id = _admin
    payload: dict = {}
    if body.is_active is not None:
        payload["is_active"] = body.is_active
    if not payload:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No changes provided")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    updated = client.table("environments").update(payload).eq("org_id", org_id).eq("id", str(env_id)).execute()
    if not updated.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Environment not found")
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=_user["user_id"],
        action="environment.updated",
        resource_type="environment",
        resource_id=str(env_id),
        metadata={"fields": list(payload.keys())},
    )
    return {"id": str(env_id), **payload}
