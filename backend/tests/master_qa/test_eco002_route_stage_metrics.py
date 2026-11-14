"""ECO-002: instrumentation must not change routing behavior or leak dynamic labels."""
from __future__ import annotations

import asyncio
from unittest.mock import Mock

import pytest

from app.services import routing_stage_metrics as metrics


@pytest.mark.asyncio
async def test_disabled_timing_returns_original_result_without_metric_or_log(monkeypatch):
    monkeypatch.delenv("ECO002_ROUTING_LATENCY_TRACE", raising=False)
    spy = Mock()
    monkeypatch.setattr(metrics.ROUTE_STAGE_SECONDS, "labels", spy)

    async def action():
        return {"answer": "unchanged"}

    assert await metrics.measure("classification", action()) == {"answer": "unchanged"}
    spy.assert_not_called()


@pytest.mark.asyncio
async def test_enabled_timing_observes_static_stage_and_preserves_result(monkeypatch):
    monkeypatch.setenv("ECO002_ROUTING_LATENCY_TRACE", "true")
    observer = Mock()
    metric_labels = Mock(return_value=observer)
    monkeypatch.setattr(metrics.ROUTE_STAGE_SECONDS, "labels", metric_labels)

    async def action():
        await asyncio.sleep(0)
        return 42

    assert await metrics.measure("understanding", action()) == 42
    metric_labels.assert_called_once_with(stage="understanding", outcome="ok")
    observer.observe.assert_called_once()
    assert observer.observe.call_args.args[0] >= 0


@pytest.mark.asyncio
async def test_enabled_timing_preserves_failure_and_marks_error(monkeypatch):
    monkeypatch.setenv("ECO002_ROUTING_LATENCY_TRACE", "1")
    observer = Mock()
    metric_labels = Mock(return_value=observer)
    monkeypatch.setattr(metrics.ROUTE_STAGE_SECONDS, "labels", metric_labels)

    async def action():
        raise LookupError("sentinel")

    with pytest.raises(LookupError, match="sentinel"):
        await metrics.measure("context_assembly", action())
    metric_labels.assert_called_once_with(stage="context_assembly", outcome="error")
    observer.observe.assert_called_once()


@pytest.mark.asyncio
async def test_dynamic_stage_labels_are_rejected(monkeypatch):
    monkeypatch.setenv("ECO002_ROUTING_LATENCY_TRACE", "yes")

    async def action():
        return "unused"

    task = action()
    try:
        with pytest.raises(ValueError, match="Unrecognized static"):
            await metrics.measure("org_123_user_request_text", task)
    finally:
        task.close()
