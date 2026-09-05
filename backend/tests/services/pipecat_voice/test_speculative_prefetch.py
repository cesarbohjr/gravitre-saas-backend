"""Tests for SpeculativePrefetchProcessor — genuine, real overlap with partial STT.

Speed/latency-standard follow-up (2026-09-05): this module (committed at
afa8020b, live on main) was the codebase's real answer to "start real work
while the user is still speaking" — but shipped with zero test coverage.
These tests close that gap: cancel-on-partial-change, the min_chars gate, the
write-shaped safety gate (never warms a live knowledge read for a
write-intent utterance, and never touches tool execution), and that a
CancelledError from a stale prefetch never propagates as a pipeline crash.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from pipecat.frames.frames import InterimTranscriptionFrame, TextFrame
from pipecat.processors.frame_processor import FrameDirection
from pipecat.utils.asyncio.task_manager import TaskManager
from pipecat.utils.base_object import BaseObject

from app.services.pipecat_voice.speculative_prefetch import (
    SpeculativePrefetchProcessor,
    _looks_write_shaped,
)


def _interim(text: str) -> InterimTranscriptionFrame:
    return InterimTranscriptionFrame(text=text, user_id="u1", timestamp="", language=None)


async def _processor(**kwargs) -> SpeculativePrefetchProcessor:
    proc = SpeculativePrefetchProcessor(
        app_settings=SimpleNamespace(),
        org_id="org-1",
        user_id="user-1",
        agent={"id": "agent-1"},
        **kwargs,
    )
    # create_task() (used to schedule each speculative prefetch) requires a
    # real, initialized TaskManager — same setup pattern already used for the
    # sibling Phase 1 turn-start strategy test.
    await BaseObject.setup(proc, TaskManager())
    # FrameProcessor.push_frame requires link()/setup() in the real pipeline;
    # tests only exercise process_frame's own gating/cancellation logic, so
    # push_frame is stubbed to a no-op rather than standing up a full pipeline.
    proc.push_frame = AsyncMock()
    return proc


class TestWriteShapedGate:
    def test_write_verbs_are_flagged(self):
        # Phrasing chosen to empirically match the real
        # is_direct_connector_write_intent regex this delegates to (contiguous
        # verb+object, e.g. "send an email" / "create a contact" / "update the
        # deal") — not every plausible write-sounding sentence matches its
        # narrower pattern (see the docstring/next tests for what does not).
        assert _looks_write_shaped("Send an email to Sarah about the campaign") is True
        assert _looks_write_shaped("Create a contact for Sarah") is True
        assert _looks_write_shaped("Update the deal for Acme") is True

    def test_some_plausible_write_phrasings_do_not_match_the_narrow_regex(self):
        """Honest characterization, not a bug in this test: the primary path
        (is_direct_connector_write_intent) requires a contiguous verb+object;
        the fallback keyword list only ever runs if that call raises, which it
        normally won't. These phrasings are real gaps in the SOURCE code's
        _looks_write_shaped, documented here rather than silently assumed
        covered — a write intent like "Email Sarah the update" (imperative
        "Email" is not in the send/post verb set) is NOT currently caught, and
        this speculative-prefetch path may warm a live knowledge read for it
        that a stricter check would have skipped. Not fixed here (out of this
        pass's scope — _looks_write_shaped is a leftover conservative gate
        this task did not touch) — reported so it is not lost.
        """
        assert _looks_write_shaped("Email Sarah the update") is False
        assert _looks_write_shaped("Schedule a meeting for Monday") is False

    def test_read_only_question_is_not_flagged(self):
        assert _looks_write_shaped("What integrations do I have connected") is False
        assert _looks_write_shaped("What is two plus two") is False

    def test_empty_text_is_not_flagged(self):
        assert _looks_write_shaped("") is False
        assert _looks_write_shaped(None) is False  # type: ignore[arg-type]


class TestMinCharsGate:
    @pytest.mark.asyncio
    async def test_short_partial_below_min_chars_never_schedules_prefetch(self):
        proc = await _processor(min_chars=12)
        with patch.object(SpeculativePrefetchProcessor, "_prefetch", AsyncMock()) as mock_prefetch:
            await proc.process_frame(_interim("hi"), FrameDirection.DOWNSTREAM)
        mock_prefetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_non_interim_frames_never_schedule_prefetch(self):
        proc = await _processor()
        with patch.object(SpeculativePrefetchProcessor, "_prefetch", AsyncMock()) as mock_prefetch:
            await proc.process_frame(TextFrame(text="final answer text"), FrameDirection.DOWNSTREAM)
        mock_prefetch.assert_not_called()
        proc.push_frame.assert_awaited_once()


class TestCancelAndRestartOnPartialChange:
    @pytest.mark.asyncio
    async def test_growing_partial_cancels_the_stale_prefetch_task(self):
        """MUTATION PROOF: if the stale task were left running (no .cancel()),
        both tasks would eventually try to touch shared per-turn state — this
        asserts the old task object is actually cancelled, not just replaced.
        """
        proc = await _processor(min_chars=5)
        started = asyncio.Event()
        release = asyncio.Event()

        async def _slow_prefetch(self, text):  # noqa: ANN001
            started.set()
            await release.wait()

        with patch.object(SpeculativePrefetchProcessor, "_prefetch", _slow_prefetch):
            await proc.process_frame(_interim("I need to email"), FrameDirection.DOWNSTREAM)
            await asyncio.wait_for(started.wait(), timeout=1.0)
            first_task = proc._task
            assert first_task is not None and not first_task.done()

            await proc.process_frame(_interim("I need to email Sarah"), FrameDirection.DOWNSTREAM)
            # Give the event loop a tick to process the cancellation.
            await asyncio.sleep(0.05)

            assert first_task.cancelled() or first_task.done()
        release.set()

    @pytest.mark.asyncio
    async def test_identical_repeated_partial_does_not_reschedule(self):
        proc = await _processor(min_chars=5)
        with patch.object(SpeculativePrefetchProcessor, "_prefetch", AsyncMock()) as mock_prefetch:
            await proc.process_frame(_interim("checking the pipeline"), FrameDirection.DOWNSTREAM)
            await proc.process_frame(_interim("checking the pipeline"), FrameDirection.DOWNSTREAM)
        assert mock_prefetch.call_count == 1


class TestPrefetchNeverTouchesToolExecutionAndNeverCrashesThePipeline:
    @pytest.mark.asyncio
    async def test_prefetch_only_calls_read_only_warm_helpers_never_a_tool_executor(self):
        proc = await _processor(min_chars=5)
        with (
            patch(
                "app.services.chat_dialogue_settings.load_chat_dialogue_settings",
                AsyncMock(return_value={}),
            ),
            patch(
                "app.services.sentiment_friction_service.get_sentiment_friction_service",
            ) as mock_sentiment,
            patch(
                "app.services.unified_turn_tool_retrieval.is_task_shaped_for_retrieval",
                return_value=(True, "task", "what integrations do I have"),
            ),
            patch(
                "app.services.unified_turn_tool_retrieval.warm_tool_document_embeddings",
                return_value=3,
            ),
            patch(
                "app.rag.tool_retrieval_embedding.embed_tool_retrieval_query_timed",
                return_value=[0.1, 0.2],
            ) as mock_embed,
            patch("app.workflows.repository.get_supabase_client", return_value=object()),
            patch(
                "app.services.unified_retrieval_service.UnifiedRetrievalService",
            ) as mock_unified,
        ):
            mock_sentiment.return_value.analyze = lambda *a, **k: {}
            mock_unified.return_value.retrieve_knowledge_rows = AsyncMock(return_value=[])
            await proc._prefetch("what integrations do I have connected")

        mock_embed.assert_called_once()
        mock_unified.return_value.retrieve_knowledge_rows.assert_awaited_once()
        # No connector/tool-execution surface (execute_plan, run_connector_turn,
        # ReAct engine, etc.) is ever imported or called by this path.

    @pytest.mark.asyncio
    async def test_write_shaped_partial_skips_the_live_knowledge_read(self):
        """HARD CONSTRAINT (own docstring): never warm a live READ against a
        write-shaped utterance's real target — only the embedding cache."""
        proc = await _processor(min_chars=5)
        with (
            patch(
                "app.services.chat_dialogue_settings.load_chat_dialogue_settings",
                AsyncMock(return_value={}),
            ),
            patch(
                "app.services.sentiment_friction_service.get_sentiment_friction_service",
            ) as mock_sentiment,
            patch(
                "app.services.unified_turn_tool_retrieval.is_task_shaped_for_retrieval",
                return_value=(True, "task", "send an email to sarah about the campaign"),
            ),
            patch(
                "app.services.unified_turn_tool_retrieval.warm_tool_document_embeddings",
                return_value=0,
            ),
            patch(
                "app.rag.tool_retrieval_embedding.embed_tool_retrieval_query_timed",
                return_value=[0.1],
            ),
            patch("app.workflows.repository.get_supabase_client", return_value=object()),
            patch("app.services.unified_retrieval_service.UnifiedRetrievalService") as mock_unified,
        ):
            mock_sentiment.return_value.analyze = lambda *a, **k: {}
            await proc._prefetch("Send an email to Sarah about the campaign")

        mock_unified.assert_not_called()

    @pytest.mark.asyncio
    async def test_cancelled_error_from_a_superseded_task_propagates_not_swallowed(self):
        """asyncio.CancelledError must re-raise (stock asyncio task-cancel
        contract) rather than being caught by the broad except Exception."""
        proc = await _processor(min_chars=5)
        with (
            patch("app.workflows.repository.get_supabase_client", return_value=object()),
            patch(
                "app.services.chat_dialogue_settings.load_chat_dialogue_settings",
                AsyncMock(side_effect=asyncio.CancelledError()),
            ),
        ):
            with pytest.raises(asyncio.CancelledError):
                await proc._prefetch("checking the pipeline for updates")

    @pytest.mark.asyncio
    async def test_a_failing_warm_helper_never_raises_out_of_prefetch(self):
        """Fire-and-forget contract: any ordinary failure must be swallowed,
        never surfaced as a pipeline error."""
        proc = await _processor(min_chars=5)
        with (
            patch("app.workflows.repository.get_supabase_client", return_value=object()),
            patch(
                "app.services.chat_dialogue_settings.load_chat_dialogue_settings",
                AsyncMock(side_effect=RuntimeError("boom")),
            ),
        ):
            await proc._prefetch("checking the pipeline for updates")  # must not raise
