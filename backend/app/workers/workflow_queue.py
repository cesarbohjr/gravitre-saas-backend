"""Durable workflow run queue with Redis fallback (STA-94)."""
from __future__ import annotations

import asyncio
import contextvars
from contextlib import contextmanager
import json
import logging
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.config import get_settings
from app.workers.queue import is_queue_available

logger = logging.getLogger(__name__)

WORKFLOW_RUN_QUEUE = "gravitre:workflow-runs"
WORKFLOW_RUN_PROCESSING = "gravitre:workflow-runs:processing"
WORKFLOW_RUN_CLAIMS = "gravitre:workflow-runs:claims"
WORKFLOW_RUN_LEASES = "gravitre:workflow-runs:leases"
WORKFLOW_RUN_OWNERS = "gravitre:workflow-runs:owners"
_current_claim: contextvars.ContextVar[str | None] = contextvars.ContextVar("workflow_queue_claim", default=None)
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


# Atomic movement is essential: separate pop/push loses work on process death.
_CLAIM = """
local payload = redis.call('LPOP', KEYS[1])
if not payload then return false end
local ok, job = pcall(cjson.decode, payload)
local runkey = ok and type(job) == 'table' and type(job.org_id) == 'string' and type(job.run_id) == 'string' and (job.org_id .. ':' .. job.run_id) or nil
if runkey and redis.call('HGET', KEYS[4], runkey) then
  redis.call('RPUSH', KEYS[1], payload)
  return false
end
if runkey then redis.call('HSET', KEYS[4], runkey, ARGV[1]) end
redis.call('HSET', KEYS[2], ARGV[1], payload)
local clock = redis.call('TIME')
local now = tonumber(clock[1]) + tonumber(clock[2]) / 1000000
redis.call('ZADD', KEYS[3], now + tonumber(ARGV[2]), ARGV[1])
return payload
"""
_ACK = """
if redis.call('HGET', KEYS[1], ARGV[1]) ~= ARGV[2] then return 0 end
local ok, job = pcall(cjson.decode, ARGV[2])
local runkey = ok and type(job) == 'table' and type(job.org_id) == 'string' and type(job.run_id) == 'string' and (job.org_id .. ':' .. job.run_id) or nil
if runkey and redis.call('HGET', KEYS[3], runkey) == ARGV[1] then redis.call('HDEL', KEYS[3], runkey) end
redis.call('HDEL', KEYS[1], ARGV[1])
redis.call('ZREM', KEYS[2], ARGV[1])
return 1
"""
_REQUEUE = """
if redis.call('HGET', KEYS[1], ARGV[1]) ~= ARGV[2] then return 0 end
if ARGV[4] ~= '' then
  local deadline = redis.call('ZSCORE', KEYS[2], ARGV[1])
  if not deadline or tonumber(deadline) > tonumber(ARGV[4]) then return 0 end
end
local ok, job = pcall(cjson.decode, ARGV[2])
local runkey = ok and type(job) == 'table' and type(job.org_id) == 'string' and type(job.run_id) == 'string' and (job.org_id .. ':' .. job.run_id) or nil
if runkey and redis.call('HGET', KEYS[4], runkey) == ARGV[1] then redis.call('HDEL', KEYS[4], runkey) end
redis.call('HDEL', KEYS[1], ARGV[1])
redis.call('ZREM', KEYS[2], ARGV[1])
redis.call('RPUSH', KEYS[3], ARGV[3])
return 1
"""
_RENEW = """
local deadline = redis.call('ZSCORE', KEYS[1], ARGV[1])
local clock = redis.call('TIME')
local now = tonumber(clock[1]) + tonumber(clock[2]) / 1000000
if not deadline or tonumber(deadline) <= now then return 0 end
redis.call('ZADD', KEYS[1], now + tonumber(ARGV[2]), ARGV[1])
return 1
"""


def _receipt(token: str, payload: str) -> str:
    return json.dumps({"_queue_claim": token, "_queue_payload": payload})


def _unpack_receipt(raw: str) -> tuple[str | None, str]:
    try:
        data = json.loads(raw)
        if isinstance(data, dict) and isinstance(data.get("_queue_payload"), str):
            return data.get("_queue_claim"), data["_queue_payload"]
    except (ValueError, TypeError):
        pass
    return None, raw


def workflow_queue_lease_seconds() -> float:
    return max(3.0, float(getattr(get_settings(), "workflow_queue_lease_seconds", 60) or 60))


async def dequeue_workflow_run(timeout_seconds: int = 5) -> str | None:
    settings = get_settings()
    redis_url = (getattr(settings, "redis_url", "") or "").strip()
    if redis_url and is_queue_available():
        try:
            from redis.asyncio import from_url
            async with from_url(redis_url, decode_responses=True) as client:
                stop = time.monotonic() + max(0, timeout_seconds)
                while True:
                    await _recover_expired_claims(client)
                    token = uuid.uuid4().hex
                    payload = await client.eval(_CLAIM, 4, WORKFLOW_RUN_QUEUE, WORKFLOW_RUN_CLAIMS,
                                                WORKFLOW_RUN_LEASES, WORKFLOW_RUN_OWNERS, token, workflow_queue_lease_seconds())
                    if payload is not None:
                        return _receipt(token, str(payload))
                    if time.monotonic() >= stop:
                        return None
                    await asyncio.sleep(min(0.1, max(0, stop - time.monotonic())))
        except Exception as exc:  # noqa: BLE001
            logger.warning("workflow_queue_dequeue_failed error=%s", str(exc))
            if _fail_closed(settings):
                return None
    if _fail_closed(settings):
        return None
    try:
        return await asyncio.wait_for(_local_queue.get(), timeout=max(0.01, timeout_seconds))
    except TimeoutError:
        return None


async def acknowledge_workflow_run(raw: str) -> None:
    token, payload = _unpack_receipt(raw)
    if not token:
        return  # local, explicitly non-durable development fallback
    from redis.asyncio import from_url
    async with from_url(get_settings().redis_url, decode_responses=True) as client:
        await client.eval(_ACK, 3, WORKFLOW_RUN_CLAIMS, WORKFLOW_RUN_LEASES, WORKFLOW_RUN_OWNERS, token, payload)


async def renew_workflow_run_claim(raw: str) -> bool:
    token, _ = _unpack_receipt(raw)
    if not token:
        return True
    from redis.asyncio import from_url
    async with from_url(get_settings().redis_url, decode_responses=True) as client:
        return bool(await client.eval(_RENEW, 1, WORKFLOW_RUN_LEASES, token, workflow_queue_lease_seconds()))


async def _recover_expired_claims(client: Any) -> None:
    seconds, micros = await client.time()
    now = seconds + micros / 1_000_000
    for token in await client.zrangebyscore(WORKFLOW_RUN_LEASES, "-inf", now, start=0, num=100):
        payload = await client.hget(WORKFLOW_RUN_CLAIMS, token)
        if payload is not None:
            await _requeue_claim(client, token, payload, expired_before=now)


def _bump_delivery_attempt(raw: str, *, max_attempts: int) -> tuple[str, bool]:
    """Increment delivery_attempt; return (payload, poisoned)."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return raw, True
    if not isinstance(data, dict):
        return raw, True
    try:
        attempt = int(data.get("delivery_attempt") or 0) + 1
    except (TypeError, ValueError):
        return raw, True
    data["delivery_attempt"] = attempt
    payload = json.dumps(data)
    return payload, attempt >= max(1, max_attempts)


async def _requeue_claim(client: Any, token: str, payload: str, *, expired_before: float | None = None) -> None:
    maximum = int(getattr(get_settings(), "workflow_queue_max_delivery_attempts", 5) or 5)
    next_payload, poisoned = _bump_delivery_attempt(payload, max_attempts=maximum)
    destination = WORKFLOW_RUN_DEAD if poisoned else WORKFLOW_RUN_QUEUE
    await client.eval(_REQUEUE, 4, WORKFLOW_RUN_CLAIMS, WORKFLOW_RUN_LEASES, destination, WORKFLOW_RUN_OWNERS,
                      token, payload, next_payload, "" if expired_before is None else expired_before)


async def requeue_workflow_run(raw: str) -> None:
    token, payload = _unpack_receipt(raw)
    if not token:
        return
    from redis.asyncio import from_url
    async with from_url(get_settings().redis_url, decode_responses=True) as client:
        await _requeue_claim(client, token, payload)


def parse_workflow_run_job(raw: str) -> WorkflowRunJob | None:
    try:
        _, payload = _unpack_receipt(raw)
        data = json.loads(payload)
        if isinstance(data, dict) and data.get("run_id"):
            return WorkflowRunJob(**data)
    except Exception:  # noqa: BLE001
        return None
    return None


@contextmanager
def workflow_run_claim(raw: str):
    token = _current_claim.set(raw)
    try:
        yield
    finally:
        _current_claim.reset(token)


def assert_current_workflow_claim_live() -> None:
    """Fence subsequent writes from a worker that lost ownership.

    The provider call already in flight is reconciled by the write ledger;
    this check prevents that old worker starting any further provider effects.
    """
    raw = _current_claim.get()
    if raw is None:
        return
    token, payload = _unpack_receipt(raw)
    if not token:
        return
    import redis
    settings = get_settings()
    if not bool(getattr(settings, "write_invoke_idempotency_enabled", False)):
        raise RuntimeError("Queued writes require write idempotency; write refused")
    with redis.from_url(settings.redis_url, decode_responses=True, socket_connect_timeout=2, socket_timeout=2) as client:
        clock = client.time()
        now = clock[0] + clock[1] / 1_000_000
        saved, expires = client.pipeline().hget(WORKFLOW_RUN_CLAIMS, token).zscore(WORKFLOW_RUN_LEASES, token).execute()
        if saved != payload or expires is None or expires <= now:
            raise RuntimeError("workflow queue claim lost; write refused")
