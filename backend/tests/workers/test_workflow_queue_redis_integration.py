"""Workflow queue Redis integration (crash recovery, poison bounds, duplicate delivery)."""
from __future__ import annotations

import json
import os
import uuid

import pytest

pytest.importorskip("redis")

from app.workers import workflow_queue as wq

REDIS_URL = os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/15")
requires_redis = pytest.mark.skipif(
    os.environ.get("GRAVITRE_REQUIRE_REDIS") == "1" and not os.environ.get("REDIS_URL"),
    reason="GRAVITRE_REQUIRE_REDIS without REDIS_URL",
)


def _job(run_id: str | None = None, *, attempt: int = 0) -> str:
    rid = run_id or str(uuid.uuid4())
    return json.dumps(
        {
            "run_id": rid,
            "org_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            "workflow_id": "wf-1",
            "delivery_attempt": attempt,
        }
    )


@pytest.fixture(autouse=True)
def _settings(monkeypatch):
    settings = type(
        "S",
        (),
        {
            "redis_url": REDIS_URL,
            "workflow_queue_fail_closed": False,
            "workflow_queue_max_delivery_attempts": 3,
        },
    )()
    monkeypatch.setattr(wq, "get_settings", lambda: settings)
    monkeypatch.setattr(wq, "is_queue_available", lambda: True)


@pytest.fixture(autouse=True)
async def _flush_redis():
    from redis.asyncio import from_url

    client = from_url(REDIS_URL, decode_responses=True)
    await client.delete(wq.WORKFLOW_RUN_QUEUE, wq.WORKFLOW_RUN_PROCESSING, wq.WORKFLOW_RUN_DEAD)
    await client.aclose()
    yield


@pytest.mark.asyncio
@requires_redis
async def test_enqueue_dequeue_ack_removes_processing():
    raw = _job()
    await wq.enqueue_workflow_run(raw)
    dequeued = await wq.dequeue_workflow_run(timeout_seconds=1)
    assert dequeued == raw
    from redis.asyncio import from_url

    client = from_url(REDIS_URL, decode_responses=True)
    assert await client.llen(wq.WORKFLOW_RUN_PROCESSING) == 1
    await wq.acknowledge_workflow_run(raw)
    assert await client.llen(wq.WORKFLOW_RUN_PROCESSING) == 0
    await client.aclose()


@pytest.mark.asyncio
@requires_redis
async def test_worker_death_leaves_processing_until_requeue():
    raw = _job()
    await wq.enqueue_workflow_run(raw)
    assert await wq.dequeue_workflow_run(timeout_seconds=1) == raw
    await wq.requeue_workflow_run(raw)
    from redis.asyncio import from_url

    client = from_url(REDIS_URL, decode_responses=True)
    assert await client.llen(wq.WORKFLOW_RUN_PROCESSING) == 0
    assert await client.llen(wq.WORKFLOW_RUN_QUEUE) == 1
    await client.aclose()


@pytest.mark.asyncio
@requires_redis
async def test_duplicate_enqueue_delivers_twice():
    run_id = str(uuid.uuid4())
    raw = _job(run_id)
    await wq.enqueue_workflow_run(raw)
    await wq.enqueue_workflow_run(raw)
    first = await wq.dequeue_workflow_run(timeout_seconds=1)
    second = await wq.dequeue_workflow_run(timeout_seconds=1)
    assert first == raw
    assert second == raw


@pytest.mark.asyncio
@requires_redis
async def test_poison_job_moves_to_dead_after_max_attempts():
    raw = _job(attempt=2)
    from redis.asyncio import from_url

    client = from_url(REDIS_URL, decode_responses=True)
    await client.rpush(wq.WORKFLOW_RUN_PROCESSING, raw)
    await wq.requeue_workflow_run(raw)
    assert await client.llen(wq.WORKFLOW_RUN_DEAD) == 1
    assert await client.llen(wq.WORKFLOW_RUN_QUEUE) == 0
    dead_raw = await client.lindex(wq.WORKFLOW_RUN_DEAD, 0)
    payload = json.loads(dead_raw)
    assert payload["delivery_attempt"] == 3
    await client.aclose()


@pytest.mark.asyncio
@requires_redis
async def test_lost_ack_can_requeue_without_duplicating_main_queue():
    raw = _job()
    await wq.enqueue_workflow_run(raw)
    dequeued = await wq.dequeue_workflow_run(timeout_seconds=1)
    assert dequeued == raw
    await wq.requeue_workflow_run(dequeued)
    again = await wq.dequeue_workflow_run(timeout_seconds=1)
    assert again is not None
    payload = json.loads(again)
    assert payload["delivery_attempt"] == 1
