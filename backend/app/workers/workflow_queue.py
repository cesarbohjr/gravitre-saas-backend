"""Durable workflow run queue with Redis fallback (STA-94)."""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.config import get_settings
from app.workers.queue import is_queue_available

logger = logging.getLogger(__name__)

WORKFLOW_RUN_QUEUE = "gravitre:workflow-runs"
WORKFLOW_RUN_PROCESSING = "gravitre:workflow-runs:processing"
WORKFLOW_RUN_DEAD = "gravitre:workflow-runs:dead"
_local_queue: asyncio.Queue[str] = asyncio.Queue()


@dataclass
class WorkflowRunJob:
    run_id: str
    org_id: str
    workflow_id: str
    region: str = "us"
    idempotency_key: str | None = None
    delivery_attempt: int = 0
    enqueued_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


def _fail_closed(settings: Any) -> bool:
    return bool(getattr(settings, "workflow_queue_fail_closed", False))


async def enqueue_workflow_run(job: WorkflowRunJob | str) -> None:
    payload = job if isinstance(job, str) else json.dumps(asdict(job))
    settings = get_settings()
    redis_url = (getattr(settings, "redis_url", "") or "").strip()
    if redis_url and is_queue_available():
        try:
            from redis.asyncio import from_url

            client = from_url(redis_url, decode_responses=True)
            await client.rpush(WORKFLOW_RUN_QUEUE, payload)
            await client.aclose()
            return
        except Exception as exc:  # noqa: BLE001
            logger.warning("workflow_queue_enqueue_failed error=%s", str(exc))
            if _fail_closed(settings):
                raise RuntimeError("workflow queue enqueue failed; fail-closed") from exc
    if _fail_closed(settings):
        raise RuntimeError("workflow queue unavailable; fail-closed")
    await _local_queue.put(payload)


async def dequeue_workflow_run(timeout_seconds: int = 5) -> str | None:
    settings = get_settings()
    redis_url = (getattr(settings, "redis_url", "") or "").strip()
    if redis_url and is_queue_available():
        try:
            from redis.asyncio import from_url

            client = from_url(redis_url, decode_responses=True)
            popped = await client.blpop(WORKFLOW_RUN_QUEUE, timeout=timeout_seconds)
            if not popped:
                await client.aclose()
                return None
            _, raw = popped
            await client.rpush(WORKFLOW_RUN_PROCESSING, raw)
            await client.aclose()
            return str(raw)
        except Exception as exc:  # noqa: BLE001
            logger.warning("workflow_queue_dequeue_failed error=%s", str(exc))
            if _fail_closed(settings):
                return None
    if _fail_closed(settings):
        return None
    try:
        return await asyncio.wait_for(_local_queue.get(), timeout=timeout_seconds)
    except TimeoutError:
        return None


async def acknowledge_workflow_run(raw: str) -> None:
    """Remove a job from the processing list after successful execution."""
    settings = get_settings()
    redis_url = (getattr(settings, "redis_url", "") or "").strip()
    if not redis_url or not is_queue_available():
        return
    try:
        from redis.asyncio import from_url

        client = from_url(redis_url, decode_responses=True)
        await client.lrem(WORKFLOW_RUN_PROCESSING, 1, raw)
        await client.aclose()
    except Exception as exc:  # noqa: BLE001
        logger.warning("workflow_queue_ack_failed error=%s", str(exc))


def _bump_delivery_attempt(raw: str, *, max_attempts: int) -> tuple[str, bool]:
    """Increment delivery_attempt; return (payload, poisoned)."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return raw, False
    if not isinstance(data, dict):
        return raw, False
    attempt = int(data.get("delivery_attempt") or 0) + 1
    data["delivery_attempt"] = attempt
    payload = json.dumps(data)
    return payload, attempt >= max(1, max_attempts)


async def requeue_workflow_run(raw: str) -> None:
    """Return a failed/incomplete job to the main queue (bounded retries)."""
    settings = get_settings()
    redis_url = (getattr(settings, "redis_url", "") or "").strip()
    if not redis_url or not is_queue_available():
        return
    max_attempts = int(getattr(settings, "workflow_queue_max_delivery_attempts", 5) or 5)
    next_raw, poisoned = _bump_delivery_attempt(raw, max_attempts=max_attempts)
    try:
        from redis.asyncio import from_url

        client = from_url(redis_url, decode_responses=True)
        await client.lrem(WORKFLOW_RUN_PROCESSING, 1, raw)
        if poisoned:
            await client.rpush(WORKFLOW_RUN_DEAD, next_raw)
            logger.warning("workflow_queue_poison_job payload=%s", next_raw[:200])
        else:
            await client.rpush(WORKFLOW_RUN_QUEUE, next_raw)
        await client.aclose()
    except Exception as exc:  # noqa: BLE001
        logger.warning("workflow_queue_requeue_failed error=%s", str(exc))


def parse_workflow_run_job(raw: str) -> WorkflowRunJob | None:
    try:
        data = json.loads(raw)
        if isinstance(data, dict) and data.get("run_id"):
            return WorkflowRunJob(**data)
    except Exception:  # noqa: BLE001
        return None
    return None
