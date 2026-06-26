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


class CompanyIntelligenceRunRequest(BaseModel):
    org_id: str | None = None


@router.post("/company-intelligence-run")
async def company_intelligence_run_cron(
    body: CompanyIntelligenceRunRequest | None = None,
    settings: Settings = Depends(get_settings),
    _: Annotated[None, Depends(require_internal_secret)] = None,
) -> dict[str, Any]:
    """Manual/GitHub-Actions trigger for the company intelligence learning loop."""
    from app.services.company_intelligence_collectors import get_active_org_ids
    from app.services.company_intelligence_orchestrator import CompanyIntelligenceOrchestrator

    req = body or CompanyIntelligenceRunRequest()
    orchestrator = CompanyIntelligenceOrchestrator(settings=settings)
    if req.org_id:
        summary = await orchestrator.run_for_org(req.org_id)
        return {"processed": 1, "results": [summary]}

    org_ids = await asyncio.to_thread(get_active_org_ids, settings, since_days=7, limit=20)
    results: list[dict[str, Any]] = []
    for org_id in org_ids:
        try:
            results.append(await orchestrator.run_for_org(org_id))
        except Exception as exc:  # noqa: BLE001
            results.append({"org_id": org_id, "error": str(exc)})
    return {"processed": len(results), "results": results}


class MemoryPromotionRunRequest(BaseModel):
    org_id: str | None = None


@router.post("/memory-promotion-run")
async def memory_promotion_run_cron(
    body: MemoryPromotionRunRequest | None = None,
    settings: Settings = Depends(get_settings),
    _: Annotated[None, Depends(require_internal_secret)] = None,
) -> dict[str, Any]:
    """Manual trigger for memory promotion evaluation (v4)."""
    from app.services.company_intelligence_collectors import get_active_org_ids
    from app.services.memory_promotion_service import get_memory_promotion_service

    req = body or MemoryPromotionRunRequest()
    service = get_memory_promotion_service(settings)
    if req.org_id:
        summary = await service.run_evaluation(req.org_id)
        return {"processed": 1, "results": [summary]}

    org_ids = await asyncio.to_thread(get_active_org_ids, settings, since_days=7, limit=20)
    results: list[dict[str, Any]] = []
    for org_id in org_ids:
        try:
            results.append(await service.run_evaluation(org_id))
        except Exception as exc:  # noqa: BLE001
            results.append({"org_id": org_id, "error": str(exc)})
    return {"processed": len(results), "results": results}


class MemoryExpirationRunRequest(BaseModel):
    org_id: str | None = None


@router.post("/memory-expiration-run")
async def memory_expiration_run_cron(
    body: MemoryExpirationRunRequest | None = None,
    settings: Settings = Depends(get_settings),
    _: Annotated[None, Depends(require_internal_secret)] = None,
) -> dict[str, Any]:
    """Manual trigger for memory expiration/decay checks (v4)."""
    from app.services.company_intelligence_collectors import get_active_org_ids
    from app.services.memory_promotion_service import get_memory_promotion_service

    req = body or MemoryExpirationRunRequest()
    service = get_memory_promotion_service(settings)
    if req.org_id:
        summary = await service.run_expiration_check(req.org_id)
        return {"processed": 1, "results": [summary]}

    org_ids = await asyncio.to_thread(get_active_org_ids, settings, since_days=7, limit=50)
    results: list[dict[str, Any]] = []
    for org_id in org_ids:
        try:
            results.append(await service.run_expiration_check(org_id))
        except Exception as exc:  # noqa: BLE001
            results.append({"org_id": org_id, "error": str(exc)})
    return {"processed": len(results), "results": results}
