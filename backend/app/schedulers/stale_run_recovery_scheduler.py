"""Periodic stale run recovery. Off unless STALE_RUN_RECOVERY_ENABLED is true.

Safe on every replica at once: each transition is compare-and-set on the run's
old status, so only one replica (or the worker itself, if it finishes late) wins.
"""
from __future__ import annotations

import asyncio

from supabase import create_client

from app.config import Settings, get_settings
from app.core.db import shared_service_client
from app.core.logging import get_logger
from app.services.stale_run_recovery import recover_stale_runs

logger = get_logger(__name__)

_INITIAL_DELAY_S = 120


async def _loop(settings: Settings, interval: int) -> None:
    client = shared_service_client(settings, create_client)
    await asyncio.sleep(min(_INITIAL_DELAY_S, interval))
    while True:
        try:
            result = await asyncio.to_thread(
                recover_stale_runs,
                client,
                threshold_minutes=int(settings.stale_run_recovery_threshold_minutes or 60),
                verifying_threshold_minutes=int(settings.stale_run_recovery_verifying_threshold_minutes or 1440),
                dry_run=False,
            )
            if result["candidates"]:
                logger.info(
                    "stale_run_recovery candidates=%s applied=%s by_outcome=%s",
                    result["candidates"],
                    result["applied"],
                    result["by_outcome"],
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("stale_run_recovery_tick_failed error=%s", exc)
        await asyncio.sleep(interval)


def start_stale_run_recovery_scheduler() -> asyncio.Task | None:
    try:
        settings = get_settings()
        enabled = bool(settings.stale_run_recovery_enabled)
        interval = int(settings.stale_run_recovery_interval_seconds or 0)
    except Exception as exc:  # noqa: BLE001
        logger.warning("stale run recovery not started: %s", exc)
        return None
    if not enabled or interval <= 0:
        logger.info("stale run recovery disabled (STALE_RUN_RECOVERY_ENABLED is false)")
        return None
    return asyncio.create_task(_loop(settings, interval))


async def stop_stale_run_recovery_scheduler(task: asyncio.Task | None) -> None:
    if task is None:
        return
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
