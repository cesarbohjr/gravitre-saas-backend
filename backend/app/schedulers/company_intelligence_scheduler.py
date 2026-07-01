"""In-process company intelligence scheduler.

When TEMPORAL_HOST is set, CompanyIntelligenceWorkflow in app/temporal/
replaces this loop — see main.py lifespan. Kept as asyncio fallback when
Temporal is not configured (no retry on Railway restarts).
"""
from __future__ import annotations

import asyncio

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.services.company_intelligence_collectors import get_active_org_ids
from app.services.company_intelligence_orchestrator import run_company_intelligence_for_org_sync

logger = get_logger(__name__)

_INITIAL_DELAY_S = 300


async def _run_once(settings: Settings) -> None:
    org_ids = await asyncio.to_thread(get_active_org_ids, settings, since_days=7, limit=20)
    if not org_ids:
        logger.info("company_intelligence_tick no_active_orgs")
        return
    processed = 0
    for org_id in org_ids:
        try:
            summary = await asyncio.to_thread(run_company_intelligence_for_org_sync, org_id, settings)
            processed += 1
            logger.info(
                "company_intelligence_org_completed org_id=%s workflow_rows=%s query_rows=%s",
                org_id,
                summary.get("workflow_rows"),
                summary.get("query_rows"),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("company_intelligence_org_failed org_id=%s error=%s", org_id, exc)
    logger.info("company_intelligence_tick processed=%s due=%s", processed, len(org_ids))


async def _loop(interval: int, settings: Settings) -> None:
    await asyncio.sleep(min(_INITIAL_DELAY_S, interval))
    while True:
        await _run_once(settings)
        await asyncio.sleep(interval)


def start_company_intelligence_scheduler() -> asyncio.Task | None:
    try:
        settings = get_settings()
        interval = int(getattr(settings, "company_intelligence_interval_seconds", 28800) or 0)
    except Exception as exc:  # noqa: BLE001
        logger.warning("company intelligence scheduler not started: %s", exc)
        return None
    if interval <= 0:
        logger.info("company intelligence scheduler disabled (COMPANY_INTELLIGENCE_INTERVAL_SECONDS<=0)")
        return None
    logger.info("company intelligence scheduler started interval=%ss", interval)
    return asyncio.create_task(_loop(interval, settings))


async def stop_company_intelligence_scheduler(task: asyncio.Task | None) -> None:
    if task is None:
        return
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    except Exception as exc:  # noqa: BLE001
        logger.warning("company intelligence scheduler stop error: %s", exc)
