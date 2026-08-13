"""In-process standing investigator scheduler (Temporal-friendly asyncio fallback)."""
from __future__ import annotations

import asyncio

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.services.standing_investigator_service import run_standing_investigators_tick

logger = get_logger(__name__)

_INITIAL_DELAY_S = 420
_DEFAULT_INTERVAL_S = 28800  # 8h, aligned with company intelligence cadence


async def _run_once(settings: Settings) -> None:
    summary = await run_standing_investigators_tick(settings)
    logger.info(
        "standing_investigator_tick orgs=%s advisory_only=%s writes_executed=%s",
        summary.get("orgs"),
        summary.get("advisory_only"),
        summary.get("writes_executed"),
    )


async def _loop(interval: int, settings: Settings) -> None:
    await asyncio.sleep(min(_INITIAL_DELAY_S, interval))
    while True:
        try:
            await _run_once(settings)
        except Exception as exc:  # noqa: BLE001
            logger.warning("standing_investigator_tick_failed error=%s", exc)
        await asyncio.sleep(interval)


def start_standing_investigator_scheduler() -> asyncio.Task | None:
    try:
        settings = get_settings()
        interval = int(
            getattr(settings, "standing_investigator_interval_seconds", _DEFAULT_INTERVAL_S) or 0
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("standing investigator scheduler not started: %s", exc)
        return None
    if interval <= 0:
        logger.info("standing investigator scheduler disabled (interval<=0)")
        return None
    logger.info("standing investigator scheduler started interval=%ss", interval)
    return asyncio.create_task(_loop(interval, settings))


async def stop_standing_investigator_scheduler(task: asyncio.Task | None) -> None:
    if task is None:
        return
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    except Exception as exc:  # noqa: BLE001
        logger.warning("standing investigator scheduler stop error: %s", exc)
