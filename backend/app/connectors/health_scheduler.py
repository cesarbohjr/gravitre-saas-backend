"""In-process connector OAuth health monitor (30s default).

Intentionally NOT migrated to Temporal: idempotent health probe; a missed
30s tick has no lasting effect on data correctness.
"""
from __future__ import annotations

import asyncio

from app.config import Settings, get_settings
from app.connectors.health_monitor_service import run_connector_health_monitor
from app.core.logging import get_logger

logger = get_logger(__name__)

_INITIAL_DELAY_S = 15


async def _run_once(settings: Settings) -> None:
    try:
        await asyncio.to_thread(run_connector_health_monitor, settings)
    except Exception as exc:  # noqa: BLE001
        logger.warning("connector_health_tick failed: %s", exc)


async def _loop(interval: int, settings: Settings) -> None:
    await asyncio.sleep(min(_INITIAL_DELAY_S, interval))
    while True:
        await _run_once(settings)
        await asyncio.sleep(interval)


def start_connector_health_scheduler() -> asyncio.Task | None:
    try:
        settings = get_settings()
        interval = int(getattr(settings, "connector_health_interval_seconds", 30) or 0)
    except Exception as exc:  # noqa: BLE001
        logger.warning("connector health scheduler not started: %s", exc)
        return None
    if interval <= 0:
        logger.info("connector health scheduler disabled (CONNECTOR_HEALTH_INTERVAL_SECONDS<=0)")
        return None
    if settings.disable_connectors:
        logger.info("connector health scheduler disabled (DISABLE_CONNECTORS=true)")
        return None
    logger.info("connector health scheduler started interval=%ss", interval)
    return asyncio.create_task(_loop(interval, settings))


async def stop_connector_health_scheduler(task: asyncio.Task | None) -> None:
    if task is None:
        return
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    except Exception as exc:  # noqa: BLE001
        logger.warning("connector health scheduler stop error: %s", exc)
