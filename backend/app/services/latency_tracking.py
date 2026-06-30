"""Per-stage latency instrumentation for the intelligence pipeline."""
from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any, ParamSpec, TypeVar
from uuid import uuid4

from app.core.logging import get_logger
from app.workflows.repository import get_supabase_client

logger = get_logger(__name__)

P = ParamSpec("P")
T = TypeVar("T")


async def log_pipeline_latency(
    settings: Any,
    *,
    org_id: str,
    stage_name: str,
    duration_ms: int,
    message_id: str | None = None,
    cache_hit: bool = False,
    tier: str | None = None,
    model_used: str | None = None,
    estimated_cost_usd: float | None = None,
    client: Any | None = None,
) -> None:
    if duration_ms < 0:
        return
    db = client or get_supabase_client(settings)
    row = {
        "id": str(uuid4()),
        "org_id": org_id,
        "message_id": message_id,
        "stage_name": stage_name,
        "duration_ms": int(duration_ms),
        "cache_hit": bool(cache_hit),
    }
    if tier:
        row["tier"] = tier
    if model_used:
        row["model_used"] = model_used
    if estimated_cost_usd is not None:
        row["estimated_cost_usd"] = estimated_cost_usd
    try:
        db.table("ai_pipeline_latency").insert(row).execute()
    except Exception as exc:  # noqa: BLE001
        logger.debug(
            "ai_pipeline_latency insert skipped org_id=%s stage=%s error=%s",
            org_id,
            stage_name,
            exc,
        )


def latency_stage(stage_name: str) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    """Decorator for async functions; expects org_id and optional message_id kwargs."""

    def decorator(func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            started = time.monotonic()
            cache_hit = bool(kwargs.get("cache_hit"))
            try:
                return await func(*args, **kwargs)
            finally:
                org_id = kwargs.get("org_id")
                settings = kwargs.get("settings")
                message_id = kwargs.get("message_id")
                if org_id and settings:
                    duration_ms = int((time.monotonic() - started) * 1000)
                    asyncio.create_task(
                        log_pipeline_latency(
                            settings,
                            org_id=str(org_id),
                            stage_name=stage_name,
                            duration_ms=duration_ms,
                            message_id=str(message_id) if message_id else None,
                            cache_hit=cache_hit,
                            client=kwargs.get("client"),
                        )
                    )

        return wrapper

    return decorator
