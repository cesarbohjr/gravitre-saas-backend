"""Read-only tenant capability snapshot for frontend consumption."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth.dependencies import get_environment_context, require_org_member
from app.capabilities.registry import tenant_capability_snapshot
from app.config import Settings, get_settings
from app.workflows.repository import get_supabase_client

router = APIRouter(prefix="/api/capabilities", tags=["capabilities"])


@router.get("")
async def get_capabilities(
    member: Annotated[tuple[dict, str, str], Depends(require_org_member)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    _user, org_id, _role = member
    if not org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization context required",
        )
    client = get_supabase_client(settings)
    return tenant_capability_snapshot(
        client,
        org_id,
        environment_name=environment_name,
    )
