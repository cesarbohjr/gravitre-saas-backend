"""Optional in-process recovery tick, using PostgreSQL recovery leases.

Safe for multiple API replicas: SKIP LOCKED leasing provides ownership and
CAS-fenced settlement; unverified cases are deferred without reissuing writes.
Disabled by default until original provider readback capability is certified.
"""
from __future__ import annotations

import asyncio

from supabase import create_client
from app.config import get_settings
from app.core.db import shared_service_client
from app.core.logging import get_logger
from app.services.tool_types import ToolContext
from app.services.write_recovery_worker import process_due_write_recoveries

logger = get_logger(__name__)


async def _loop(settings, interval: int) -> None:
    service_client = shared_service_client(settings, create_client)

    def resolve_context(org_id: str, connector_id: str) -> ToolContext:
        return ToolContext(
            settings=settings, client=service_client, org_id=org_id,
            actor_id="system:write-recovery", connector_id=connector_id,
            write_idempotency_required=True,
        )

    await asyncio.sleep(min(30, interval))
    while True:
        try:
            stats = await asyncio.to_thread(
                process_due_write_recoveries,
                service_client=service_client,
                context_factory=resolve_context,
            )
            if stats["seen"] or stats["error"]:
                logger.info("write_recovery_tick %s", stats)
        except Exception:
            logger.exception("write_recovery_tick_failed")
        await asyncio.sleep(interval)


def start_write_recovery_scheduler() -> asyncio.Task | None:
    settings = get_settings()
    if not bool(getattr(settings, "write_recovery_scheduler_enabled", False)):
        return None
    interval = int(getattr(settings, "write_recovery_scheduler_interval_seconds", 120))
    if interval <= 0:
        return None
    return asyncio.create_task(_loop(settings, interval))


async def stop_write_recovery_scheduler(task: asyncio.Task | None) -> None:
    if task is None:
        return
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
