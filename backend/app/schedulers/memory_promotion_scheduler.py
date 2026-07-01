"""In-process memory promotion and expiration schedulers (v4).

Promotion evaluation and outcome measurement migrate to Temporal workflows
(MemoryPromotionWorkflow, OutcomeMeasurementWorkflow) when TEMPORAL_HOST is set.
Expiration checks stay here — missed ticks are low impact and idempotent.
"""
from __future__ import annotations

import asyncio

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.services.company_intelligence_collectors import get_active_org_ids
from app.services.memory_promotion_service import get_memory_promotion_service

logger = get_logger(__name__)

_INITIAL_DELAY_S = 420


async def _run_promotion_eval(settings: Settings) -> None:
    org_ids = await asyncio.to_thread(get_active_org_ids, settings, since_days=7, limit=20)
    service = get_memory_promotion_service(settings)
    from app.services.outcome_attribution_service import get_outcome_attribution_service

    outcome_service = get_outcome_attribution_service(settings)
    for org_id in org_ids:
        try:
            summary = await service.run_evaluation(org_id)
            measured = await outcome_service.measure_outcomes_due(org_id)
            summary["outcome_measurements_completed"] = measured
            logger.info("memory_promotion_eval org_id=%s summary=%s", org_id, summary)
        except Exception as exc:  # noqa: BLE001
            logger.warning("memory_promotion_eval_failed org_id=%s error=%s", org_id, exc)


async def _run_expiration_check(settings: Settings) -> None:
    org_ids = await asyncio.to_thread(get_active_org_ids, settings, since_days=7, limit=50)
    service = get_memory_promotion_service(settings)
    for org_id in org_ids:
        try:
            summary = await service.run_expiration_check(org_id)
            logger.info("memory_expiration_check org_id=%s summary=%s", org_id, summary)
        except Exception as exc:  # noqa: BLE001
            logger.warning("memory_expiration_check_failed org_id=%s error=%s", org_id, exc)


async def _promotion_loop(interval: int, settings: Settings) -> None:
    await asyncio.sleep(min(_INITIAL_DELAY_S, interval))
    while True:
        await _run_promotion_eval(settings)
        await asyncio.sleep(interval)


async def _expiration_loop(interval: int, settings: Settings) -> None:
    await asyncio.sleep(min(_INITIAL_DELAY_S + 60, interval))
    while True:
        await _run_expiration_check(settings)
        await asyncio.sleep(interval)


def start_memory_promotion_scheduler() -> asyncio.Task | None:
    try:
        settings = get_settings()
        interval = int(getattr(settings, "memory_promotion_eval_interval_seconds", 28800) or 0)
    except Exception as exc:  # noqa: BLE001
        logger.warning("memory promotion scheduler not started: %s", exc)
        return None
    if interval <= 0:
        logger.info("memory promotion scheduler disabled")
        return None
    logger.info("memory promotion scheduler started interval=%ss", interval)
    return asyncio.create_task(_promotion_loop(interval, settings))


def start_memory_expiration_scheduler() -> asyncio.Task | None:
    try:
        settings = get_settings()
        interval = int(getattr(settings, "memory_expiration_check_interval_seconds", 86400) or 0)
    except Exception as exc:  # noqa: BLE001
        logger.warning("memory expiration scheduler not started: %s", exc)
        return None
    if interval <= 0:
        logger.info("memory expiration scheduler disabled")
        return None
    logger.info("memory expiration scheduler started interval=%ss", interval)
    return asyncio.create_task(_expiration_loop(interval, settings))


async def stop_scheduler(task: asyncio.Task | None) -> None:
    if task is None:
        return
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    except Exception as exc:  # noqa: BLE001
        logger.warning("memory scheduler stop error: %s", exc)
