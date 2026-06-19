"""Internal cron API for platform CS workspace maintenance (Tier 6 v2)."""
from __future__ import annotations

import asyncio
import hmac
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from supabase import create_client

from app.config import Settings, get_settings
from app.services.platform_cs_workspace_service import backfill_platform_health_snapshots

router = APIRouter(prefix="/api/internal/platform/cs-workspace", tags=["platform-internal"])


async def require_internal_secret(
    settings: Annotated[Settings, Depends(get_settings)],
    x_internal_secret: Annotated[str | None, Header()] = None,
) -> None:
    secret = (settings.internal_api_secret or "").strip()
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="INTERNAL_API_SECRET is not configured",
        )
    if not x_internal_secret or not hmac.compare_digest(x_internal_secret, secret):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid internal secret")


@router.post("/snapshots/backfill-due")
async def internal_backfill_cs_snapshots(
    _secret: Annotated[None, Depends(require_internal_secret)],
    settings: Settings = Depends(get_settings),
    limit: int = Query(default=25, ge=1, le=100),
    lookback_days: int = Query(default=30, ge=7, le=90, alias="lookbackDays"),
) -> dict[str, Any]:
    """Cron entry: backfill integration health snapshots for orgs missing history."""
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    return await asyncio.to_thread(
        backfill_platform_health_snapshots,
        client,
        limit=limit,
        lookback_days=lookback_days,
        actor_id=None,
    )
