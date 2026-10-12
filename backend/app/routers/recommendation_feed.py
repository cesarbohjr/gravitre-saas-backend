"""Phase 5: one ranked recommendation feed (advisory only)."""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.auth.dependencies import get_current_user, get_org_context
from app.config import Settings, get_settings
from app.services.recommendation_feed import build_feed, feed_enabled
from app.workflows.repository import get_supabase_client

router = APIRouter(prefix="/api/recommendations", tags=["recommendations"])


@router.get("/feed")
async def recommendation_feed(
    user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
    department: str | None = Query(default=None),
) -> dict[str, Any]:
    if not feed_enabled(settings):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    if not org_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    return await build_feed(
        get_supabase_client(settings),
        settings,
        org_id=org_id,
        user_id=str(user.get("user_id") or "") or None,
        department=department,
    )
