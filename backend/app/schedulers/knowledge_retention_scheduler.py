"""Daily retention prune for indexed documents (Phase 2C).

Off unless KNOWLEDGE_RETENTION_PRUNE_ENABLED is true. Deletes are filtered by org,
source and age, so running on several replicas at once only repeats empty passes.
"""
from __future__ import annotations

import asyncio

from supabase import create_client

from app.config import Settings, get_settings
from app.core.db import shared_service_client
from app.core.logging import get_logger
from app.services.knowledge_retention import run_retention_prune

logger = get_logger(__name__)

_INITIAL_DELAY_S = 300


async def _loop(settings: Settings, interval: int) -> None:
    client = shared_service_client(settings, create_client)
    await asyncio.sleep(min(_INITIAL_DELAY_S, interval))
    while True:
        try:
            results = await asyncio.to_thread(run_retention_prune, client)
            if results:
                logger.info("knowledge_retention_tick orgs=%s", len(results))
        except Exception as exc:  # noqa: BLE001
            logger.warning("knowledge_retention_tick_failed error=%s", exc)
        await asyncio.sleep(interval)


def start_knowledge_retention_scheduler() -> asyncio.Task | None:
    try:
        settings = get_settings()
        enabled = getattr(settings, "knowledge_retention_prune_enabled", False) is True
        interval = int(getattr(settings, "knowledge_retention_interval_seconds", 86400) or 0)
    except Exception as exc:  # noqa: BLE001
        logger.warning("knowledge retention not started: %s", exc)
        return None
    if not enabled or interval <= 0:
        logger.info("knowledge retention prune disabled")
        return None
    return asyncio.create_task(_loop(settings, interval))


async def stop_knowledge_retention_scheduler(task: asyncio.Task | None) -> None:
    if task is None:
        return
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    except Exception as exc:  # noqa: BLE001
        logger.warning("knowledge retention stop error: %s", exc)
