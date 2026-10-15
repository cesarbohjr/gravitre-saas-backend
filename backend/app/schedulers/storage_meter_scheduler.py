"""Daily per-org storage snapshot (services/storage_meter.py).

Off unless STORAGE_METER_ENABLED is true. Snapshots are upserted per org and day, so
several replicas only rewrite the same rows.
"""
from __future__ import annotations

import asyncio

from supabase import create_client

from app.config import Settings, get_settings
from app.core.db import shared_service_client
from app.core.logging import get_logger
from app.services.storage_meter import write_storage_snapshots

logger = get_logger(__name__)

_INITIAL_DELAY_S = 300


async def _loop(settings: Settings, interval: int) -> None:
    client = shared_service_client(settings, create_client)
    await asyncio.sleep(min(_INITIAL_DELAY_S, interval))
    while True:
        try:
            orgs = await asyncio.to_thread(write_storage_snapshots, client)
            logger.info("storage_meter_tick orgs=%s", orgs)
        except Exception as exc:  # noqa: BLE001
            logger.warning("storage_meter_tick_failed error=%s", type(exc).__name__)
        await asyncio.sleep(interval)


def start_storage_meter_scheduler() -> asyncio.Task | None:
    try:
        settings = get_settings()
        enabled = getattr(settings, "storage_meter_enabled", False) is True
        interval = int(getattr(settings, "storage_meter_interval_seconds", 86400) or 0)
    except Exception as exc:  # noqa: BLE001
        logger.warning("storage meter not started: %s", exc)
        return None
    if not enabled or interval <= 0:
        logger.info("storage meter disabled")
        return None
    return asyncio.create_task(_loop(settings, interval))


async def stop_storage_meter_scheduler(task: asyncio.Task | None) -> None:
    if task is None:
        return
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    except Exception as exc:  # noqa: BLE001
        logger.warning("storage meter stop error: %s", exc)
