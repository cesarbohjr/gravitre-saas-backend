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
_local_queue: asyncio.Queue[str] = asyncio.Queue()


@dataclass
class WorkflowRunJob:
    run_id: str
    org_id: str
    workflow_id: str
    region: str = "us"
    idempotency_key: str | None = None
    enqueued_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


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
            logger.warning("workflow_queue_enqueue_failed fallback_local error=%s", str(exc))
    await _local_queue.put(payload)


async def dequeue_workflow_run(timeout_seconds: int = 5) -> str | None:
    settings = get_settings()
    redis_url = (getattr(settings, "redis_url", "") or "").strip()
    if redis_url and is_queue_available():
        try:
            from redis.asyncio import from_url

            client = from_url(redis_url, decode_responses=True)
            result = await client.blpop(WORKFLOW_RUN_QUEUE, timeout=timeout_seconds)
            await client.aclose()
            if result:
                _, raw = result
                return str(raw)
            return None
        except Exception as exc:  # noqa: BLE001
            logger.warning("workflow_queue_dequeue_failed fallback_local error=%s", str(exc))
    try:
        return await asyncio.wait_for(_local_queue.get(), timeout=timeout_seconds)
    except TimeoutError:
        return None


def parse_workflow_run_job(raw: str) -> WorkflowRunJob | None:
    try:
        data = json.loads(raw)
        if isinstance(data, dict) and data.get("run_id"):
            return WorkflowRunJob(**data)
    except Exception:  # noqa: BLE001
        return None
    return None
