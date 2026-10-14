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
            "workflow_queue_fail_closed": True,
            "write_invoke_idempotency_enabled": True,
            "workflow_queue_max_delivery_attempts": 3,
        },
    )()
    monkeypatch.setattr(wq, "get_settings", lambda: settings)
    monkeypatch.setattr(wq, "is_queue_available", lambda: True)


@pytest.fixture(autouse=True)
async def _flush_redis():
    from redis.asyncio import from_url

    client = from_url(REDIS_URL, decode_responses=True)
    await client.delete(wq.WORKFLOW_RUN_QUEUE, wq.WORKFLOW_RUN_PROCESSING, wq.WORKFLOW_RUN_DEAD, wq.WORKFLOW_RUN_CLAIMS, wq.WORKFLOW_RUN_LEASES, wq.WORKFLOW_RUN_OWNERS)
    await client.aclose()
    yield


@pytest.mark.asyncio
@requires_redis
async def test_enqueue_dequeue_ack_removes_processing():
    raw = _job()
    await wq.enqueue_workflow_run(raw)
    dequeued = await wq.dequeue_workflow_run(timeout_seconds=1)
    assert wq._unpack_receipt(dequeued)[1] == raw
    from redis.asyncio import from_url

    client = from_url(REDIS_URL, decode_responses=True)
    assert await client.hlen(wq.WORKFLOW_RUN_CLAIMS) == 1
    await wq.acknowledge_workflow_run(dequeued)
    assert await client.hlen(wq.WORKFLOW_RUN_CLAIMS) == 0
    await client.aclose()


@pytest.mark.asyncio
@requires_redis
async def test_worker_death_leaves_processing_until_requeue():
    raw = _job()
    await wq.enqueue_workflow_run(raw)
    dequeued = await wq.dequeue_workflow_run(timeout_seconds=1)
    assert wq._unpack_receipt(dequeued)[1] == raw
    await wq.requeue_workflow_run(dequeued)
    from redis.asyncio import from_url

    client = from_url(REDIS_URL, decode_responses=True)
    assert await client.hlen(wq.WORKFLOW_RUN_CLAIMS) == 0
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
    assert await wq.dequeue_workflow_run(timeout_seconds=0) is None
    await wq.acknowledge_workflow_run(first)
    second = await wq.dequeue_workflow_run(timeout_seconds=1)
    assert wq._unpack_receipt(first)[1] == raw
    assert wq._unpack_receipt(second)[1] == raw
    assert first != second


@pytest.mark.asyncio
@requires_redis
async def test_poison_job_moves_to_dead_after_max_attempts():
    raw = _job(attempt=2)
    from redis.asyncio import from_url

    client = from_url(REDIS_URL, decode_responses=True)
    await wq.enqueue_workflow_run(raw)
    receipt = await wq.dequeue_workflow_run(timeout_seconds=1)
    await wq.requeue_workflow_run(receipt)
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
    assert wq._unpack_receipt(dequeued)[1] == raw
    await wq.requeue_workflow_run(dequeued)
    again = await wq.dequeue_workflow_run(timeout_seconds=1)
    assert again is not None
    payload = json.loads(wq._unpack_receipt(again)[1])
    assert payload["delivery_attempt"] == 1


@pytest.mark.asyncio
async def test_expired_claim_recovered_and_stale_ack_cannot_remove_new_owner():
    import time
    from redis.asyncio import from_url
    raw = _job()
    await wq.enqueue_workflow_run(raw)
    abandoned = await wq.dequeue_workflow_run(timeout_seconds=1)
    old_token, _ = wq._unpack_receipt(abandoned)
    async with from_url(REDIS_URL, decode_responses=True) as client:
        await client.zadd(wq.WORKFLOW_RUN_LEASES, {old_token: time.time() - 1})
    recovered = await wq.dequeue_workflow_run(timeout_seconds=1)
    new_token, payload = wq._unpack_receipt(recovered)
    assert old_token != new_token
    assert json.loads(payload)["delivery_attempt"] == 1
    await wq.acknowledge_workflow_run(abandoned)
    await wq.requeue_workflow_run(abandoned)
    async with from_url(REDIS_URL, decode_responses=True) as client:
        assert await client.hget(wq.WORKFLOW_RUN_CLAIMS, new_token) == payload
        assert await client.llen(wq.WORKFLOW_RUN_QUEUE) == 0


@pytest.mark.asyncio
async def test_live_claim_renewal_and_competing_consumers():
    import asyncio
    from redis.asyncio import from_url
    await wq.enqueue_workflow_run(_job())
    claims = await asyncio.gather(*(wq.dequeue_workflow_run(timeout_seconds=0) for _ in range(8)))
    owners = [claim for claim in claims if claim is not None]
    assert len(owners) == 1
    assert await wq.renew_workflow_run_claim(owners[0])
    assert await wq.dequeue_workflow_run(timeout_seconds=0) is None


@pytest.mark.asyncio
async def test_actual_process_death_recovers_durable_claim():
    import asyncio
    import subprocess
    import sys
    import time
    from redis.asyncio import from_url
    await wq.enqueue_workflow_run(_job())
    code = f"""
import asyncio, time
from types import SimpleNamespace
from app.workers import workflow_queue as wq
wq.get_settings = lambda: SimpleNamespace(redis_url={REDIS_URL!r}, workflow_queue_fail_closed=True)
wq.is_queue_available = lambda: True
receipt = asyncio.run(wq.dequeue_workflow_run(1))
print(receipt, flush=True)
time.sleep(60)
"""
    child = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, text=True)
    try:
        receipt = await asyncio.wait_for(asyncio.to_thread(child.stdout.readline), timeout=10)
        assert receipt.strip()
        child.kill()
        await asyncio.to_thread(child.wait)
        token, _ = wq._unpack_receipt(receipt)
        async with from_url(REDIS_URL, decode_responses=True) as client:
            assert await client.hlen(wq.WORKFLOW_RUN_CLAIMS) == 1
            await client.zadd(wq.WORKFLOW_RUN_LEASES, {token: time.time() - 1})
        recovered = await wq.dequeue_workflow_run(1)
        assert recovered is not None
        assert wq.parse_workflow_run_job(recovered).delivery_attempt == 1
    finally:
        if child.poll() is None:
            child.kill()
            child.wait()


@pytest.mark.asyncio
async def test_lease_loss_fences_new_provider_writes():
    import asyncio
    import time
    from redis.asyncio import from_url
    await wq.enqueue_workflow_run(_job())
    receipt = await wq.dequeue_workflow_run(1)
    token, _ = wq._unpack_receipt(receipt)
    with wq.workflow_run_claim(receipt):
        await asyncio.to_thread(wq.assert_current_workflow_claim_live)
        async with from_url(REDIS_URL, decode_responses=True) as client:
            await client.zadd(wq.WORKFLOW_RUN_LEASES, {token: time.time() - 1})
        with pytest.raises(RuntimeError, match="write refused"):
            await asyncio.to_thread(wq.assert_current_workflow_claim_live)
