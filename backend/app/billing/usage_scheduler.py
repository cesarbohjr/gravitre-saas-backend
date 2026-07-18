"""In-process hourly scheduler that reports metered AI usage to Stripe.

Activates the usage-sync pipeline without an external scheduler: a background
asyncio task runs report_usage_for_active_orgs on an interval. Safe because
reporting is idempotent — it only sends usage_tracking rows with
stripe_reported_at IS NULL and uses a deterministic Stripe meter-event
identifier, so even if multiple instances run this loop, usage is never
double-reported.

Disable by setting USAGE_SYNC_INTERVAL_SECONDS=0 (e.g. if you prefer the
GitHub Action / a Railway cron service instead). The sync work runs in a thread
(report_usage_for_active_orgs uses a sync Supabase client) so it never blocks the
event loop.
"""
from __future__ import annotations

import asyncio

from app.billing.service import get_current_period
from app.billing.stripe_metering import report_usage_for_active_orgs
from app.billing.stripe_research_lookup_metering import report_research_lookup_overage_for_active_orgs
from app.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_INITIAL_DELAY_S = 60  # report shortly after boot, then every interval


def _sync_all_usage(period_start, period_end, settings: Settings) -> dict:
    ai_summary = report_usage_for_active_orgs(period_start, period_end, settings)
    research_summary = report_research_lookup_overage_for_active_orgs(period_start, period_end, settings)
    return {
        "ai_credits": ai_summary,
        "research_lookups": research_summary,
        "error": ai_summary.get("error") or research_summary.get("error"),
    }


async def _run_once(settings: Settings) -> None:
    try:
        period_start, period_end = get_current_period()
        summary = await asyncio.to_thread(
            _sync_all_usage, period_start, period_end, settings
        )
        logger.info(
            "usage_sync_tick orgs=%s ai_reported_rows=%s research_reported_orgs=%s error=%s",
            summary.get("ai_credits", {}).get("orgs"),
            summary.get("ai_credits", {}).get("reported_rows"),
            summary.get("research_lookups", {}).get("reported_orgs"),
            summary.get("error"),
        )
    except Exception as exc:  # noqa: BLE001 - never let a tick kill the loop
        logger.warning("usage_sync_tick failed: %s", str(exc))


async def _loop(interval: int, settings: Settings) -> None:
    await asyncio.sleep(min(_INITIAL_DELAY_S, interval))
    while True:
        await _run_once(settings)
        await asyncio.sleep(interval)


def start_usage_sync_scheduler() -> asyncio.Task | None:
    """Start the background loop. Returns the task, or None if disabled."""
    try:
        settings = get_settings()
        interval = int(getattr(settings, "usage_sync_interval_seconds", 3600) or 0)
    except Exception as exc:  # noqa: BLE001 - never block app startup
        logger.warning("usage sync scheduler not started: %s", str(exc))
        return None
    if interval <= 0:
        logger.info("usage sync scheduler disabled (USAGE_SYNC_INTERVAL_SECONDS<=0)")
        return None
    logger.info("usage sync scheduler started interval=%ss", interval)
    return asyncio.create_task(_loop(interval, settings))


async def stop_usage_sync_scheduler(task: asyncio.Task | None) -> None:
    if task is None:
        return
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    except Exception as exc:  # noqa: BLE001
        logger.warning("usage sync scheduler stop error: %s", str(exc))
