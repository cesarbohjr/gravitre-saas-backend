"""Activity feed API."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from supabase import create_client

from app.auth.dependencies import get_current_user, get_org_context
from app.config import Settings, get_settings
from app.services.activity_feed_service import list_recent_activity

router = APIRouter(prefix="/api/activity", tags=["activity"])


@router.get("/recent")
async def recent_activity(
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
    limit: int = Query(12, ge=1, le=50),
    source: str | None = Query(None),
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    user_id = _user["user_id"]
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    events = list_recent_activity(
        client,
        org_id=org_id,
        user_id=user_id,
        limit=limit,
        source=source,
    )
    return {"events": events}
