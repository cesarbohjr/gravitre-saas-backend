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
