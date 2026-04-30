"""Queue helpers for training jobs.

Falls back to local async queue when Redis/Upstash is not configured.
"""
from __future__ import annotations

import asyncio

from app.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_local_queue: asyncio.Queue[str] = asyncio.Queue()


async def enqueue_training_job(job_id: str) -> None:
    """Enqueue a training job identifier."""
    settings = get_settings()
    redis_url = (getattr(settings, "redis_url", "") or "").strip()
    if redis_url:
        try:
            from redis.asyncio import from_url

            client = from_url(redis_url, decode_responses=True)
            await client.rpush("gravitre:training_jobs", job_id)
            await client.aclose()
            return
        except Exception as exc:
            logger.warning("redis_enqueue_failed fallback_local error=%s", str(exc))
    await _local_queue.put(job_id)


async def dequeue_training_job(timeout_seconds: int = 5) -> str | None:
    """Dequeue a training job identifier."""
    settings = get_settings()
    redis_url = (getattr(settings, "redis_url", "") or "").strip()
    if redis_url:
        try:
            from redis.asyncio import from_url

            client = from_url(redis_url, decode_responses=True)
            result = await client.blpop("gravitre:training_jobs", timeout=timeout_seconds)
            await client.aclose()
            if result:
                _, job_id = result
                return str(job_id)
            return None
        except Exception as exc:
            logger.warning("redis_dequeue_failed fallback_local error=%s", str(exc))
    try:
        return await asyncio.wait_for(_local_queue.get(), timeout=timeout_seconds)
    except TimeoutError:
        return None
