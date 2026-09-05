"""Voice-SLO follow-up (2026-09-05): SpeculativePrefetchProcessor's genuine
speculative-generation trigger on Deepgram Flux's ProposedUserStoppedSpeakingFrame.

Distinct from test_speculative_prefetch.py (which covers the original
READ-only cache-warming mechanism only) — these tests cover the second,
newer mechanism: starting a real, cancelable CognitiveTurnKernel reasoning
call via SpeculativeGenerationCoordinator.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pipecat.frames.frames import InterimTranscriptionFrame, ProposedUserStoppedSpeakingFrame
from pipecat.processors.frame_processor import FrameDirection
from pipecat.utils.asyncio.task_manager import TaskManager
from pipecat.utils.base_object import BaseObject

from app.services.pipecat_voice.speculative_generation import SpeculativeGenerationCoordinator
from app.services.pipecat_voice.speculative_prefetch import SpeculativePrefetchProcessor


def _interim(text: str) -> InterimTranscriptionFrame:
    return InterimTranscriptionFrame(text=text, user_id="u1", timestamp="", language=None)


async def _processor(**kwargs) -> SpeculativePrefetchProcessor:
    coordinator = kwargs.pop("speculative_coordinator", None)
    if coordinator is None:
        coordinator = SpeculativeGenerationCoordinator()
    proc = SpeculativePrefetchProcessor(
        app_settings=SimpleNamespace(),
        org_id="org-1",
        user_id="user-1",
        agent={"id": "agent-1"},
        conversation_id="conv-1",
        speculative_coordinator=coordinator,
        **kwargs,
    )
    await BaseObject.setup(proc, TaskManager())
    proc.push_frame = AsyncMock()
    # Avoid the (unrelated) read-only prefetch path doing real network/DB
    # work during these generation-focused tests.
    proc._prefetch = AsyncMock()
    return proc


def _fake_intelligence(events):
    intelligence = MagicMock()

    async def _stream(**kwargs):
        for event in events:
            yield event

    intelligence.execute_task_streaming = _stream
    return intelligence


class TestProbableEotStartsASpeculativeRun:
    @pytest.mark.asyncio
    async def test_proposed_stop_with_sufficient_partial_starts_a_run(self):
        coordinator = SpeculativeGenerationCoordinator()
        proc = await _processor(min_chars=5, speculative_coordinator=coordinator)
        await proc.process_frame(_interim("what is two plus two"), FrameDirection.DOWNSTREAM)

        with patch(
            "app.operators.agent_intelligence.get_agent_intelligence",
            return_value=_fake_intelligence(["ok"]),
        ):
            await proc.process_frame(ProposedUserStoppedSpeakingFrame(), FrameDirection.DOWNSTREAM)

        assert coordinator.has_pending_run is True

    @pytest.mark.asyncio
    async def test_proposed_stop_below_min_chars_does_not_start_a_run(self):
        coordinator = SpeculativeGenerationCoordinator()
        proc = await _processor(min_chars=12, speculative_coordinator=coordinator)
        await proc.process_frame(_interim("hi"), FrameDirection.DOWNSTREAM)
        await proc.process_frame(ProposedUserStoppedSpeakingFrame(), FrameDirection.DOWNSTREAM)

        assert coordinator.has_pending_run is False

    @pytest.mark.asyncio
    async def test_no_coordinator_configured_is_a_safe_no_op(self):
        """Non-Flux STT wires speculative_coordinator=None in pipeline.py —
        this must never raise."""
        proc = await _processor(min_chars=5, speculative_coordinator=None)
        await proc.process_frame(_interim("what is two plus two"), FrameDirection.DOWNSTREAM)
        await proc.process_frame(ProposedUserStoppedSpeakingFrame(), FrameDirection.DOWNSTREAM)  # must not raise

    @pytest.mark.asyncio
    async def test_duplicate_proposed_stop_with_no_new_interim_does_not_restart(self):
        """MUTATION PROOF: two Proposed-stop signals for the same unchanged
        partial (a real, observed Flux behavior) must not spawn a second,
        redundant reasoning call — remove the `_last_speculative_text` guard
        and this fails (call_count becomes 2).
        """
        coordinator = SpeculativeGenerationCoordinator()
        proc = await _processor(min_chars=5, speculative_coordinator=coordinator)
        await proc.process_frame(_interim("checking the pipeline"), FrameDirection.DOWNSTREAM)

        call_count = 0

        def _get_intelligence():
            nonlocal call_count
            call_count += 1
            return _fake_intelligence(["ok"])

        with patch("app.operators.agent_intelligence.get_agent_intelligence", side_effect=_get_intelligence):
            await proc.process_frame(ProposedUserStoppedSpeakingFrame(), FrameDirection.DOWNSTREAM)
            await asyncio.sleep(0.01)
            await proc.process_frame(ProposedUserStoppedSpeakingFrame(), FrameDirection.DOWNSTREAM)
            await asyncio.sleep(0.01)

        assert call_count == 1


class TestWriteShapedTextNeverSpeculativelyGenerates:
    @pytest.mark.asyncio
    async def test_write_shaped_partial_never_starts_a_speculative_run(self):
        """HARD CONSTRAINT: never speculatively run the full governed turn
        (tool routing, memory writes, write-governance staging) against
        unconfirmed, write-shaped text."""
        coordinator = SpeculativeGenerationCoordinator()
        proc = await _processor(min_chars=5, speculative_coordinator=coordinator)
        await proc.process_frame(
            _interim("Send an email to Sarah about the campaign"), FrameDirection.DOWNSTREAM
        )

        with patch(
            "app.operators.agent_intelligence.get_agent_intelligence",
        ) as mock_get_intel:
            await proc.process_frame(ProposedUserStoppedSpeakingFrame(), FrameDirection.DOWNSTREAM)

        mock_get_intel.assert_not_called()
        assert coordinator.has_pending_run is False


class TestContinuedSpeechCancelsThePendingRun:
    @pytest.mark.asyncio
    async def test_new_materially_different_interim_after_probable_eot_cancels_the_run(self):
        """MUTATION PROOF: the probable-EOT was wrong (the user kept
        talking) — the stale speculative run must be cancelled immediately,
        not left running to (harmlessly, but wastefully) completion.
        """
        coordinator = SpeculativeGenerationCoordinator()
        proc = await _processor(min_chars=5, speculative_coordinator=coordinator)
        await proc.process_frame(_interim("what is the weather"), FrameDirection.DOWNSTREAM)

        started = asyncio.Event()

        async def _slow_stream(**kwargs):
            started.set()
            await asyncio.sleep(10)
            yield "never"

        intelligence = MagicMock()
        intelligence.execute_task_streaming = _slow_stream

        with patch("app.operators.agent_intelligence.get_agent_intelligence", return_value=intelligence):
            await proc.process_frame(ProposedUserStoppedSpeakingFrame(), FrameDirection.DOWNSTREAM)
            await asyncio.wait_for(started.wait(), timeout=1.0)
            run_task = coordinator._run.task  # noqa: SLF001 — direct inspection for the mutation proof
            assert not run_task.done()

            await proc.process_frame(
                _interim("what is the weather in Chicago tomorrow"), FrameDirection.DOWNSTREAM
            )
            await asyncio.sleep(0.02)

        assert run_task.cancelled() or run_task.done()
        assert coordinator.has_pending_run is False
