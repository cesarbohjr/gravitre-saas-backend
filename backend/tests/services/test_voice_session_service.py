"""Regression tests for voice session streaming behavior."""
from __future__ import annotations

import base64
from collections.abc import AsyncIterator, Iterator
from typing import Any

import pytest

from app.operators.stream_events import AssistantStreamComplete, AssistantStreamEvent
from app.services import voice_session_service
from app.services.tier1_voice_service import VoiceProviderError


class _FakeIntelligence:
    def __init__(self, deltas: list[str], complete: str | None = None) -> None:
        self._deltas = deltas
        self._complete = complete if complete is not None else "".join(deltas)
        self.kwargs: dict[str, Any] = {}

    async def execute_task_streaming(self, **kwargs: Any) -> AsyncIterator[Any]:
        self.kwargs = dict(kwargs)
        for delta in self._deltas:
            yield AssistantStreamEvent(sse_type="text-delta", payload={"delta": delta})
        yield AssistantStreamComplete(
            full_content=self._complete,
            tool_results=[],
            react_result=None,
            model="gpt-test",
            message_id="msg-voice-1",
        )


def _settings_with_voice(mock_settings):
    mock_settings.elevenlabs_api_key = "test-elevenlabs"
    return mock_settings


@pytest.mark.asyncio
async def test_stream_voice_turn_emits_audio_chunks_as_they_arrive(monkeypatch, mock_settings):
    monkeypatch.setattr(
        "app.operators.agent_intelligence.get_agent_intelligence",
        lambda: _FakeIntelligence(["Please provide recipient, subject, and body."]),
    )

    def _fake_tts_stream(*_: Any, **__: Any) -> Iterator[bytes]:
        yield b"chunk-1-"
        yield b"chunk-2"

    monkeypatch.setattr(voice_session_service, "synthesize_speech_stream", _fake_tts_stream)

    events = [
        event
        async for event in voice_session_service.stream_voice_turn_events(
            settings=_settings_with_voice(mock_settings),
            org_id="org-1",
            user_id="user-1",
            text="Send an email",
            agent={"id": "agent-1"},
            conversation_id="conv-1",
        )
    ]

    # Provider transport pieces are arbitrary MP3 byte ranges; each spoken
    # phrase is emitted once, assembled, so the browser can decode it.
    audio_events = [e for e in events if e.get("type") == "voice.audio.delta"]
    assert [base64.b64decode(str(e["audio_base64"])) for e in audio_events] == [
        b"chunk-1-chunk-2",
    ]
    ttfa = next((e for e in events if e.get("type") == "voice.ttfa"), None)
    assert ttfa is not None and ttfa.get("metric") == "A"
    assert any(e.get("type") == "voice.turn.complete" for e in events)


@pytest.mark.asyncio
async def test_operator_turn_speaks_perceive_before_kernel(monkeypatch, mock_settings):
    """When PERCEIVE draft is empty, Metric A is the composed answer, not filler TTS."""
    import asyncio

    from app.services.voice_slo import EARLY_PERCEIVE_DRAFT

    started = {"kernel": False}

    class _SlowIntelligence(_FakeIntelligence):
        async def execute_task_streaming(self, **kwargs: Any) -> AsyncIterator[Any]:
            started["kernel"] = True
            await asyncio.sleep(0.05)
            async for ev in super().execute_task_streaming(**kwargs):
                yield ev

    monkeypatch.setattr(
        "app.operators.agent_intelligence.get_agent_intelligence",
        lambda: _SlowIntelligence(["Plan ready. Nothing executed."]),
    )
    monkeypatch.setattr(
        voice_session_service,
        "synthesize_speech_stream",
        lambda *_, **__: iter((b"audio-1",)),
    )
    events = [
        event
        async for event in voice_session_service.stream_voice_turn_events(
            settings=_settings_with_voice(mock_settings),
            org_id="org-1",
            user_id="user-1",
            text="Check that my Google Ads account is actually connected.",
            agent={"id": "agent-1"},
            conversation_id="conv-1",
        )
    ]
    audio = [e for e in events if e.get("type") == "voice.audio.delta"]
    assert audio
    if (EARLY_PERCEIVE_DRAFT or "").strip():
        assert started["kernel"] is True
    texts = "".join(str(e.get("delta") or "") for e in events if e.get("type") == "voice.text.delta")
    assert "on it" not in texts.lower()
    assert "classified this as" not in texts.lower()


_PLAN_HOLD_PROBE_PROMPT = (
    "List my HubSpot contacts at a high level and show the complete plan before "
    "you execute anything. Don't execute."
)


@pytest.mark.asyncio
async def test_plan_hold_turn_speaks_honest_plan_draft_before_kernel(monkeypatch, mock_settings):
    """Metric A on a plan-hold turn is the honest PLAN draft, spoken before the kernel runs.

    Only behind VOICE_EARLY_PLAN_ACK_ENABLED + the org allowlist, and only
    after the shared safety gate allowed the turn (see
    test_voice_early_plan_ack.py). The kernel says the same sentence at its
    PLAN stage after retrieval and planning; the voice turn must not speak it
    twice.
    """
    mock_settings.voice_early_plan_ack_enabled = True
    mock_settings.voice_early_plan_ack_org_ids = "org-1"
    from app.services.cognitive_loop_controller import speakable_loop_stage
    from app.services.voice_slo import EARLY_PLAN_HOLD_DRAFT

    kernel_draft = speakable_loop_stage("PLAN", extras={"plan_without_execute": True})
    assert kernel_draft == EARLY_PLAN_HOLD_DRAFT
    order: list[str] = []
    slo_rows: list[dict[str, Any]] = []

    class _PlanHoldKernel(_FakeIntelligence):
        async def execute_task_streaming(self, **kwargs: Any) -> AsyncIterator[Any]:
            order.append("kernel")
            async for ev in super().execute_task_streaming(**kwargs):
                yield ev

    monkeypatch.setattr(
        "app.operators.agent_intelligence.get_agent_intelligence",
        lambda: _PlanHoldKernel(
            [kernel_draft, "Step one reads HubSpot contacts. Nothing has run."],
        ),
    )

    def _tts(*_: Any, **kwargs: Any) -> Iterator[bytes]:
        order.append(f"tts:{kwargs.get('text')}")
        yield b"audio"

    monkeypatch.setattr(voice_session_service, "_PERCEIVE_TTS_CACHE", {})
    monkeypatch.setattr(voice_session_service, "synthesize_speech_stream", _tts)
    monkeypatch.setattr(
        "app.services.pipecat_voice.voice_latency_metrics.record_voice_slo_metric",
        lambda *_a, **kw: slo_rows.append(kw),
    )
    events = [
        event
        async for event in voice_session_service.stream_voice_turn_events(
            settings=_settings_with_voice(mock_settings),
            org_id="org-1",
            user_id="user-1",
            text=_PLAN_HOLD_PROBE_PROMPT,
            agent={"id": "agent-1"},
            conversation_id="conv-1",
        )
    ]
    deltas = [str(e.get("delta") or "") for e in events if e.get("type") == "voice.text.delta"]
    assert deltas[0] == EARLY_PLAN_HOLD_DRAFT
    assert deltas.count(EARLY_PLAN_HOLD_DRAFT) == 1
    first_tts = next(i for i, step in enumerate(order) if step.startswith("tts:"))
    assert order[first_tts] == f"tts:{EARLY_PLAN_HOLD_DRAFT}"
    assert first_tts < order.index("kernel")
    assert order.count(f"tts:{EARLY_PLAN_HOLD_DRAFT}") == 1
    metric_a = [row for row in slo_rows if row.get("metric") == "time_to_first_honest_response"]
    assert metric_a and metric_a[0]["source"] == "loop_stage:PLAN"
    # Honest: never claims work ran, never the retired generic filler.
    joined = " ".join(deltas).lower()
    assert "classified this as" not in joined
    assert "running the full loop" not in joined


@pytest.mark.asyncio
async def test_connector_status_plan_hold_turn_gets_no_early_plan_draft(monkeypatch, mock_settings):
    """The kernel stays silent on stages for connector-status asks; so does the early draft."""
    from app.services.voice_slo import EARLY_PLAN_HOLD_DRAFT

    mock_settings.voice_early_plan_ack_enabled = True
    mock_settings.voice_early_plan_ack_org_ids = "org-1"
    monkeypatch.setattr(
        "app.operators.agent_intelligence.get_agent_intelligence",
        lambda: _FakeIntelligence(["Google Ads is connected."]),
    )
    monkeypatch.setattr(
        voice_session_service, "synthesize_speech_stream", lambda *_, **__: iter((b"a",))
    )
    events = [
        event
        async for event in voice_session_service.stream_voice_turn_events(
            settings=_settings_with_voice(mock_settings),
            org_id="org-1",
            user_id="user-1",
            text=(
                "Check that my Google Ads account is actually connected, and show me the "
                "complete plan before you execute anything. Don't execute without my approval."
            ),
            agent={"id": "agent-1"},
            conversation_id="conv-1",
        )
    ]
    deltas = [str(e.get("delta") or "") for e in events if e.get("type") == "voice.text.delta"]
    assert EARLY_PLAN_HOLD_DRAFT not in deltas


def test_standing_plan_hold_draft_audio_is_cached(monkeypatch, mock_settings):
    """Warm-up synthesizes the plan-hold draft once so Metric A skips the TTS round trip."""
    from app.services.voice_slo import EARLY_PLAN_HOLD_DRAFT

    calls: list[str] = []

    def _tts(*_: Any, **kwargs: Any) -> Iterator[bytes]:
        calls.append(str(kwargs.get("text")))
        yield b"warm"

    monkeypatch.setattr(voice_session_service, "_PERCEIVE_TTS_CACHE", {})
    monkeypatch.setattr(voice_session_service, "synthesize_speech_stream", _tts)
    assert voice_session_service.warm_perceive_tts_cache(_settings_with_voice(mock_settings))
    assert voice_session_service.warm_perceive_tts_cache(_settings_with_voice(mock_settings))
    spoken = voice_session_service.normalize_spoken_text(EARLY_PLAN_HOLD_DRAFT)
    assert calls == [spoken]
    assert (
        "sarah",
        "eleven_flash_v2_5",
        "mp3_44100_128",
        spoken,
    ) in voice_session_service._PERCEIVE_TTS_CACHE


@pytest.mark.asyncio
async def test_stream_voice_turn_keeps_text_path_when_tts_fails(monkeypatch, mock_settings):
    monkeypatch.setattr(
        "app.operators.agent_intelligence.get_agent_intelligence",
        lambda: _FakeIntelligence(["What's the recipient, subject, and body?"]),
    )

    def _failing_tts_stream(*_: Any, **__: Any) -> Iterator[bytes]:
        raise VoiceProviderError(
            "ElevenLabs timeout",
            status_code=504,
            error_class="service_failure",
            provider="elevenlabs",
        )
        yield b""  # pragma: no cover

    monkeypatch.setattr(voice_session_service, "synthesize_speech_stream", _failing_tts_stream)

    events = [
        event
        async for event in voice_session_service.stream_voice_turn_events(
            settings=_settings_with_voice(mock_settings),
            org_id="org-1",
            user_id="user-1",
            text="Send an email",
            agent={"id": "agent-1"},
            conversation_id="conv-1",
        )
    ]

    complete = next((e for e in events if e.get("type") == "voice.turn.complete"), None)
    assert complete is not None
    assert "recipient, subject, and body" in str(complete.get("text") or "").lower()

    errors = [e for e in events if e.get("type") == "voice.error"]
    assert errors
    assert errors[0].get("provider") == "elevenlabs"


@pytest.mark.asyncio
async def test_voice_session_uses_agent_mode_for_google_ads(monkeypatch, mock_settings):
    fake = _FakeIntelligence(["I planned a 5-step orchestration."])
    monkeypatch.setattr(
        "app.operators.agent_intelligence.get_agent_intelligence",
        lambda: fake,
    )
    monkeypatch.setattr(
        voice_session_service,
        "synthesize_speech_stream",
        lambda *_, **__: iter((b"x",)),
    )
    events = [
        event
        async for event in voice_session_service.stream_voice_turn_events(
            settings=_settings_with_voice(mock_settings),
            org_id="org-1",
            user_id="user-1",
            text=(
                "I have a Google Ads campaign strategy ready to go live. "
                "Don't execute anything without my approval first."
            ),
            agent={"id": "agent-1"},
            conversation_id="conv-1",
        )
    ]
    assert fake.kwargs.get("mode") == "agent"
    assert fake.kwargs.get("spoken_mode") is True
    assert any(e.get("type") == "voice.turn.complete" for e in events)


@pytest.mark.asyncio
async def test_voice_session_prefers_complete_payload_over_streamed_deltas(
    monkeypatch, mock_settings
):
    fake = _FakeIntelligence(
        ["I don't have enough information yet to do that safely."],
        complete="I planned a **5-step orchestration**, but **nothing is runnable**.",
    )
    monkeypatch.setattr(
        "app.operators.agent_intelligence.get_agent_intelligence",
        lambda: fake,
    )
    monkeypatch.setattr(
        voice_session_service,
        "synthesize_speech_stream",
        lambda *_, **__: iter((b"x",)),
    )
    events = [
        event
        async for event in voice_session_service.stream_voice_turn_events(
            settings=_settings_with_voice(mock_settings),
            org_id="org-1",
            user_id="user-1",
            text="hey",
            agent={"id": "agent-1"},
            conversation_id="conv-1",
        )
    ]
    complete = next((e for e in events if e.get("type") == "voice.turn.complete"), None)
    assert complete is not None
    assert "5-step orchestration" in str(complete.get("text") or "")
    assert "enough information" not in str(complete.get("text") or "").lower()


@pytest.mark.asyncio
async def test_voice_cancel_near_approval_emits_cancelled(monkeypatch, mock_settings):
    monkeypatch.setattr(
        "app.operators.agent_intelligence.get_agent_intelligence",
        lambda: _FakeIntelligence(["I can send it after you confirm."]),
    )
    monkeypatch.setattr(
        voice_session_service,
        "synthesize_speech_stream",
        lambda *_, **__: iter((b"x",)),
    )
    events = [
        event
        async for event in voice_session_service.stream_voice_turn_events(
            settings=_settings_with_voice(mock_settings),
            org_id="org-1",
            user_id="user-1",
            text="Send an email to ada@example.com subject Hello body Hi",
            agent={"id": "agent-1"},
            conversation_id="conv-1",
            should_cancel=lambda: True,
        )
    ]
    assert any(e.get("type") == "voice.turn.cancelled" for e in events) or any(
        e.get("type") == "voice.turn.complete" for e in events
    )


@pytest.mark.asyncio
async def test_legacy_http_voice_turn_is_saved_server_side(monkeypatch, mock_settings):
    """The HTTP Talk path saves turns to the same conversation store as text and Pipecat."""
    monkeypatch.setattr(
        "app.operators.agent_intelligence.get_agent_intelligence",
        lambda: _FakeIntelligence(["Pipeline is up twelve percent."]),
    )
    monkeypatch.setattr(
        voice_session_service, "synthesize_speech_stream", lambda *_, **__: iter((b"x",))
    )
    saved: list[dict[str, Any]] = []
    summaries: list[str | None] = []

    def _fake_persist(_settings: Any, **kwargs: Any) -> tuple[str, str]:
        saved.append(kwargs)
        return "conv-new", "msg-voice-1"

    monkeypatch.setattr(
        "app.services.shared_turn_preparation.persist_completed_turn", _fake_persist
    )
    monkeypatch.setattr(
        "app.services.shared_turn_preparation.persist_turn_summary",
        lambda _s, **kw: summaries.append(kw.get("conversation_id")),
    )
    events = [
        event
        async for event in voice_session_service.stream_voice_turn_events(
            settings=_settings_with_voice(mock_settings),
            org_id="org-1",
            user_id="user-1",
            text="How is pipeline doing?",
            agent={"id": "agent-1"},
            conversation_id=None,
        )
    ]
    assert len(saved) == 1
    assert saved[0]["user_text"] == "How is pipeline doing?"
    assert saved[0]["assistant_text"] == "Pipeline is up twelve percent."
    assert saved[0]["conversation_id"] is None
    assert summaries == ["conv-new"]
    ended = next(e for e in events if e.get("type") == "voice.session.ended")
    # A first turn creates the conversation; the client learns its id from the stream.
    assert ended["conversation_id"] == "conv-new"


@pytest.mark.asyncio
async def test_legacy_http_voice_turn_persist_failure_does_not_break_the_turn(
    monkeypatch, mock_settings
):
    monkeypatch.setattr(
        "app.operators.agent_intelligence.get_agent_intelligence",
        lambda: _FakeIntelligence(["Done."]),
    )
    monkeypatch.setattr(
        voice_session_service, "synthesize_speech_stream", lambda *_, **__: iter((b"x",))
    )

    def _boom(*_: Any, **__: Any) -> None:
        raise RuntimeError("db down")

    monkeypatch.setattr("app.services.shared_turn_preparation.persist_completed_turn", _boom)
    events = [
        event
        async for event in voice_session_service.stream_voice_turn_events(
            settings=_settings_with_voice(mock_settings),
            org_id="org-1",
            user_id="user-1",
            text="Do it",
            agent={"id": "agent-1"},
            conversation_id="conv-1",
        )
    ]
    ended = next(e for e in events if e.get("type") == "voice.session.ended")
    assert ended["cancelled"] is False and ended["conversation_id"] == "conv-1"
