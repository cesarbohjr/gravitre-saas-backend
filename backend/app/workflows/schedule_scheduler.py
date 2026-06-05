"""In-process workflow schedule dispatcher (STA-47)."""
from __future__ import annotations

import asyncio

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.services.workflow_schedule_service import dispatch_due_workflow_schedules

logger = get_logger(__name__)

_INITIAL_DELAY_S = 60


async def _run_once(settings: Settings) -> None:
    try:
        summary = await asyncio.to_thread(dispatch_due_workflow_schedules, settings)
        logger.info(
            "workflow_schedule_tick due=%s processed=%s",
            summary.get("due_count"),
            summary.get("processed"),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("workflow_schedule_tick failed: %s", exc)


async def _loop(interval: int, settings: Settings) -> None:
    await asyncio.sleep(min(_INITIAL_DELAY_S, interval))
    while True:
        await _run_once(settings)
        await asyncio.sleep(interval)


def start_workflow_schedule_scheduler() -> asyncio.Task | None:
    try:
        settings = get_settings()
        interval = int(getattr(settings, "workflow_schedule_interval_seconds", 60) or 0)
    except Exception as exc:  # noqa: BLE001
        logger.warning("workflow schedule scheduler not started: %s", exc)
        return None
    if interval <= 0:
        logger.info("workflow schedule scheduler disabled (WORKFLOW_SCHEDULE_INTERVAL_SECONDS<=0)")
        return None
    logger.info("workflow schedule scheduler started interval=%ss", interval)
    return asyncio.create_task(_loop(interval, settings))


async def stop_workflow_schedule_scheduler(task: asyncio.Task | None) -> None:
    if task is None:
        return
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    except Exception as exc:  # noqa: BLE001
        logger.warning("workflow schedule scheduler stop error: %s", exc)
