"""The existing workflow worker runs the orphan sweep only when enabled."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest


@pytest.mark.asyncio
@pytest.mark.parametrize("enabled", [True, False])
async def test_worker_poll_invokes_orphan_detector_only_when_rollout_enabled(
    monkeypatch, enabled
):
    from app.workers import workflow_worker as worker
    from app.services import workflow_orphan_reconciler as orphan

    observed = []
    monkeypatch.setattr(
        orphan, "recover_one_stale_graph_run",
        lambda settings: observed.append(settings) or {"state": "no_candidate"},
    )

    async def stop_after_first_poll(*, timeout_seconds):
        raise asyncio.CancelledError

    monkeypatch.setattr(worker, "dequeue_workflow_run", stop_after_first_poll)
    settings = SimpleNamespace(
        workflow_orphan_recovery_enabled=enabled,
        workflow_orphan_recovery_interval_seconds=60,
    )
    with pytest.raises(asyncio.CancelledError):
        await worker._worker_loop(1, settings)
    assert observed == ([settings] if enabled else [])


def test_old_redis_worker_is_fenced_after_sql_recovery_takes_over(monkeypatch):
    import json
    import time

    import redis
    from app.workers import workflow_queue as queue
    from app.workflows import repository

    settings = SimpleNamespace(
        write_invoke_idempotency_enabled=True,
        redis_url="redis://fixture",
        workflow_orphan_recovery_enabled=True,
    )
    monkeypatch.setattr(queue, "get_settings", lambda: settings)
    payload = json.dumps({
        "run_id": "22222222-2222-4222-8222-222222222222",
        "org_id": "11111111-1111-4111-8111-111111111111",
        "workflow_id": "33333333-3333-4333-8333-333333333333",
    })
    raw = json.dumps({"_queue_claim": "token1", "_queue_payload": payload})

    class Pipeline:
        def hget(self, *_): return self
        def zscore(self, *_): return self
        def execute(self): return (payload, time.time() + 120)

    class Redis:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def time(self): return (int(time.time()), 0)
        def pipeline(self): return Pipeline()

    monkeypatch.setattr(redis, "from_url", lambda *a, **kw: Redis())
    status = ["paused"]

    class Query:
        def select(self, *_): return self
        def eq(self, *_): return self
        def limit(self, *_): return self
        def execute(self): return SimpleNamespace(data=[{"status": status[0]}])

    monkeypatch.setattr(
        repository, "get_supabase_client",
        lambda settings: SimpleNamespace(table=lambda name: Query()),
    )
    with queue.workflow_run_claim(raw):
        with pytest.raises(RuntimeError, match="parked or completed"):
            queue.assert_current_workflow_claim_live()
        status[0] = "running"
        queue.assert_current_workflow_claim_live()
