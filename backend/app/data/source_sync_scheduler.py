"""In-process data source sync scheduler."""
from __future__ import annotations

import asyncio

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.services.source_sync_service import run_scheduled_source_syncs

logger = get_logger(__name__)

_INITIAL_DELAY_S = 90


async def _run_once(settings: Settings) -> None:
    try:
        summary = await run_scheduled_source_syncs(settings)
        logger.info(
            "source_sync_tick due=%s processed=%s errors=%s",
            summary.get("due_count"),
            summary.get("processed"),
            summary.get("errors"),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("source_sync_tick failed: %s", exc)


async def _loop(interval: int, settings: Settings) -> None:
    await asyncio.sleep(min(_INITIAL_DELAY_S, interval))
    while True:
        await _run_once(settings)
        await asyncio.sleep(interval)


def start_source_sync_scheduler() -> asyncio.Task | None:
    try:
        settings = get_settings()
        interval = int(getattr(settings, "source_sync_interval_seconds", 300) or 0)
    except Exception as exc:  # noqa: BLE001
        logger.warning("source sync scheduler not started: %s", exc)
        return None
    if interval <= 0:
        logger.info("source sync scheduler disabled (SOURCE_SYNC_INTERVAL_SECONDS<=0)")
        return None
    logger.info("source sync scheduler started interval=%ss", interval)
    return asyncio.create_task(_loop(interval, settings))


async def stop_source_sync_scheduler(task: asyncio.Task | None) -> None:
    if task is None:
        return
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    except Exception as exc:  # noqa: BLE001
        logger.warning("source sync scheduler stop error: %s", exc)
