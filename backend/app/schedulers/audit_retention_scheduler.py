"""Daily audit-log / telemetry retention (services/data_retention.py).

Off unless AUDIT_RETENTION_DAYS or TELEMETRY_RETENTION_DAYS is above 0. Dry run by
default (AUDIT_RETENTION_DRY_RUN). The receipt row is a lease, so several replicas
never prune at the same time.
"""
from __future__ import annotations

import asyncio

from supabase import create_client

from app.config import Settings, get_settings
from app.core.db import shared_service_client
from app.core.logging import get_logger
from app.services.data_retention import retention_plan, run_data_retention

logger = get_logger(__name__)

_INITIAL_DELAY_S = 300


async def _loop(settings: Settings, interval: int) -> None:
    client = shared_service_client(settings, create_client)
    await asyncio.sleep(min(_INITIAL_DELAY_S, interval))
    while True:
        try:
            receipt = await asyncio.to_thread(run_data_retention, client, settings)
            logger.info("audit_retention_tick status=%s", receipt.get("status"))
        except Exception as exc:  # noqa: BLE001
            logger.warning("audit_retention_tick_failed error=%s", type(exc).__name__)
        await asyncio.sleep(interval)


def start_audit_retention_scheduler() -> asyncio.Task | None:
    try:
        settings = get_settings()
        enabled = bool(retention_plan(settings))
        interval = int(getattr(settings, "audit_retention_interval_seconds", 86400) or 0)
    except Exception as exc:  # noqa: BLE001
        logger.warning("audit retention not started: %s", exc)
        return None
    if not enabled or interval <= 0:
        logger.info("audit retention disabled (retention days 0 = keep forever)")
        return None
    return asyncio.create_task(_loop(settings, interval))


async def stop_audit_retention_scheduler(task: asyncio.Task | None) -> None:
    if task is None:
        return
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    except Exception as exc:  # noqa: BLE001
        logger.warning("audit retention stop error: %s", exc)
