"""Phase 15: Settings API."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from supabase import create_client

from app.auth.dependencies import get_current_user, get_org_context, require_admin
from app.config import Settings, get_settings
from app.workflows.audit import write_audit_event

router = APIRouter(prefix="/api/settings", tags=["settings"])


class SettingsUpdateRequest(BaseModel):
    settings: dict


@router.get("")
async def get_settings_route(
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=403, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    r = client.table("organizations").select("id, settings").eq("id", org_id).limit(1).execute()
    if not r.data:
        raise HTTPException(status_code=404, detail="Organization not found")
    return {"settings": r.data[0].get("settings") or {}}


@router.patch("")
async def update_settings_route(
    body: SettingsUpdateRequest,
    _admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    _user, org_id = _admin
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    updated = client.table("organizations").update({"settings": body.settings}).eq("id", org_id).execute()
    if not updated.data:
        raise HTTPException(status_code=404, detail="Organization not found")
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=_user["user_id"],
        action="settings.updated",
        resource_type="org_settings",
        resource_id=str(org_id),
        metadata={},
    )
    return {"settings": body.settings}
