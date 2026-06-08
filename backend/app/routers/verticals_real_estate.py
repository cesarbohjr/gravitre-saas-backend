"""Real estate vertical pack API (STA-115)."""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from supabase import create_client

from app.auth.dependencies import get_current_user, get_org_context, require_admin
from app.config import Settings, get_settings
from app.services.real_estate_vertical_service import (
    get_real_estate_vertical_status,
    install_real_estate_vertical_pack,
)

router = APIRouter(prefix="/api/verticals/real-estate", tags=["verticals"])


@router.get("")
async def get_real_estate_vertical(
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    if org_id is None:
        raise HTTPException(status_code=403, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    return get_real_estate_vertical_status(client, org_id)


@router.post("/install")
async def install_real_estate_vertical(
    admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    user, org_id = admin
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    return install_real_estate_vertical_pack(
        client,
        org_id,
        actor_id=user["user_id"],
    )
