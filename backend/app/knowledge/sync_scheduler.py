"""In-process knowledge sync scheduler (STA-45).

Intentionally NOT migrated to Temporal: sync is idempotent and re-runs on the
next tick if a deploy interrupts an in-flight sync.
"""
from __future__ import annotations

import asyncio

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.services.knowledge_sync_service import run_scheduled_knowledge_syncs

logger = get_logger(__name__)

_INITIAL_DELAY_S = 120


async def _run_once(settings: Settings) -> None:
    try:
        summary = await asyncio.to_thread(run_scheduled_knowledge_syncs, settings)
        logger.info(
            "knowledge_sync_tick due=%s processed=%s",
            summary.get("due_count"),
            summary.get("processed"),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("knowledge_sync_tick failed: %s", exc)


async def _loop(interval: int, settings: Settings) -> None:
    await asyncio.sleep(min(_INITIAL_DELAY_S, interval))
    while True:
        await _run_once(settings)
        await asyncio.sleep(interval)


def start_knowledge_sync_scheduler() -> asyncio.Task | None:
    try:
        settings = get_settings()
        interval = int(getattr(settings, "knowledge_sync_interval_seconds", 3600) or 0)
    except Exception as exc:  # noqa: BLE001
        logger.warning("knowledge sync scheduler not started: %s", exc)
        return None
    if interval <= 0:
        logger.info("knowledge sync scheduler disabled (KNOWLEDGE_SYNC_INTERVAL_SECONDS<=0)")
        return None
    logger.info("knowledge sync scheduler started interval=%ss", interval)
    return asyncio.create_task(_loop(interval, settings))


async def stop_knowledge_sync_scheduler(task: asyncio.Task | None) -> None:
    if task is None:
        return
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    except Exception as exc:  # noqa: BLE001
        logger.warning("knowledge sync scheduler stop error: %s", exc)
