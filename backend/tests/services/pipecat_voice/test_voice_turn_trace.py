"""One latency record per spoken turn (voice_turn_trace.VoiceTurnTrace)."""
from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest
from pipecat.frames.frames import (
    BotStartedSpeakingFrame,
    EagerTranscriptionFrame,
    InterimTranscriptionFrame,
    ProposedUserStoppedSpeakingFrame,
    TranscriptionFrame,
    TTSAudioRawFrame,
)
from pipecat.observers.base_observer import FramePushed
from pipecat.processors.frame_processor import FrameDirection

from app.services.pipecat_voice import voice_turn_trace as vtt
from app.services.pipecat_voice.json_audio_serializer import GravitreJsonAudioSerializer
from app.services.pipecat_voice.voice_latency_observer import GravitreVoiceLatencyObserver
from app.services.pipecat_voice.voice_turn_trace import VoiceTurnTrace, resolve_turn_tier


class _Clock:
    def __init__(self) -> None:
        self.t = 100.0

    def __call__(self) -> float:
        return self.t

    def at(self, ms: float) -> float:
        self.t = 100.0 + ms / 1000.0
        return self.t


def _drive_full_turn(trace: VoiceTurnTrace, clock: _Clock) -> None:
    clock.at(0)
    trace.on_interim()  # last interim = end of speech
    clock.at(200)
    trace.on_eager_end_of_turn()
    clock.at(450)
    trace.on_stt_final()
    trace.on_user_stopped()
    clock.at(470)
    trace.begin_turn()
    clock.at(480)
    trace.note("durable_ready")
    clock.at(530)
    trace.note("prompt_ready")
    clock.at(700)
    trace.note("guard_done")
    # The brain started at 540 ms; its own checkpoints are ms from its start.
    trace.attach_brain_marks(
        {
            "_t0_perf": 100.540,
            "client_ready": 0,
            "workspace_focus_resolved": 5,
            "intent_gateway": 65,
            "engine_settings": 100,
            "routing_classified": 130,
            "pre_kernel_entry": 400,
            "react_entry": 900,
            "first_sse": 1500,
        }
    )
    trace.attach_intelligence(
        {"effectiveMode": "fast", "routing": {"reasoningDepth": "full", "conversationTier": "medium"}}
    )
    clock.at(1790)
    trace.note("first_token")
    clock.at(1850)
    trace.note("first_speakable")
    trace.note("tts_requested")
    clock.at(2000)
    trace.on_tts_audio()
    clock.at(2010)
    trace.on_bot_started_speaking()
    trace.on_observer_breakdown(e2e_ms=1560, ttfb_by_processor_ms={"ElevenLabsTTSService": 150})
    trace.set_turn_meta(turn_id="turn-1", speculative_outcome="fresh")


class TestOneRecordPerTurn:
    @pytest.mark.asyncio
    async def test_every_stage_lands_in_one_record_on_one_clock(self) -> None:
        clock = _Clock()
        written: list[dict] = []
        trace = VoiceTurnTrace(writer=written.append, clock=clock)
        _drive_full_turn(trace, clock)
        clock.at(2600)
        trace.end_turn()
        assert written == []  # waits for the browser's playback report
        clock.at(2110)
        trace.on_client_playback_started(40)

        assert len(written) == 1
        rec = written[0]
        d = rec["stage_durations_ms"]
        assert rec["turn_id"] == "turn-1"
        assert rec["tier"] == "medium" and rec["tier_source"] == "brain"
        assert d["eot_detection_ms"] == 470
        assert d["stt_finalization_ms"] == 450
        assert d["eager_eot_ms"] == 200
        assert d["durable_context_ms"] == 10
        assert d["prompt_assembly_ms"] == 50
        assert d["moderation_guard_ms"] == 170
        assert d["intent_tier_classification_ms"] == 60 + 30
        # first_sse is a post-answer checkpoint: pre-LLM work ends at react_entry.
        assert d["brain_pre_llm_ms"] == 900
        assert d["model_ttft_ms"] == 1790 - 1440
        assert d["first_speakable_ms"] == 60
        assert d["tts_ttfb_ms"] == 150
        assert d["server_audio_out_ms"] == 10
        # (2110 - 2010 - 40) / 2
        assert d["transport_est_ms"] == 30
        assert d["browser_playback_startup_ms"] == 40
        assert d["speech_end_to_playback_ms"] == 2010 + 30 + 40
        assert d["observer_e2e_ms"] == 1560
        assert d["brain.react_entry"] == 900
        assert rec["marks"]["browser_playback_started"] == 2080
        assert rec["marks"]["turn_committed"] == 470
        json.dumps(rec)  # audit metadata must be JSON

    @pytest.mark.asyncio
    async def test_missing_playback_report_is_written_after_the_grace_period(self, monkeypatch) -> None:
        monkeypatch.setattr(vtt, "PLAYBACK_REPORT_GRACE_S", 0.01)
        clock = _Clock()
        written: list[dict] = []
        trace = VoiceTurnTrace(writer=written.append, clock=clock)
        _drive_full_turn(trace, clock)
        trace.end_turn()
        await asyncio.sleep(0.05)
        assert len(written) == 1
        assert "browser_playback_startup_ms" not in written[0]["stage_durations_ms"]

    def test_next_turn_flushes_the_previous_one(self) -> None:
        clock = _Clock()
        written: list[dict] = []
        trace = VoiceTurnTrace(writer=written.append, clock=clock)
        _drive_full_turn(trace, clock)
        trace.end_turn()
        trace.begin_turn()
        assert len(written) == 1

    def test_turn_without_speech_frames_uses_commit_as_reference(self) -> None:
        clock = _Clock()
        written: list[dict] = []
        trace = VoiceTurnTrace(writer=written.append, clock=clock)
        trace.begin_turn()
        clock.at(300)
        trace.note("first_token")
        trace.end_turn()
        assert written[0]["stage_durations_ms"]["speech_end_to_first_token_ms"] == 300

    @pytest.mark.asyncio
    async def test_out_of_range_client_report_is_ignored(self) -> None:
        clock = _Clock()
        written: list[dict] = []
        trace = VoiceTurnTrace(writer=written.append, clock=clock)
        _drive_full_turn(trace, clock)
        trace.end_turn()
        assert written == []
        trace.on_client_playback_started("not a number")
        assert "browser_playback_startup_ms" not in written[0]["stage_durations_ms"]


class TestTier:
    def test_the_brains_recorded_tier_wins(self) -> None:
        data = {"routing": {"conversationTier": "Light", "conversationTierReason": "social"}, "effectiveMode": "agent"}
        assert resolve_turn_tier(data, "deep") == ("light", "brain")

    def test_bridge_tier_is_the_fallback_and_nothing_is_inferred(self) -> None:
        assert resolve_turn_tier({"effectiveMode": "agent"}, "medium") == ("medium", "bridge")
        assert resolve_turn_tier({"effectiveMode": "agent"}) == (None, "unknown")
        assert resolve_turn_tier({}, None) == (None, "unknown")

    def test_record_carries_the_brain_tier_over_the_bridge_tier(self) -> None:
        clock = _Clock()
        written: list[dict] = []
        trace = VoiceTurnTrace(writer=written.append, clock=clock)
        trace.begin_turn()
        trace.set_turn_meta(tier="medium")
        trace.attach_intelligence({"routing": {"conversationTier": "deep", "conversationTierReason": "connector"}})
        trace.end_turn()
        trace.flush_pending()
        assert written[0]["tier"] == "deep" and written[0]["tier_source"] == "brain"
        assert written[0]["extra"]["tier_reason"] == "connector"


class TestBrowserReport:
    @pytest.mark.asyncio
    async def test_serializer_records_playback_started_and_emits_no_frame(self) -> None:
        clock = _Clock()
        written: list[dict] = []
        trace = VoiceTurnTrace(writer=written.append, clock=clock)
        _drive_full_turn(trace, clock)
        trace.end_turn()
        serializer = GravitreJsonAudioSerializer(turn_trace=trace)
        frame = await serializer.deserialize(json.dumps({"type": "playback.started", "receive_to_playback_ms": 55}))
        assert frame is None
        assert written[0]["stage_durations_ms"]["browser_playback_startup_ms"] == 55

    @pytest.mark.asyncio
    async def test_serializer_without_trace_ignores_the_report(self) -> None:
        serializer = GravitreJsonAudioSerializer()
        assert await serializer.deserialize(json.dumps({"type": "playback.started"})) is None


def _pushed(frame) -> FramePushed:
    return FramePushed(
        source=SimpleNamespace(name="src"),  # type: ignore[arg-type]
        destination=SimpleNamespace(name="dst"),  # type: ignore[arg-type]
        frame=frame,
        direction=FrameDirection.DOWNSTREAM,
        timestamp=0,
    )


class TestObserverStamps:
    @pytest.mark.asyncio
    async def test_observer_stamps_speech_tts_and_first_audio_out(self) -> None:
        clock = _Clock()
        written: list[dict] = []
        trace = VoiceTurnTrace(writer=written.append, clock=clock)
        obs = GravitreVoiceLatencyObserver(turn_trace=trace)
        for name in ("on_latency_measured", "on_latency_breakdown", "on_first_bot_speech_latency"):
            obs._register_event_handler(name)
        clock.at(0)
        await obs.on_push_frame(_pushed(InterimTranscriptionFrame("hi there", "u", "")))
        clock.at(150)
        await obs.on_push_frame(_pushed(EagerTranscriptionFrame("hi there", "u", "")))
        clock.at(400)
        await obs.on_push_frame(_pushed(TranscriptionFrame("hi there", "u", "", finalized=True)))
        await obs.on_push_frame(_pushed(ProposedUserStoppedSpeakingFrame()))
        clock.at(420)
        trace.begin_turn()
        clock.at(900)
        trace.note("first_token")
        trace.note("tts_requested")
        clock.at(1000)
        await obs.on_push_frame(_pushed(TTSAudioRawFrame(b"\x00\x00" * 10, 24000, 1)))
        clock.at(1010)
        await obs.on_push_frame(_pushed(BotStartedSpeakingFrame()))
        trace.end_turn()
        trace.flush_pending()
        d = written[0]["stage_durations_ms"]
        assert d["eager_eot_ms"] == 150
        assert d["stt_finalization_ms"] == 400
        assert d["eot_detection_ms"] == 420
        assert d["tts_ttfb_ms"] == 100
        assert d["speech_end_to_server_audio_ms"] == 1010
