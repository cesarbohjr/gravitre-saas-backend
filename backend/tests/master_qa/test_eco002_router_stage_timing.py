"""ECO-002: timing is opt-in, content-free and behavior-preserving."""
import asyncio
import logging

import pytest

from app.services.router_stage_timing import timed_router_stage, router_sample


@pytest.mark.asyncio
async def test_disabled_timing_preserves_result_without_emitting(monkeypatch, caplog):
    monkeypatch.delenv("GRAVITRE_ROUTER_STAGE_TIMING_ENABLED", raising=False)

    async def operation():
        return {"answer": "private user text"}

    with caplog.at_level(logging.INFO):
        assert await timed_router_stage("classification", "chat", operation()) == {"answer": "private user text"}
    assert "router_stage_timing" not in caplog.text


@pytest.mark.asyncio
async def test_enabled_timing_emits_bounded_labels_not_content(monkeypatch, caplog):
    monkeypatch.setenv("GRAVITRE_ROUTER_STAGE_TIMING_ENABLED", "1")
    secret = "PRIVATE-PROMPT-DO-NOT-LOG"

    async def operation():
        return secret

    with caplog.at_level(logging.INFO):
        assert await timed_router_stage("classification", secret, operation()) == secret
    assert "stage=classification" in caplog.text
    assert "surface=other" in caplog.text
    assert "duration_ms=" in caplog.text
    assert secret not in caplog.text


@pytest.mark.asyncio
async def test_error_propagates_and_is_recorded(monkeypatch, caplog):
    monkeypatch.setenv("GRAVITRE_ROUTER_STAGE_TIMING_ENABLED", "1")

    async def operation():
        raise RuntimeError("internal sensitive exception")

    with caplog.at_level(logging.INFO):
        with pytest.raises(RuntimeError, match="internal sensitive exception"):
            await timed_router_stage("context", "voice", operation())
    assert "outcome=error" in caplog.text
    assert "internal sensitive exception" not in caplog.text


@pytest.mark.asyncio
async def test_cancellation_is_not_swallowed(monkeypatch, caplog):
    monkeypatch.setenv("GRAVITRE_ROUTER_STAGE_TIMING_ENABLED", "1")

    async def operation():
        raise asyncio.CancelledError()

    with caplog.at_level(logging.INFO):
        with pytest.raises(asyncio.CancelledError):
            await timed_router_stage("enrichments", "agent", operation())
    assert "outcome=error" in caplog.text


@pytest.mark.asyncio
async def test_unknown_stage_rejected_without_running(monkeypatch):
    monkeypatch.setenv("GRAVITRE_ROUTER_STAGE_TIMING_ENABLED", "1")
    ran = False

    async def operation():
        nonlocal ran
        ran = True

    coro = operation()
    try:
        with pytest.raises(ValueError, match="Unknown routing timing stage"):
            await timed_router_stage("untrusted", "chat", coro)
    finally:
        coro.close()
    assert not ran


@pytest.mark.asyncio
async def test_synthetic_sample_correlates_and_resets(monkeypatch, caplog):
    monkeypatch.setenv("GRAVITRE_ROUTER_STAGE_TIMING_ENABLED", "1")

    async def operation():
        await asyncio.sleep(0)
        return "ok"

    with caplog.at_level(logging.INFO):
        with router_sample("ci-route-0001"):
            assert await timed_router_stage("classification", "chat", operation()) == "ok"
            assert await timed_router_stage("context", "chat", operation()) == "ok"
        assert await timed_router_stage("enrichments", "chat", operation()) == "ok"
    lines = [r.message for r in caplog.records if "router_stage_timing" in r.message]
    assert len(lines) == 3
    assert all("sample=ci-route-0001" in line for line in lines[:2])
    assert "sample=" not in lines[2]


@pytest.mark.asyncio
async def test_sample_rejects_unbounded_or_private_identifiers():
    with pytest.raises(ValueError, match="invalid synthetic sample identifier"):
        with router_sample("contains@email.example"):
            pass
    with pytest.raises(ValueError, match="invalid synthetic sample identifier"):
        with router_sample("x" * 49):
            pass
