"""In-process tick for past-due approval escalation and the weekly summary."""
from __future__ import annotations

import asyncio

from supabase import create_client

from app.config import Settings, get_settings
from app.core.db import shared_service_client
from app.core.logging import get_logger
from app.services.ops_notifications import run_ops_notifications_tick

logger = get_logger(__name__)

_INITIAL_DELAY_S = 300
_DEFAULT_INTERVAL_S = 900  # 15 min: escalations land soon after the SLA runs out


async def _run_once(settings: Settings) -> None:
    client = shared_service_client(settings, create_client)
    summary = await asyncio.to_thread(run_ops_notifications_tick, client)
    logger.info(
        "ops_notifications_tick orgs=%s escalated=%s summaries=%s",
        summary.get("orgs"),
        summary.get("escalated"),
        summary.get("summaries"),
    )


async def _loop(interval: int, settings: Settings) -> None:
    await asyncio.sleep(min(_INITIAL_DELAY_S, interval))
    while True:
        try:
            await _run_once(settings)
        except Exception as exc:  # noqa: BLE001
            logger.warning("ops_notifications_tick_failed error=%s", exc)
        await asyncio.sleep(interval)


def start_ops_notifications_scheduler() -> asyncio.Task | None:
    try:
        settings = get_settings()
        interval = int(getattr(settings, "ops_notifications_interval_seconds", _DEFAULT_INTERVAL_S) or 0)
    except Exception as exc:  # noqa: BLE001
        logger.warning("ops notifications scheduler not started: %s", exc)
        return None
    if interval <= 0:
        logger.info("ops notifications scheduler disabled (interval<=0)")
        return None
    logger.info("ops notifications scheduler started interval=%ss", interval)
    return asyncio.create_task(_loop(interval, settings))


async def stop_ops_notifications_scheduler(task: asyncio.Task | None) -> None:
    if task is None:
        return
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    except Exception as exc:  # noqa: BLE001
        logger.warning("ops notifications scheduler stop error: %s", exc)
