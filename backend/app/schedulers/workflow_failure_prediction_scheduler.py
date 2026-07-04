"""Periodic workflow failure prediction scans (STA-167)."""
from __future__ import annotations

import asyncio

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.services.company_intelligence_collectors import get_active_org_ids
from app.services.workflow_failure_prediction_service import scan_org_failure_predictions
from app.workflows.repository import get_supabase_client

logger = get_logger(__name__)

_INITIAL_DELAY_S = 600


async def _run_once(settings: Settings) -> None:
    org_ids = await asyncio.to_thread(get_active_org_ids, settings, since_days=7, limit=25)
    if not org_ids:
        logger.info("workflow_failure_prediction_tick no_active_orgs")
        return
    client = get_supabase_client(settings)
    processed = 0
    for org_id in org_ids:
        try:
            summary = await asyncio.to_thread(
                scan_org_failure_predictions,
                client,
                settings,
                org_id,
                environment_name="production",
            )
            processed += 1
            logger.info(
                "workflow_failure_prediction_org_completed org_id=%s workflows=%s alerts=%s",
                org_id,
                summary.get("workflowCount"),
                summary.get("alertCount"),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("workflow_failure_prediction_org_failed org_id=%s error=%s", org_id, exc)
    logger.info("workflow_failure_prediction_tick processed=%s due=%s", processed, len(org_ids))


async def _loop(interval: int, settings: Settings) -> None:
    await asyncio.sleep(min(_INITIAL_DELAY_S, interval))
    while True:
        await _run_once(settings)
        await asyncio.sleep(interval)


def start_workflow_failure_prediction_scheduler() -> asyncio.Task | None:
    try:
        settings = get_settings()
        interval = int(getattr(settings, "workflow_failure_prediction_interval_seconds", 3600) or 0)
    except Exception as exc:  # noqa: BLE001
        logger.warning("workflow failure prediction scheduler not started: %s", exc)
        return None
    if interval <= 0:
        logger.info("workflow failure prediction scheduler disabled (interval<=0)")
        return None
    logger.info("workflow failure prediction scheduler started interval=%ss", interval)
    return asyncio.create_task(_loop(interval, settings))


async def stop_workflow_failure_prediction_scheduler(task: asyncio.Task | None) -> None:
    if task is None:
        return
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    except Exception as exc:  # noqa: BLE001
        logger.warning("workflow failure prediction scheduler stop error: %s", exc)
