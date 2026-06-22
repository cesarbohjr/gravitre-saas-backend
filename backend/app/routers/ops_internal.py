"""Internal cron endpoints for daily rollups, retention purge, and connector health."""
from __future__ import annotations

import asyncio
import hmac
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field

from app.config import Settings, get_settings
from app.connectors.health_monitor_service import run_connector_health_monitor
from app.core.logging import get_logger
from app.workflows.repository import get_supabase_client

logger = get_logger(__name__)

router = APIRouter(prefix="/api/internal/ops", tags=["ops-internal"])


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


class RollupDailyRequest(BaseModel):
    days: int = Field(default=1, ge=1, le=90)
    purge_days: int | None = Field(default=None, ge=1, le=3650)


def _run_daily_rollup(settings: Settings, *, days: int, purge_days: int | None) -> dict[str, Any]:
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    client = get_supabase_client(settings)
    client.rpc(
        "rollup_all_daily",
        {"start_at": start.isoformat(), "end_at": end.isoformat()},
    ).execute()
    purged = None
    if purge_days is not None:
        cutoff = end - timedelta(days=purge_days)
        client.rpc("purge_audit_events_before", {"cutoff": cutoff.isoformat()}).execute()
        purged = cutoff.isoformat()
    return {
        "start_at": start.isoformat(),
        "end_at": end.isoformat(),
        "days": days,
        "purge_cutoff": purged,
    }


@router.post("/rollup-daily")
async def rollup_daily_cron(
    body: RollupDailyRequest | None = None,
    settings: Settings = Depends(get_settings),
    _: Annotated[None, Depends(require_internal_secret)] = None,
) -> dict[str, Any]:
    """Daily metrics rollups (+ optional audit retention purge)."""
    req = body or RollupDailyRequest()
    summary = await asyncio.to_thread(
        _run_daily_rollup,
        settings,
        days=req.days,
        purge_days=req.purge_days,
    )
    logger.info(
        "rollup_daily_cron days=%s purge_cutoff=%s",
        summary.get("days"),
        summary.get("purge_cutoff"),
    )
    return summary


@router.post("/connector-health")
async def connector_health_cron(
    settings: Settings = Depends(get_settings),
    _: Annotated[None, Depends(require_internal_secret)] = None,
) -> dict[str, Any]:
    """Run connector OAuth health checks (durable alternative to in-process scheduler)."""
    summary = await asyncio.to_thread(run_connector_health_monitor, settings)
    logger.info(
        "connector_health_cron checked=%s updated=%s errors=%s",
        summary.get("checked"),
        summary.get("updated"),
        summary.get("errors"),
    )
    return summary
