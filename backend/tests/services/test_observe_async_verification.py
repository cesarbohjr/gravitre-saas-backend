"""Async OBSERVE critic must not block non-write spoken delivery."""
from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, patch

import pytest

from app.services.verification_critic_service import schedule_verification_after_delivery
from app.services.voice_slo import verification_must_block_delivery


@pytest.mark.asyncio
async def test_schedule_verification_returns_immediately():
    """MUTATION PROOF: awaiting verify_before_delivery here would stall Metric B."""
    started = time.perf_counter()
    slow = AsyncMock()

    async def _slow(**_kwargs):
        await asyncio.sleep(0.25)

    slow.side_effect = _slow
    with patch(
        "app.services.verification_critic_service.get_verification_critic_service",
        return_value=type("S", (), {"verify_before_delivery": slow})(),
    ):
        out = schedule_verification_after_delivery(answer="plan ready", query="show the plan")
    elapsed = time.perf_counter() - started
    assert elapsed < 0.1, f"async critic blocked for {elapsed:.3f}s"
    assert out["skipped"] == "async_non_write_observe"
    assert out["blocking"] is False
    await asyncio.sleep(0.05)


def test_agent_intelligence_call_site_keeps_write_await():
    """MUTATION PROOF: deleting the await branch would skip write governance."""
    from pathlib import Path

    src = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "operators"
        / "agent_intelligence.py"
    ).read_text(encoding="utf-8")
    assert "schedule_verification_after_delivery" in src
    assert "elif not _block_critic:" in src
    assert "await get_verification_critic_service(active_settings).verify_before_delivery(" in src


def test_write_still_requires_blocking_path():
    """MUTATION PROOF: reverting the write gate would skip governance."""
    assert (
        verification_must_block_delivery(
            tool_results=[{"name": "hubspot.contacts.create", "success": True}],
            execution_verified=False,
            message="create the contact",
        )
        is True
    )
