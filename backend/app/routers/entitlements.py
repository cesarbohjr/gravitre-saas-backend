from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth.dependencies import get_current_user, get_org_context
from app.config import Settings, get_settings
from app.middleware.entitlements import resolve_entitlements

router = APIRouter(prefix="/api/entitlements", tags=["entitlements"])


@router.get("")
async def get_entitlements_route(
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if not org_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    entitlements = resolve_entitlements(settings, org_id)
    return {"entitlements": entitlements}

