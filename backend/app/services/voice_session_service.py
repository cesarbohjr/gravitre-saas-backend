"""Streaming voice session over the existing unified-turn / SSE chat backbone.

Flow:
  Deepgram live partials → provisional turn-taking → finalize user turn
  → execute_task_streaming(spoken_mode=True) → sentence-chunk TTS stream
  → same write-confirm / GIBE paths as text.
"""
from __future__ import annotations

import base64
import re
import time
from collections.abc import AsyncIterator
from typing import Any

from app.config import Settings
from app.services.tier1_voice_service import synthesize_speech_stream
from app.services.voice_agent_profile import normalize_voice_profile
from app.services.voice_turn_taking import (
    TurnTakingState,
    maybe_finalize_user_turn,
    on_agent_speech_end,
    on_agent_speech_start,
    on_user_partial,
    on_user_utterance_end,
    parse_sensitivity,
    snapshot,
)

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


def split_speakable_chunks(buffer: str, *, min_chars: int = 24) -> tuple[list[str], str]:
    """Emit speakable chunks at sentence boundaries; keep remainder provisional."""
    parts = _SENTENCE_END.split(buffer)
    if len(parts) <= 1:
        if len(buffer) >= max(min_chars * 3, 80) and (" " in buffer):
            # Long clause without terminal punctuation — flush a clause on comma/space.
            idx = buffer.rfind(", ", 0, len(buffer) - 10)
            if idx < min_chars:
                idx = buffer.rfind(" ", 0, len(buffer) - 5)
            if idx >= min_chars:
                return [buffer[:idx].strip()], buffer[idx:].lstrip()
        return [], buffer
    ready = [p.strip() for p in parts[:-1] if p.strip()]
    return ready, parts[-1]


async def stream_voice_turn_events(
    *,
    settings: Settings,
    org_id: str,
    user_id: str,
    text: str,
    agent: dict[str, Any] | None,
    conversation_id: str | None,
    conversation_history: list[dict[str, Any]] | None = None,
    voice_id: str | None = None,
    tts_model: str | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """Run unified-turn streaming + progressive TTS. Yields typed events."""
    from app.operators.agent_intelligence import get_agent_intelligence
    from app.operators.assistant_sse import AssistantStreamComplete, AssistantStreamEvent

    profile = normalize_voice_profile((agent or {}).get("voice_profile"))
    resolved_voice = voice_id or profile.get("voice_id") or profile.get("voice_key")
    model = tts_model or profile.get("tts_model") or "eleven_flash_v2_5"

    yield {
        "type": "voice.session.started",
        "spoken_mode": True,
        "write_confirm_policy": "nl_yes_same_path_as_text",
        "pipeline": "execute_task_streaming",
        "voice_id": resolved_voice,
        "tts_model": model,
    }

    intelligence = get_agent_intelligence()
    text_buffer = ""
    full_text: list[str] = []
    t_start = time.perf_counter()
    first_text_ms: int | None = None
    first_audio_ms: int | None = None
    agent_audio_started = False

    async for event in intelligence.execute_task_streaming(
        settings=settings,
        org_id=org_id,
        user_id=user_id,
        query=text,
        agent_id=str((agent or {}).get("id") or "") or None,
        conversation_history=conversation_history,
        conversation_id=conversation_id,
        spoken_mode=True,
    ):
        if isinstance(event, AssistantStreamComplete):
            yield {
                "type": "voice.turn.complete",
                "message_id": event.message_id,
                "model": event.model,
                "text": "".join(full_text),
                "latency_ms": {
                    "total": int((time.perf_counter() - t_start) * 1000),
                    "ttft_ms": first_text_ms,
                    "ttfa_ms": first_audio_ms,
                },
            }
            continue
        if not isinstance(event, AssistantStreamEvent):
            continue
        if event.sse_type == "data-intelligence":
            yield {"type": "voice.intelligence", "payload": event.payload}
            continue
        if event.sse_type != "text-delta":
            yield {"type": f"voice.sse.{event.sse_type}", "payload": event.payload}
            continue
        delta = event.payload.get("delta")
        if not isinstance(delta, str) or not delta:
            continue
        if first_text_ms is None:
            first_text_ms = int((time.perf_counter() - t_start) * 1000)
            yield {"type": "voice.ttft", "ms": first_text_ms}
        full_text.append(delta)
        text_buffer += delta
        chunks, text_buffer = split_speakable_chunks(text_buffer)
        for chunk in chunks:
            if not agent_audio_started:
                agent_audio_started = True
                yield {"type": "voice.agent_speech.start"}
            for audio in synthesize_speech_stream(
                settings,
                text=chunk,
                voice_key=resolved_voice,
                model_id=model,
            ):
                if first_audio_ms is None:
                    first_audio_ms = int((time.perf_counter() - t_start) * 1000)
                    yield {"type": "voice.ttfa", "ms": first_audio_ms}
                yield {
                    "type": "voice.audio.delta",
                    "content_type": "audio/mpeg",
                    "audio_base64": base64.b64encode(audio).decode("ascii"),
                    "text_chunk": chunk,
                }
    # Flush remainder
    rem = text_buffer.strip()
    if rem:
        if not agent_audio_started:
            yield {"type": "voice.agent_speech.start"}
        for audio in synthesize_speech_stream(
            settings, text=rem, voice_key=resolved_voice, model_id=model
        ):
            if first_audio_ms is None:
                first_audio_ms = int((time.perf_counter() - t_start) * 1000)
                yield {"type": "voice.ttfa", "ms": first_audio_ms}
            yield {
                "type": "voice.audio.delta",
                "content_type": "audio/mpeg",
                "audio_base64": base64.b64encode(audio).decode("ascii"),
                "text_chunk": rem,
            }
    if agent_audio_started:
        yield {"type": "voice.agent_speech.end"}
    yield {"type": "voice.session.ended", "transcript": "".join(full_text)}


def apply_stt_event_to_turn_state(
    state: TurnTakingState,
    *,
    event: dict[str, Any],
    now_ms: float | None = None,
) -> tuple[TurnTakingState, str | None]:
    """Map Deepgram-like events into provisional turn-taking; maybe finalize."""
    t = now_ms if now_ms is not None else time.time() * 1000
    etype = str(event.get("type") or event.get("event") or "").lower()
    transcript = str(
        event.get("transcript")
        or event.get("text")
        or ((event.get("channel") or {}).get("alternatives") or [{}])[0].get("transcript")
        or ""
    ).strip()
    is_final = bool(event.get("is_final") or event.get("speech_final"))
    if etype in {"vad_speech", "speech_started"} or event.get("vad_speech"):
        state = on_user_partial(state, text=transcript or state.provisional_user_text, now_ms=t, vad_speech=True)
    elif etype in {"utterance_end", "speech_ended"}:
        state = on_user_utterance_end(state, text=transcript or state.provisional_user_text, now_ms=t)
    elif transcript:
        if is_final:
            state = on_user_utterance_end(state, text=transcript, now_ms=t)
        else:
            state = on_user_partial(state, text=transcript, now_ms=t, vad_speech=True)
    finalized = maybe_finalize_user_turn(state, now_ms=t)
    return state, finalized


def new_turn_state(sensitivity: str | None = None) -> TurnTakingState:
    return TurnTakingState(sensitivity=parse_sensitivity(sensitivity))


def turn_state_snapshot(state: TurnTakingState) -> dict[str, Any]:
    return snapshot(state)


def mark_agent_speaking(state: TurnTakingState, *, speaking: bool, now_ms: float | None = None) -> TurnTakingState:
    t = now_ms if now_ms is not None else time.time() * 1000
    if speaking:
        return on_agent_speech_start(state, now_ms=t)
    return on_agent_speech_end(state, now_ms=t)
