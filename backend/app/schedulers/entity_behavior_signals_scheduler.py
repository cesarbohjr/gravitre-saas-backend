"""Daily rule-based behaviour signals per account (Phase 7).

Calls ``compute_entity_behavior_signals`` (migration 20261012040000) for every
org with customer observations in the last 90 days. The function upserts one
row per entity, signal and day, so a second replica running the same tick only
rewrites the same values.

Off unless ENTITY_BEHAVIOR_SIGNALS_ENABLED is true.
"""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

from supabase import create_client

from app.config import Settings, get_settings
from app.core.db import shared_service_client
from app.core.logging import get_logger

logger = get_logger(__name__)

_INITIAL_DELAY_S = 600
LOOKBACK_DAYS = 90
MAX_ROWS_SCANNED = 20000


def orgs_with_recent_observations(client: Any, *, now: datetime | None = None) -> list[str]:
    now = now or datetime.now(UTC)
    since = (now - timedelta(days=LOOKBACK_DAYS)).isoformat()
    rows = (
        client.table("entity_observations")
        .select("org_id")
        .gte("observed_at", since)
        .limit(MAX_ROWS_SCANNED)
        .execute()
        .data
        or []
    )
    return sorted({str(r["org_id"]) for r in rows if r.get("org_id")})


def run_behavior_signals(client: Any, *, now: datetime | None = None) -> dict[str, int]:
    """One pass over all orgs; returns rows written per org. Never raises per org."""
    now = now or datetime.now(UTC)
    written: dict[str, int] = {}
    for org_id in orgs_with_recent_observations(client, now=now):
        try:
            res = client.rpc(
                "compute_entity_behavior_signals", {"p_org_id": org_id, "p_as_of": now.isoformat()}
            ).execute()
            written[org_id] = int(res.data or 0)
        except Exception as exc:  # noqa: BLE001
            logger.warning("behavior_signals_org_failed org_id=%s error=%s", org_id, type(exc).__name__)
    return written


async def _loop(settings: Settings, interval: int) -> None:
    client = shared_service_client(settings, create_client)
    await asyncio.sleep(min(_INITIAL_DELAY_S, interval))
    while True:
        try:
            written = await asyncio.to_thread(run_behavior_signals, client)
            logger.info("behavior_signals_tick orgs=%s rows=%s", len(written), sum(written.values()))
        except Exception as exc:  # noqa: BLE001
            logger.warning("behavior_signals_tick_failed error=%s", exc)
        await asyncio.sleep(interval)


def start_entity_behavior_signals_scheduler() -> asyncio.Task | None:
    try:
        settings = get_settings()
        enabled = getattr(settings, "entity_behavior_signals_enabled", False) is True
        interval = int(getattr(settings, "entity_behavior_signals_interval_seconds", 86400) or 0)
    except Exception as exc:  # noqa: BLE001
        logger.warning("behavior signals not started: %s", exc)
        return None
    if not enabled or interval <= 0:
        logger.info("behavior signals disabled")
        return None
    return asyncio.create_task(_loop(settings, interval))


async def stop_entity_behavior_signals_scheduler(task: asyncio.Task | None) -> None:
    if task is None:
        return
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    except Exception as exc:  # noqa: BLE001
        logger.warning("behavior signals stop error: %s", exc)
