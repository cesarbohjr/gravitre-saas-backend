"""Daily labeling of checkable predictions (Phase 6).

Off unless ML_PREDICTION_OUTCOMES_ENABLED is true. Each update only moves a row
out of 'pending', so running on several replicas at once cannot double-label.
"""
from __future__ import annotations

import asyncio

from supabase import create_client

from app.config import Settings, get_settings
from app.core.db import shared_service_client
from app.core.logging import get_logger
from app.ml.prediction_outcomes import run_labeling

logger = get_logger(__name__)

_INITIAL_DELAY_S = 300


async def _loop(settings: Settings, interval: int) -> None:
    client = shared_service_client(settings, create_client)
    await asyncio.sleep(min(_INITIAL_DELAY_S, interval))
    while True:
        try:
            results = await asyncio.to_thread(run_labeling, client)
            if results:
                logger.info("prediction_labeling_tick orgs=%s", len(results))
        except Exception as exc:  # noqa: BLE001
            logger.warning("prediction_labeling_tick_failed error=%s", exc)
        await asyncio.sleep(interval)


def start_prediction_labeling_scheduler() -> asyncio.Task | None:
    try:
        settings = get_settings()
        enabled = getattr(settings, "ml_prediction_outcomes_enabled", False) is True
        interval = int(getattr(settings, "ml_prediction_labeling_interval_seconds", 86400) or 0)
    except Exception as exc:  # noqa: BLE001
        logger.warning("prediction labeling not started: %s", exc)
        return None
    if not enabled or interval <= 0:
        logger.info("prediction labeling disabled")
        return None
    return asyncio.create_task(_loop(settings, interval))


async def stop_prediction_labeling_scheduler(task: asyncio.Task | None) -> None:
    if task is None:
        return
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    except Exception as exc:  # noqa: BLE001
        logger.warning("prediction labeling stop error: %s", exc)
