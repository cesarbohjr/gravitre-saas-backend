"""Queue helpers for training and agent-execution jobs.

Falls back to local async queues when Redis/Upstash is not configured.
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

AGENT_EXECUTION_QUEUE = "gravitre:agent-execution"
_local_training_queue: asyncio.Queue[str] = asyncio.Queue()
_local_agent_queue: asyncio.Queue[str] = asyncio.Queue()
_queue_available: bool | None = None


@dataclass
class AgentExecutionJob:
    """Payload for an async agent/operator execution job."""

    job_id: str
    org_id: str
    user_id: str
    agent_id: str
    task: dict[str, Any]
    context: dict[str, Any]
    priority: int = 5
    timeout_seconds: int = 300
    max_retries: int = 3
    kind: str = "operator_task"
    environment: str = "production"
    session_id: str | None = None
    enqueued_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


def is_queue_available() -> bool:
    """Return True when Redis queue is configured and reachable."""
    global _queue_available  # noqa: PLW0603
    settings = get_settings()
    redis_url = (getattr(settings, "redis_url", "") or "").strip()
    if not redis_url:
        _queue_available = False
        return False
    if _queue_available is not None:
        return _queue_available
    try:
        import redis

        client = redis.from_url(redis_url, decode_responses=True, socket_connect_timeout=1.0)
        client.ping()
        client.close()
        _queue_available = True
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("agent execution queue unavailable: %s", str(exc))
        _queue_available = False
        return False


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
    await _local_training_queue.put(job_id)


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
        return await asyncio.wait_for(_local_training_queue.get(), timeout=timeout_seconds)
    except TimeoutError:
        return None


async def enqueue_agent_execution_job(job: AgentExecutionJob | str) -> None:
    """Enqueue an agent execution job (by id or full payload)."""
    settings = get_settings()
    payload = job if isinstance(job, str) else json.dumps(asdict(job))
    redis_url = (getattr(settings, "redis_url", "") or "").strip()
    if redis_url:
        try:
            from redis.asyncio import from_url

            client = from_url(redis_url, decode_responses=True)
            await client.rpush(AGENT_EXECUTION_QUEUE, payload)
            await client.aclose()
            global _queue_available  # noqa: PLW0603
            _queue_available = True
            return
        except Exception as exc:
            logger.warning("agent_queue_enqueue_failed fallback_local error=%s", str(exc))
    await _local_agent_queue.put(payload if isinstance(payload, str) else job.job_id)


async def dequeue_agent_execution_job(timeout_seconds: int = 5) -> str | None:
    """Dequeue an agent execution job id or JSON payload."""
    settings = get_settings()
    redis_url = (getattr(settings, "redis_url", "") or "").strip()
    if redis_url:
        try:
            from redis.asyncio import from_url

            client = from_url(redis_url, decode_responses=True)
            result = await client.blpop(AGENT_EXECUTION_QUEUE, timeout=timeout_seconds)
            await client.aclose()
            if result:
                _, raw = result
                return str(raw)
            return None
        except Exception as exc:
            logger.warning("agent_queue_dequeue_failed fallback_local error=%s", str(exc))
    try:
        return await asyncio.wait_for(_local_agent_queue.get(), timeout=timeout_seconds)
    except TimeoutError:
        return None


async def process_agent_execution_job(job_id: str) -> None:
    """Dequeue and execute a single agent job by database id."""
    from app.config import get_settings
    from app.operators import agent_jobs as jobs
    from app.workflows.repository import get_supabase_client

    settings = get_settings()
    client = get_supabase_client(settings)
    row = client.table("agent_jobs").select("*").eq("id", job_id).limit(1).execute().data
    if not row:
        logger.error("agent_execution_job_not_found job_id=%s", job_id)
        return
    job = row[0]
    handler = jobs._HANDLERS.get(job.get("kind") or "")
    timeout_s = int((job.get("payload") or {}).get("timeout_seconds") or 300)
    try:
        if handler is None:
            raise ValueError(f"no handler for kind={job.get('kind')}")
        result = await asyncio.wait_for(handler(settings, job), timeout=timeout_s)
        await asyncio.to_thread(jobs.complete_job, client, job["id"], result)
        try:
            from app.marketplace.adoption import maybe_record_agent_adoption

            await asyncio.to_thread(maybe_record_agent_adoption, client, job)
        except Exception as exc:  # noqa: BLE001
            logger.warning("marketplace adoption hook skipped job_id=%s error=%s", job_id, str(exc))
        logger.info("agent_execution_completed job_id=%s kind=%s", job_id, job.get("kind"))
    except TimeoutError:
        await asyncio.to_thread(
            jobs.fail_or_requeue_job, client, job, "execution_timeout"
        )
        logger.warning("agent_execution_timeout job_id=%s timeout_s=%s", job_id, timeout_s)
    except Exception as exc:  # noqa: BLE001
        logger.warning("agent_execution_failed job_id=%s error=%s", job_id, str(exc))
        await asyncio.to_thread(jobs.fail_or_requeue_job, client, job, str(exc))
