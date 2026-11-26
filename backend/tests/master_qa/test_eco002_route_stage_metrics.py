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


@pytest.mark.asyncio
async def test_telemetry_failure_cannot_replace_successful_router_result(monkeypatch):
    monkeypatch.setenv("ECO002_ROUTING_LATENCY_TRACE", "true")

    def unavailable_collector(**kwargs):
        raise RuntimeError("metrics endpoint unavailable")

    monkeypatch.setattr(metrics.ROUTE_STAGE_SECONDS, "labels", unavailable_collector)

    async def action():
        return {"approved_route": "unchanged"}

    assert await metrics.measure("response_dispatch", action()) == {
        "approved_route": "unchanged",
    }


@pytest.mark.asyncio
async def test_telemetry_failure_cannot_mask_router_exception(monkeypatch):
    monkeypatch.setenv("ECO002_ROUTING_LATENCY_TRACE", "true")
    monkeypatch.setattr(
        metrics.ROUTE_STAGE_SECONDS, "labels",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("collector down")),
    )

    async def action():
        raise PermissionError("governed dispatch denied")

    with pytest.raises(PermissionError, match="governed dispatch denied"):
        await metrics.measure("response_dispatch", action())


@pytest.mark.asyncio
async def test_log_sink_failure_preserves_routing_result(monkeypatch):
    monkeypatch.setenv("ECO002_ROUTING_LATENCY_TRACE", "true")
    monkeypatch.setattr(metrics.ROUTE_STAGE_SECONDS, "labels", Mock(return_value=Mock()))
    monkeypatch.setattr(
        metrics.logger, "info",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("logger unavailable")),
    )

    async def action():
        return 42

    assert await metrics.measure("classification", action()) == 42


@pytest.mark.asyncio
async def test_cancelled_stage_is_recorded_separately_and_propagated(monkeypatch):
    monkeypatch.setenv("ECO002_ROUTING_LATENCY_TRACE", "true")
    observer = Mock()
    labels = Mock(return_value=observer)
    monkeypatch.setattr(metrics.ROUTE_STAGE_SECONDS, "labels", labels)

    async def action():
        raise asyncio.CancelledError()

    with pytest.raises(asyncio.CancelledError):
        await metrics.measure("response_dispatch", action())
    labels.assert_called_once_with(stage="response_dispatch", outcome="cancelled")
    observer.observe.assert_called_once()


@pytest.mark.asyncio
async def test_collector_failure_does_not_mask_cancellation(monkeypatch):
    monkeypatch.setenv("ECO002_ROUTING_LATENCY_TRACE", "true")
    monkeypatch.setattr(
        metrics.ROUTE_STAGE_SECONDS, "labels",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("collector down")),
    )

    async def action():
        raise asyncio.CancelledError()

    with pytest.raises(asyncio.CancelledError):
        await metrics.measure("response_dispatch", action())


@pytest.mark.asyncio
async def test_independent_model_and_overview_reads_overlap_without_dispatch(monkeypatch):
    import threading
    from types import SimpleNamespace
    from app.services.intelligence_router import IntelligenceRouter
    from app.services import intelligence_overview_policy

    model_started = threading.Event()
    policy_started = threading.Event()
    release = threading.Event()
    calls = []
    async def select(org_id, classification):
        calls.append(("model", org_id, classification))
        model_started.set()
        assert await asyncio.to_thread(release.wait, 3)
        return {"model": "fixture"}
    def policy(org_id, settings):
        calls.append(("policy", org_id))
        policy_started.set()
        assert release.wait(3)
        return {"contextual": "balanced"}
    monkeypatch.setattr(intelligence_overview_policy, "load_overview_policy", policy)
    monkeypatch.setenv("VOICE_CONTEXT_IO_OFFLOAD", "true")
    router = object.__new__(IntelligenceRouter)
    router.settings = SimpleNamespace()
    router._model_selector = SimpleNamespace(select=select)
    classification = {"requires_action": True}
    task = asyncio.create_task(router._select_model_and_overview("tenant-A", classification))
    try:
        assert await asyncio.to_thread(model_started.wait, 2)
        assert await asyncio.to_thread(policy_started.wait, 2)
        assert not task.done()
    finally:
        release.set()
    assert await task == ({"model": "fixture"}, {"contextual": "balanced"})
    assert ("model", "tenant-A", classification) in calls and ("policy", "tenant-A") in calls


@pytest.mark.asyncio
async def test_model_denial_propagates_and_optional_task_is_drained(monkeypatch):
    from types import SimpleNamespace
    from app.services.intelligence_router import IntelligenceRouter
    from app.services import intelligence_overview_policy
    async def deny(*args):
        raise PermissionError("model scope denied")
    monkeypatch.setattr(intelligence_overview_policy, "load_overview_policy", lambda *_: {})
    router = object.__new__(IntelligenceRouter)
    router.settings = SimpleNamespace()
    router._model_selector = SimpleNamespace(select=deny)
    with pytest.raises(PermissionError, match="model scope denied"):
        await router._select_model_and_overview("tenant-A", {})
