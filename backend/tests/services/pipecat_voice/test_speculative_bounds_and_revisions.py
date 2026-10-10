"""Speculative generation: side-effect scope, bounds, counters, and versioned
request revisions with strict adoption (always on)."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from pipecat.frames.frames import InterimTranscriptionFrame, ProposedUserStoppedSpeakingFrame
from pipecat.processors.frame_processor import FrameDirection
from pipecat.utils.asyncio.task_manager import TaskManager
from pipecat.utils.base_object import BaseObject

from app.operators.stream_events import AssistantStreamEvent
from app.services.pipecat_voice.cognitive_llm import GravitreCognitiveLLMService, adopt_or_fresh
from app.services.pipecat_voice.speculative_generation import (
    RequestRevision,
    SpeculativeBounds,
    SpeculativeGenerationCoordinator,
    classify_revision_delta,
    compute_revision_versions,
    extract_request_constraints,
    start_speculative_run,
    strict_transcript_match,
    with_turn_inputs,
)
from app.services.pipecat_voice.speculative_prefetch import SpeculativePrefetchProcessor
from app.services.pipecat_voice.voice_latency_tuning import (
    resolve_voice_speculative_bounds,
    speculative_interim_breaks_run,
    voice_request_revisions_enabled,
)
from app.services.speculative_execution import (
    SpeculativeSideEffectBlocked,
    block_if_speculative,
    run_or_defer,
)
from tests.services.pipecat_voice.speculation_helpers import (
    adoptable,
    confirmed_turn_sees_matching_versions,
)


def _delta(text: str) -> AssistantStreamEvent:
    return AssistantStreamEvent(sse_type="text-delta", payload={"delta": text})


async def _events(*items):
    for item in items:
        yield item


def _bound(versions: Any, **overrides: Any):
    """Bind principal and prompt the way the confirmed test service will."""
    base: dict[str, Any] = dict(
        org_id="00000000-0000-4000-8000-000000000001",
        user_id="00000000-0000-4000-8000-000000000002",
        agent_id=None,
        turn_inputs={"assistant_base_prompt": None},
    )
    base.update(overrides)
    return with_turn_inputs(versions, **base)


def _versions(**overrides: Any):
    base = dict(
        conversation_id="conv-1",
        task_state={"pending_task": None},
        history=[{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}],
        history_summary=None,
    )
    base.update(overrides)
    return compute_revision_versions(**base)


# ---------------------------------------------------------------------------
# Side-effect scope wired into runs
# ---------------------------------------------------------------------------


class TestRunSideEffects:
    @pytest.mark.asyncio
    async def test_discarded_run_drops_its_deferred_writes(self):
        written: list[str] = []

        async def _write():
            written.append("task_state")

        async def _runner():
            await run_or_defer("conversation.task_state", _write)
            yield _delta("hi")

        coordinator = SpeculativeGenerationCoordinator()
        run = start_speculative_run(text="what is my revenue", runner=_runner, create_task=asyncio.ensure_future)
        coordinator.set_run(run)
        await run.task
        assert written == []
        assert coordinator.adopt("something else entirely") is None
        assert written == []
        assert coordinator.stats.discarded == 1
        assert coordinator.stats.deferred_writes_dropped == 1

    @pytest.mark.asyncio
    async def test_adopted_run_replays_its_deferred_writes_on_commit(self):
        written: list[str] = []

        async def _write():
            written.append("task_state")

        async def _runner():
            await run_or_defer("conversation.task_state", _write)
            yield _delta("hi")

        coordinator = SpeculativeGenerationCoordinator()
        run = start_speculative_run(text="what is my revenue", runner=_runner, create_task=asyncio.ensure_future)
        coordinator.set_run(run)
        await run.task
        adopted = coordinator.adopt("what is my revenue")
        assert adopted is run and written == []
        assert await adopted.commit() == 1
        assert written == ["task_state"]
        assert coordinator.stats.adopted == 1

    @pytest.mark.asyncio
    async def test_blocked_run_stops_and_is_never_adopted(self):
        produced: list[str] = []

        async def _runner():
            yield _delta("first")
            try:
                block_if_speculative("connector_write:email.send")
            except SpeculativeSideEffectBlocked:
                pass  # the brain swallows tool errors; the run is still poisoned
            produced.append("after-block")
            yield _delta("second")
            produced.append("never")

        coordinator = SpeculativeGenerationCoordinator()
        run = start_speculative_run(text="what is my revenue", runner=_runner, create_task=asyncio.ensure_future)
        coordinator.set_run(run)
        await run.task  # the producer stops itself; nothing more is generated
        assert run.outcome == "blocked"
        assert "never" not in produced
        assert coordinator.adopt("what is my revenue") is None
        assert coordinator.stats.blocked == 1

    @pytest.mark.asyncio
    async def test_adopt_or_fresh_redoes_a_turn_whose_commit_was_blocked(self):
        async def _adopted():
            raise SpeculativeSideEffectBlocked("approval")
            yield  # pragma: no cover

        async def _fresh():
            yield _delta("fresh answer")

        out = [e async for e in adopt_or_fresh(_adopted(), _fresh)]
        assert [e.payload["delta"] for e in out] == ["fresh answer"]


# ---------------------------------------------------------------------------
# Bounds and counters
# ---------------------------------------------------------------------------


class TestBounds:
    def test_default_bounds_are_on_and_clamped(self):
        assert resolve_voice_speculative_bounds(SimpleNamespace()) == SpeculativeBounds()
        wild = resolve_voice_speculative_bounds(
            SimpleNamespace(
                voice_speculative_timeout_s=999,
                voice_speculative_max_buffer_chars=1,
                voice_speculative_max_buffer_events=10**9,
            )
        )
        assert wild.timeout_s == 20.0 and wild.max_buffered_chars == 200 and wild.max_buffered_events == 4096

    def test_settings_defaults(self):
        from app.config import Settings

        fields = Settings.model_fields
        assert fields["voice_speculative_timeout_s"].default == 5.0
        assert fields["voice_speculative_max_buffer_chars"].default == 2000
        # Strict adoption no longer depends on the retired setting.
        assert voice_request_revisions_enabled(SimpleNamespace()) is True
        assert voice_request_revisions_enabled(SimpleNamespace(voice_request_revisions_v1=False)) is True

    @pytest.mark.asyncio
    async def test_unadopted_run_times_out_and_counts_wasted_time(self):
        hold = asyncio.Event()

        async def _runner():
            yield _delta("partial")
            await hold.wait()
            yield _delta("never")

        coordinator = SpeculativeGenerationCoordinator()
        run = start_speculative_run(
            text="what is my revenue",
            runner=_runner,
            create_task=asyncio.ensure_future,
            bounds=SpeculativeBounds(timeout_s=0.05),
        )
        coordinator.set_run(run)
        await asyncio.sleep(0.12)
        assert run.outcome == "timeout"
        assert run.task.cancelled() or run.task.done()
        assert coordinator.adopt("what is my revenue") is None
        assert coordinator.stats.timeouts == 1
        assert coordinator.stats.discarded == 1
        assert coordinator.stats.wasted_s >= 0.04

    @pytest.mark.asyncio
    async def test_timeout_never_cuts_an_adopted_run(self):
        hold = asyncio.Event()

        async def _runner():
            yield _delta("a")
            await hold.wait()
            yield _delta("b")

        coordinator = SpeculativeGenerationCoordinator()
        run = start_speculative_run(
            text="what is my revenue",
            runner=_runner,
            create_task=asyncio.ensure_future,
            bounds=SpeculativeBounds(timeout_s=0.05),
        )
        coordinator.set_run(run)
        assert coordinator.adopt("what is my revenue") is run
        await asyncio.sleep(0.1)
        hold.set()
        got = [e.payload["delta"] async for e in run.adopted_events()]
        assert got == ["a", "b"]
        assert coordinator.stats.timeouts == 0

    @pytest.mark.asyncio
    async def test_buffer_cap_pauses_the_producer_until_adoption(self):
        produced = 0

        async def _runner():
            nonlocal produced
            for _ in range(50):
                produced += 1
                yield _delta("x" * 10)

        coordinator = SpeculativeGenerationCoordinator()
        run = start_speculative_run(
            text="tell me a long story",
            runner=_runner,
            create_task=asyncio.ensure_future,
            bounds=SpeculativeBounds(timeout_s=5, max_buffered_chars=45),
        )
        coordinator.set_run(run)
        await asyncio.sleep(0.05)
        assert run.paused
        assert produced == 5  # 50 chars > 45: paused right there
        assert run.queue.qsize() <= 5
        assert coordinator.stats.buffer_pauses == 1
        adopted = coordinator.adopt("tell me a long story")
        got = [e async for e in adopted.adopted_events()]
        assert len(got) == 50

    @pytest.mark.asyncio
    async def test_confirmed_turn_cancels_a_non_adoptable_run_immediately(self):
        hold = asyncio.Event()

        async def _runner():
            yield _delta("a")
            await hold.wait()

        coordinator = SpeculativeGenerationCoordinator()
        run = start_speculative_run(text="what is my revenue", runner=_runner, create_task=asyncio.ensure_future)
        coordinator.set_run(run)
        await asyncio.sleep(0)
        assert coordinator.adopt("what is my pipeline") is None
        await asyncio.sleep(0)
        assert run.task.cancelled() or run.task.done()
        assert coordinator.last_reject_reason == "transcript_mismatch"


# ---------------------------------------------------------------------------
# Strict transcript check
# ---------------------------------------------------------------------------


class TestStrictTranscriptMatch:
    @pytest.mark.parametrize(
        "spec,final",
        [
            ("show me sessions last month", "show me sessions last month but not organic"),
            ("send it", "send it, actually don't"),
            ("yes", "yes, wait"),
            ("what is my revenue", "what is my revenue excluding refunds"),
            ("pull my pipeline", "pull my pipeline for Acme"),
            ("send it", "send items"),
            ("show me sessions last month", "show me sessions last month and last week"),
        ],
    )
    def test_meaning_changing_tails_are_rejected_even_with_v2_word_budget(self, spec, final):
        ok, reason = strict_transcript_match(spec, final, max_extra_words=3)
        assert not ok, reason

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "spec,final",
        [
            ("show me sessions last month", "show me sessions last month but not organic"),
            ("send it", "send it, actually don't"),
            ("yes", "yes, wait"),
        ],
    )
    async def test_closes_what_the_v2_word_count_rule_lets_through(self, spec, final):
        run = start_speculative_run(text=spec, runner=lambda: _events(), create_task=asyncio.ensure_future)
        await run.task
        assert run.matches(final, prefix_max_extra_words=3) is True  # v2: <= 3 extra words
        assert strict_transcript_match(spec, final, max_extra_words=3)[0] is False

    @pytest.mark.asyncio
    async def test_v2_prefix_rule_now_respects_word_boundaries(self):
        run = start_speculative_run(text="send it", runner=lambda: _events(), create_task=asyncio.ensure_future)
        await run.task
        assert run.matches("send items", prefix_max_extra_words=3) is False
        assert run.matches("send it now", prefix_max_extra_words=3) is True

    def test_turn_trace_record_carries_the_counters(self):
        from app.services.pipecat_voice.voice_turn_trace import VoiceTurnTrace

        trace = VoiceTurnTrace()
        trace.begin_turn()
        trace.set_turn_meta(speculative_outcome="fresh", speculation={"started": 2, "discarded": 2, "wasted_s": 0.4})
        trace.end_turn()
        record = trace.written[-1] if trace.written else trace.flush_pending()
        assert record["extra"]["speculation"]["wasted_s"] == 0.4

    def test_inert_tails_adopt_only_within_the_v2_budget(self):
        assert strict_transcript_match("what is two plus two", "What is two plus two, please?", max_extra_words=3) == (
            True,
            "inert_tail",
        )
        assert strict_transcript_match("what is two plus two", "what is two plus two please", max_extra_words=0)[0] is False
        assert strict_transcript_match("what is two plus two", "What is two plus two?", max_extra_words=0) == (
            True,
            "exact",
        )

    def test_constraints_come_from_the_existing_resolvers(self):
        c = extract_request_constraints("how many sessions from google analytics last month by source")
        assert c["time"] == "last_month"
        assert "google_analytics" in c["sources"]
        assert "sources" in c["breakdowns"]
        assert extract_request_constraints("yes")["continuation"] is True

    def test_revision_delta_flags_time_window_only_corrections(self):
        assert classify_revision_delta("show me sessions last month", "show me sessions last week") == "time_window_only"
        assert classify_revision_delta("show me sessions last month", "show me sessions last month but not organic") == "qualified"


# ---------------------------------------------------------------------------
# Versioned revisions in the coordinator
# ---------------------------------------------------------------------------


async def _finished_run(coordinator: SpeculativeGenerationCoordinator, text: str, versions=None):
    revision = coordinator.note_transcript(text)
    run = start_speculative_run(
        text=text, runner=lambda: _events(_delta("ok")), create_task=asyncio.ensure_future, revision=revision
    )
    run.versions = versions
    coordinator.set_run(run)
    await run.task
    return run


class TestVersionedAdoption:
    def test_revision_numbers_rise_only_on_word_changes(self):
        c = SpeculativeGenerationCoordinator()
        r1 = c.note_transcript("show me sessions")
        assert c.note_transcript("Show me sessions.").revision == r1.revision
        r2 = c.note_transcript("show me sessions last month")
        assert r2.revision == r1.revision + 1
        assert isinstance(r2, RequestRevision)

    @pytest.mark.asyncio
    async def test_all_bound_versions_must_match(self):
        c = SpeculativeGenerationCoordinator()
        await _finished_run(c, "what is my revenue", versions=_versions())
        assert c.adopt("what is my revenue", strict=True, versions=_versions()) is not None

        mismatches = {
            "conversation_id": _versions(conversation_id="conv-2"),
            "pending_task_version": _versions(task_state={"pending_task": {"id": "p1", "tool": "email"}}),
            "approval_version": _versions(task_state={"pending_task": None, "pending_action": {"kind": "approve"}}),
            "context_version": _versions(history=[{"role": "user", "content": "something else"}]),
        }
        for name, confirmed in mismatches.items():
            await _finished_run(c, "what is my revenue", versions=_versions())
            assert c.adopt("what is my revenue", strict=True, versions=confirmed) is None
            assert c.last_reject_reason == f"version_mismatch:{name}"

    @pytest.mark.asyncio
    async def test_unbound_run_is_not_adopted_in_strict_mode(self):
        c = SpeculativeGenerationCoordinator()
        await _finished_run(c, "what is my revenue", versions=None)
        assert c.adopt("what is my revenue", strict=True, versions=_versions()) is None
        assert c.last_reject_reason == "versions_unbound"

    @pytest.mark.asyncio
    async def test_newer_incompatible_revision_rejects(self):
        c = SpeculativeGenerationCoordinator()
        await _finished_run(c, "show me sessions last month", versions=_versions())
        c.note_transcript("show me sessions last month but not organic")
        assert c.adopt("show me sessions last month", strict=True, versions=_versions()) is None
        assert c.last_reject_reason.startswith("newer_revision")

    @pytest.mark.asyncio
    async def test_strict_rejection_records_the_delta(self):
        c = SpeculativeGenerationCoordinator()
        await _finished_run(c, "show me sessions last month", versions=_versions())
        assert c.adopt("show me sessions last week", prefix_max_extra_words=3, strict=True, versions=_versions()) is None
        assert c.last_revision_delta == "time_window_only"
        assert c.stats.rejected_revisions == 1

    @pytest.mark.asyncio
    async def test_v2_prefix_adoption_unchanged_when_flag_off(self):
        c = SpeculativeGenerationCoordinator()
        await _finished_run(c, "show me sessions last month")
        # v2 (word budget only) still adopts a 3-word tail without the flag...
        assert c.adopt("show me sessions last month by source", prefix_max_extra_words=3) is not None
        await _finished_run(c, "show me sessions last month", versions=_versions())
        # ...the strict check does not.
        assert (
            c.adopt("show me sessions last month by source", prefix_max_extra_words=3, strict=True, versions=_versions())
            is None
        )

    def test_ledger_changes_do_not_change_versions(self):
        a = _versions(task_state={"parameter_ledger": {"slots": {"a": 1}}})
        b = _versions(task_state={"parameter_ledger": {"slots": {"a": 2}}})
        assert a == b


class TestInterimCancellation:
    def test_strict_cancels_on_a_qualifier_that_v2_would_keep(self):
        spec, new = "show me sessions last month", "show me sessions last month but"
        assert speculative_interim_breaks_run(spec, new, strict=False, v2_enabled=True, max_extra_words=3) is False
        assert speculative_interim_breaks_run(spec, new, strict=True, v2_enabled=True, max_extra_words=3) is True

    def test_v1_cancels_on_any_change(self):
        assert speculative_interim_breaks_run("a b", "a b c", strict=False, v2_enabled=False, max_extra_words=0)


# ---------------------------------------------------------------------------
# Wiring: prefetch processor and confirmed turn
# ---------------------------------------------------------------------------


def _interim(text: str) -> InterimTranscriptionFrame:
    return InterimTranscriptionFrame(text=text, user_id="u1", timestamp="", language=None)


async def _processor(settings: Any, coordinator: SpeculativeGenerationCoordinator) -> SpeculativePrefetchProcessor:
    proc = SpeculativePrefetchProcessor(
        app_settings=settings,
        org_id="org-1",
        user_id="user-1",
        agent={"id": "agent-1"},
        conversation_id=None,
        speculative_coordinator=coordinator,
        min_chars=5,
    )
    await BaseObject.setup(proc, TaskManager())
    proc.push_frame = AsyncMock()
    proc._prefetch = AsyncMock()
    return proc


def _slow_intelligence():
    intelligence = SimpleNamespace()

    async def _stream(**_kwargs):
        yield _delta("ok")
        await asyncio.sleep(10)

    intelligence.execute_task_streaming = _stream
    return intelligence


class TestProcessorWiring:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("flag", [False, True])
    async def test_qualifier_interim_cancels_whatever_the_retired_flag_says(self, flag):
        settings = SimpleNamespace(voice_speculative_v2=True, voice_request_revisions_v1=flag)
        coordinator = SpeculativeGenerationCoordinator()
        proc = await _processor(settings, coordinator)
        await proc.process_frame(_interim("show me sessions last month"), FrameDirection.DOWNSTREAM)
        with patch("app.operators.agent_intelligence.get_agent_intelligence", return_value=_slow_intelligence()):
            await proc.process_frame(ProposedUserStoppedSpeakingFrame(), FrameDirection.DOWNSTREAM)
            await asyncio.sleep(0.02)
            assert coordinator.has_pending_run
            run = coordinator.pending_run
            assert run.bounds == SpeculativeBounds()
            assert run.revision is not None
            await proc.process_frame(_interim("show me sessions last month but"), FrameDirection.DOWNSTREAM)
        assert coordinator.has_pending_run is False
        coordinator.cancel()


class TestStartFailureNeverDropsTheFrame:
    @pytest.mark.asyncio
    async def test_proposed_stop_is_forwarded_even_if_starting_the_run_fails(self):
        coordinator = SpeculativeGenerationCoordinator()
        proc = await _processor(SimpleNamespace(), coordinator)
        await proc.process_frame(_interim("what is my revenue"), FrameDirection.DOWNSTREAM)
        with patch(
            "app.services.pipecat_voice.speculative_prefetch.start_speculative_run",
            side_effect=TypeError("unexpected keyword argument 'bounds'"),
        ):
            frame = ProposedUserStoppedSpeakingFrame()
            await proc.process_frame(frame, FrameDirection.DOWNSTREAM)
        assert any(call.args and call.args[0] is frame for call in proc.push_frame.await_args_list)
        assert coordinator.has_pending_run is False


class TestRunnerScope:
    @pytest.mark.asyncio
    async def test_brain_runs_inside_the_scope_but_barge_in_bookkeeping_does_not(self):
        from app.services.speculative_execution import current_scope

        seen: dict[str, Any] = {}
        coordinator = SpeculativeGenerationCoordinator()
        proc = await _processor(SimpleNamespace(), coordinator)

        async def _before_run():
            seen["before_run"] = current_scope()

        proc.before_run = _before_run
        intelligence = SimpleNamespace()

        async def _stream(**_kwargs):
            seen["brain"] = current_scope()
            yield _delta("ok")

        intelligence.execute_task_streaming = _stream
        await proc.process_frame(_interim("what is my revenue"), FrameDirection.DOWNSTREAM)
        with patch("app.operators.agent_intelligence.get_agent_intelligence", return_value=intelligence):
            await proc.process_frame(ProposedUserStoppedSpeakingFrame(), FrameDirection.DOWNSTREAM)
            await coordinator.pending_run.task
        assert seen["before_run"] is None
        assert seen["brain"] is coordinator.pending_run.scope
        coordinator.cancel()


def _service(settings: Any, coordinator: SpeculativeGenerationCoordinator):
    service = GravitreCognitiveLLMService(
        app_settings=settings,
        org_id="00000000-0000-4000-8000-000000000001",
        user_id="00000000-0000-4000-8000-000000000002",
        speculative_coordinator=coordinator,
    )
    deltas: list[str] = []

    async def _push(frame: Any, *_a: Any, **_k: Any) -> None:
        message = getattr(frame, "message", None)
        if isinstance(message, dict) and message.get("type") == "assistant_text":
            deltas.append(str(message.get("delta") or ""))

    service.push_frame = AsyncMock(side_effect=_push)
    service._push_llm_text = AsyncMock()
    service.start_ttfb_metrics = AsyncMock()
    service.stop_ttfb_metrics = AsyncMock()
    return service, deltas


class _Ctx:
    def get_messages(self) -> list[dict[str, Any]]:
        return [{"role": "user", "content": "what is two plus two"}]


class _Trace:
    def __init__(self) -> None:
        self.meta: dict[str, Any] = {}

    def __getattr__(self, _name: str):
        return lambda *a, **k: None

    def set_turn_meta(self, **kwargs: Any) -> None:
        self.meta.update({k: v for k, v in kwargs.items() if v is not None})


class TestConfirmedTurnWiring:
    @pytest.mark.asyncio
    async def test_adoption_replays_deferred_writes_and_reports_counters(self):
        written: list[str] = []

        async def _write():
            written.append("objective")

        async def _runner():
            await run_or_defer("kernel.active_objective", _write)
            yield _delta("Four.")

        coordinator = SpeculativeGenerationCoordinator()
        run = start_speculative_run(text="what is two plus two", runner=_runner, create_task=asyncio.ensure_future)
        coordinator.set_run(adoptable(run))
        await run.task
        assert written == []

        service, deltas = _service(SimpleNamespace(), coordinator)
        trace = _Trace()
        service._turn_trace = trace
        with confirmed_turn_sees_matching_versions(), patch(
            "app.operators.agent_intelligence.get_agent_intelligence"
        ) as intel:
            intel.return_value.execute_task_streaming = AsyncMock(side_effect=AssertionError("must adopt"))
            await service._run_gravitre_turn(_Ctx())

        assert written == ["objective"]
        assert any("four" in d.lower() for d in deltas)
        assert trace.meta["speculative_outcome"] == "adopted"
        spec = trace.meta["speculation"]
        assert spec["started"] == 1 and spec["adopted"] == 1 and spec["deferred_writes_replayed"] == 1

    @pytest.mark.asyncio
    async def test_revisions_flag_rejects_on_version_mismatch_and_runs_fresh(self):
        coordinator = SpeculativeGenerationCoordinator()
        run = await _finished_run(
            coordinator,
            "what is two plus two",
            versions=_bound(_versions(conversation_id=None, history=[{"role": "user", "content": "older context"}])),
        )
        service, deltas = _service(SimpleNamespace(voice_request_revisions_v1=True), coordinator)
        trace = _Trace()
        service._turn_trace = trace

        async def _fresh(**_kwargs: Any):
            yield _delta("Fresh four.")

        with patch("app.operators.agent_intelligence.get_agent_intelligence") as intel:
            intel.return_value.execute_task_streaming = _fresh
            await service._run_gravitre_turn(_Ctx())

        assert run.outcome == "discarded"
        assert trace.meta["speculative_outcome"] == "fresh"
        assert trace.meta["speculation"]["reject_reason"] == "version_mismatch:context_version"
        assert any("fresh four" in d.lower() for d in deltas)

    @pytest.mark.asyncio
    async def test_revisions_flag_adopts_when_every_version_matches(self):
        coordinator = SpeculativeGenerationCoordinator()
        await _finished_run(
            coordinator,
            "what is two plus two",
            versions=_bound(_versions(conversation_id=None, history=[], task_state=None)),
        )
        service, deltas = _service(SimpleNamespace(voice_request_revisions_v1=True), coordinator)
        with patch("app.operators.agent_intelligence.get_agent_intelligence") as intel:
            intel.return_value.execute_task_streaming = AsyncMock(side_effect=AssertionError("must adopt"))
            await service._run_gravitre_turn(_Ctx())
        assert coordinator.stats.adopted == 1


# ---------------------------------------------------------------------------
# The adoption contract (audit 2026-10-10, finding 3)
# ---------------------------------------------------------------------------


class TestAdoptionContract:
    @pytest.mark.asyncio
    async def test_two_unreadable_states_never_match(self):
        unknown = _bound(_versions(task_state={"_unavailable": True}))
        assert unknown.known is False
        c = SpeculativeGenerationCoordinator()
        await _finished_run(c, "what is two plus two", versions=unknown)
        assert c.adopt("what is two plus two", strict=True, versions=unknown) is None
        assert c.last_reject_reason == "versions_unknown"

    @pytest.mark.asyncio
    async def test_unreadable_confirmed_state_rejects_a_known_run(self):
        c = SpeculativeGenerationCoordinator()
        await _finished_run(c, "what is two plus two", versions=_bound(_versions()))
        unknown = _bound(_versions(task_state={"_unavailable": True}))
        assert c.adopt("what is two plus two", strict=True, versions=unknown) is None
        assert c.last_reject_reason == "versions_unknown"

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("field", "override"),
        [
            ("principal_version", {"user_id": "someone-else"}),
            ("principal_version", {"agent_id": "agent-2"}),
            ("prompt_version", {"turn_inputs": {"assistant_base_prompt": "new instructions"}}),
        ],
    )
    async def test_principal_or_prompt_changes_reject(self, field, override):
        c = SpeculativeGenerationCoordinator()
        await _finished_run(c, "what is two plus two", versions=_bound(_versions()))
        assert c.adopt("what is two plus two", strict=True, versions=_bound(_versions(), **override)) is None
        assert c.last_reject_reason == f"version_mismatch:{field}"

    @pytest.mark.asyncio
    async def test_matching_known_versions_adopt(self):
        c = SpeculativeGenerationCoordinator()
        run = await _finished_run(c, "what is two plus two", versions=_bound(_versions()))
        assert c.adopt("What is two plus two?", strict=True, versions=_bound(_versions())) is run

    @pytest.mark.parametrize(
        ("spec", "final"),
        [
            ("Compute 1.5 plus 2", "Compute 1 5 plus 2"),
            ("move it to -5", "move it to 5"),
            ("book 10/12", "book 10 12"),
            ("set the budget to $40", "set the budget to 40"),
            ("raise it 5%", "raise it 5"),
            ("send the report", "send the report again"),
        ],
    )
    def test_meaning_carrying_punctuation_and_again_are_preserved(self, spec, final):
        ok, _why = strict_transcript_match(spec, final, max_extra_words=3)
        assert ok is False

    @pytest.mark.parametrize(
        ("spec", "final"),
        [
            ("What is two plus two", "what is two plus two?"),
            ("Show me sessions, last month", "show me sessions last month."),
            ("revenue was 1,000 dollars", "Revenue was 1000 dollars"),
            ("show me sessions", "show me sessions please"),
            ("compute 1.5 plus 2", "Compute 1.5 plus 2."),
        ],
    )
    def test_benign_punctuation_case_and_inert_tails_still_adopt(self, spec, final):
        ok, _why = strict_transcript_match(spec, final, max_extra_words=3)
        assert ok is True


class TestAdoptedReplayOffTheFirstWord:
    @pytest.mark.asyncio
    async def test_first_buffered_event_does_not_wait_for_the_deferred_replay(self):
        """Audit finding 5: a 120 ms deferred write delayed the first adopted
        event by 120 ms. The replay now runs behind the first words, in order,
        and the turn still ends only after it lands."""
        release = asyncio.Event()
        order: list[str] = []

        async def _slow_write():
            await release.wait()
            order.append("deferred")

        async def _runner():
            await run_or_defer("kernel.active_objective", _slow_write)
            yield _delta("Four.")

        coordinator = SpeculativeGenerationCoordinator()
        run = start_speculative_run(text="what is two plus two", runner=_runner, create_task=asyncio.ensure_future)
        coordinator.set_run(adoptable(run))
        await run.task

        service, deltas = _service(SimpleNamespace(), coordinator)
        with confirmed_turn_sees_matching_versions(), patch(
            "app.operators.agent_intelligence.get_agent_intelligence"
        ) as intel:
            intel.return_value.execute_task_streaming = AsyncMock(side_effect=AssertionError("must adopt"))
            turn = asyncio.create_task(service._run_gravitre_turn(_Ctx()))
            for _ in range(200):
                if any("four" in d.lower() for d in deltas):
                    break
                await asyncio.sleep(0.01)
            assert any("four" in d.lower() for d in deltas), "first words before the replay finished"
            assert order == [] and not turn.done(), "the turn waits for the replay"
            release.set()
            await asyncio.wait_for(turn, timeout=5.0)
        assert order == ["deferred"]
        assert coordinator.stats.deferred_writes_replayed == 1

    @pytest.mark.asyncio
    async def test_a_blocked_run_still_fails_before_any_output(self):
        run = start_speculative_run(text="email sarah", runner=lambda: _events(_delta("Sent.")), create_task=asyncio.ensure_future)
        await run.task
        run.scope.mark_blocked("connector_write:email.send")
        with pytest.raises(SpeculativeSideEffectBlocked):
            run.start_commit()
