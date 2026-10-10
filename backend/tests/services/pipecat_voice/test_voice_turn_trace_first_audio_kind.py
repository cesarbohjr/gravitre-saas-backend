"""First audio is timed per kind, and first-speech SLO times the first ANSWER audio."""
from __future__ import annotations

import asyncio
from typing import Any

import pytest

from app.services.pipecat_voice import voice_turn_trace as vtt
from app.services.pipecat_voice.voice_turn_trace import (
    VoiceTurnTrace,
    first_speech_slo_sample,
)


class _Clock:
    def __init__(self) -> None:
        self.t = 100.0

    def __call__(self) -> float:
        return self.t

    def at(self, ms: float) -> float:
        self.t = 100.0 + ms / 1000.0
        return self.t


def _start(trace: VoiceTurnTrace, clock: _Clock) -> None:
    clock.at(0)
    trace.on_interim()
    clock.at(300)
    trace.on_stt_final()
    trace.on_user_stopped()
    clock.at(320)
    trace.begin_turn()


@pytest.mark.asyncio
async def test_filler_first_then_answer_slo_uses_the_answer() -> None:
    clock = _Clock()
    written: list[dict] = []
    trace = VoiceTurnTrace(writer=written.append, clock=clock)
    _start(trace, clock)
    # The acknowledgement plays at 900 ms; the observer e2e fires on it.
    clock.at(900)
    trace.on_bot_started_speaking()
    trace.on_first_audio_of_kind("filler", clock.t)
    trace.on_observer_breakdown(e2e_ms=600, ttfb_by_processor_ms={})
    clock.at(950)
    trace.on_client_playback_started(30)
    clock.at(2500)
    trace.note("first_token")
    trace.note("first_speakable")
    clock.at(2600)
    trace.end_turn()
    # The bridge is done and the playback report is in, but the answer has
    # not played yet: the record waits for it.
    assert written == []
    clock.at(3100)
    trace.on_first_audio_of_kind("answer", clock.t)

    assert len(written) == 1
    rec = written[0]
    d = rec["stage_durations_ms"]
    assert d["speech_end_to_first_filler_audio_ms"] == 900
    assert d["speech_end_to_first_answer_audio_ms"] == 3100
    assert "speech_end_to_first_progress_audio_ms" not in d
    assert rec["extra"]["first_audio_kind"] == "filler"
    # The observer said 600 ms (the filler); the answer came 2200 ms later.
    assert rec["first_speech"]["slo_ms"] == 600 + 2200
    assert rec["extra"]["first_audio_by_kind_e2e_ms"] == {"filler": 600, "answer": 2800}
    ms, extra = first_speech_slo_sample(rec)
    assert ms == 2800
    assert extra["first_filler_audio_ms"] == 600
    assert extra["first_audio_kind"] == "filler"
    assert extra["slo_basis"] == "first_answer_audio"


@pytest.mark.asyncio
async def test_answer_first_slo_equals_the_observer() -> None:
    clock = _Clock()
    written: list[dict] = []
    trace = VoiceTurnTrace(writer=written.append, clock=clock)
    _start(trace, clock)
    clock.at(800)
    trace.note("first_token")
    trace.note("first_speakable")
    clock.at(1000)
    trace.on_bot_started_speaking()
    trace.on_first_audio_of_kind("answer", clock.t)
    trace.on_observer_breakdown(e2e_ms=700, ttfb_by_processor_ms={})
    trace.end_turn()
    trace.on_client_playback_started(20)
    rec = written[0]
    assert rec["first_speech"]["slo_ms"] == 700
    assert first_speech_slo_sample(rec)[1]["first_audio_kind"] == "answer"


@pytest.mark.asyncio
async def test_turn_with_only_filler_has_no_slo_sample() -> None:
    clock = _Clock()
    written: list[dict] = []
    trace = VoiceTurnTrace(writer=written.append, clock=clock)
    _start(trace, clock)
    clock.at(900)
    trace.on_bot_started_speaking()
    trace.on_first_audio_of_kind("filler", clock.t)
    trace.on_observer_breakdown(e2e_ms=600, ttfb_by_processor_ms={})
    trace.on_client_playback_started(10)
    # Barge-in before any answer text: the next turn begins.
    trace.begin_turn()
    rec = written[0]
    assert rec["first_speech"]["slo_ms"] is None
    assert first_speech_slo_sample(rec) is None
    assert rec["stage_durations_ms"]["speech_end_to_first_filler_audio_ms"] == 900


@pytest.mark.asyncio
async def test_unlabelled_audio_keeps_the_observer_value() -> None:
    clock = _Clock()
    written: list[dict] = []
    trace = VoiceTurnTrace(writer=written.append, clock=clock)
    _start(trace, clock)
    clock.at(800)
    trace.note("first_speakable")
    clock.at(1000)
    trace.on_bot_started_speaking()
    trace.on_observer_breakdown(e2e_ms=700, ttfb_by_processor_ms={})
    trace.end_turn()
    trace.on_client_playback_started(20)
    rec = written[0]
    ms, extra = first_speech_slo_sample(rec)
    assert ms == 700
    assert extra["slo_basis"] == "first_audio_unlabelled"


@pytest.mark.asyncio
async def test_waiting_for_answer_audio_is_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(vtt, "ANSWER_AUDIO_GRACE_S", 0.02)
    monkeypatch.setattr(vtt, "PLAYBACK_REPORT_GRACE_S", 0.01)
    clock = _Clock()
    written: list[dict] = []
    trace = VoiceTurnTrace(writer=written.append, clock=clock)
    _start(trace, clock)
    clock.at(900)
    trace.on_bot_started_speaking()
    trace.on_first_audio_of_kind("filler", clock.t)
    trace.on_client_playback_started(10)
    trace.note("first_speakable")
    trace.end_turn()
    assert written == []
    await asyncio.sleep(0.06)
    assert len(written) == 1


def test_extra_facts_land_in_the_record() -> None:
    clock = _Clock()
    written: list[dict] = []
    trace = VoiceTurnTrace(writer=written.append, clock=clock)
    _start(trace, clock)
    trace.add_extra("answer_chunks_while_tool_pending", 2)
    trace.end_turn()
    assert written[0]["extra"]["answer_chunks_while_tool_pending"] == 2


@pytest.mark.asyncio
async def test_audit_writer_records_metric_a_from_the_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []

    def _slo(_settings: Any, **kwargs: Any) -> None:
        calls.append({"kind": "slo", **kwargs})

    def _critical(_settings: Any, **kwargs: Any) -> None:
        calls.append({"kind": "critical", **kwargs})

    monkeypatch.setattr(
        "app.services.pipecat_voice.voice_latency_metrics.record_voice_slo_metric", _slo
    )
    monkeypatch.setattr("app.services.turn_latency_trace.record_voice_turn_critical_path", _critical)
    write = vtt.audit_writer(object(), org_id="o", user_id="u", conversation_id_getter=lambda: "c")
    record = {
        "turn_id": "t",
        "first_speech": {
            "slo_ms": 2800,
            "first_audio_kind": "filler",
            "by_kind_e2e_ms": {"filler": 600, "answer": 2800},
        },
        "extra": {},
    }
    await write(record)
    slo = next(c for c in calls if c["kind"] == "slo")
    assert slo["ms"] == 2800
    assert slo["source"] == "duplex_first_speech"
    assert slo["extra"]["first_filler_audio_ms"] == 600
    assert any(c["kind"] == "critical" for c in calls)

    calls.clear()
    await write({"turn_id": "t2", "first_speech": {"slo_ms": None}, "extra": {}})
    assert [c["kind"] for c in calls] == ["critical"]


def test_pipeline_no_longer_records_metric_a_on_the_first_audio_of_any_kind() -> None:
    import inspect

    from app.services.pipecat_voice import pipeline as pipeline_module

    source = inspect.getsource(pipeline_module.build_pipecat_voice_task)
    assert "METRIC_A_ID" not in source
    assert "on_first_audio=turn_trace.on_first_audio_of_kind" in source
