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
import uuid
from collections.abc import AsyncIterator, Callable
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

# Short-lived barge-in cancel flags (turn_id → expiry epoch seconds).
# Prefer Redis so cancel works across Railway replicas; memory is local fallback.
_CANCELLED_TURNS: dict[str, float] = {}
_CANCEL_REDIS_PREFIX = "voice:turn:cancel:"


def request_turn_cancel(turn_id: str, *, ttl_seconds: float = 120.0) -> None:
    tid = (turn_id or "").strip()
    if not tid:
        return
    ttl = max(5.0, float(ttl_seconds))
    _CANCELLED_TURNS[tid] = time.time() + ttl
    now = time.time()
    stale = [k for k, exp in _CANCELLED_TURNS.items() if exp < now]
    for k in stale:
        _CANCELLED_TURNS.pop(k, None)
    try:
        from app.config import get_settings
        from app.core.redis_client import get_sync_redis

        client = get_sync_redis(get_settings())
        if client is not None:
            client.setex(f"{_CANCEL_REDIS_PREFIX}{tid}", int(ttl), "1")
    except Exception:  # noqa: BLE001
        pass


def is_turn_cancelled(turn_id: str) -> bool:
    tid = (turn_id or "").strip()
    if not tid:
        return False
    exp = _CANCELLED_TURNS.get(tid)
    if exp is not None:
        if exp < time.time():
            _CANCELLED_TURNS.pop(tid, None)
        else:
            return True
    try:
        from app.config import get_settings
        from app.core.redis_client import get_sync_redis

        client = get_sync_redis(get_settings())
        if client is not None:
            return bool(client.get(f"{_CANCEL_REDIS_PREFIX}{tid}"))
    except Exception:  # noqa: BLE001
        return False
    return False


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
    turn_id: str | None = None,
    should_cancel: Callable[[], bool] | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """Run unified-turn streaming + progressive TTS. Yields typed events."""
    from app.operators.agent_intelligence import get_agent_intelligence
    from app.operators.stream_events import AssistantStreamComplete, AssistantStreamEvent

    profile = normalize_voice_profile((agent or {}).get("voice_profile"))
    resolved_voice = voice_id or profile.get("voice_id") or profile.get("voice_key")
    model = tts_model or profile.get("tts_model") or "eleven_flash_v2_5"
    resolved_turn_id = (turn_id or "").strip() or str(uuid.uuid4())
    resolved_conversation_id = (conversation_id or "").strip() or None

    def _cancelled() -> bool:
        if should_cancel and should_cancel():
            return True
        return is_turn_cancelled(resolved_turn_id)

    yield {
        "type": "voice.session.started",
        "spoken_mode": True,
        "modality": "voice",
        "originating_modality": "voice",
        "write_confirm_policy": "nl_yes_same_path_as_text",
        "pipeline": "execute_task_streaming",
        "cognitive_path": "CognitiveTurnKernel",
        "voice_id": resolved_voice,
        "tts_model": model,
        "turn_id": resolved_turn_id,
        "conversation_id": resolved_conversation_id,
    }

    intelligence = get_agent_intelligence()
    text_buffer = ""
    full_text: list[str] = []
    t_start = time.perf_counter()
    first_text_ms: int | None = None
    first_audio_ms: int | None = None
    agent_audio_started = False
    cancelled = False

    async for event in intelligence.execute_task_streaming(
        settings=settings,
        org_id=org_id,
        user_id=user_id,
        query=text,
        agent_id=str((agent or {}).get("id") or "") or None,
        conversation_history=conversation_history,
        conversation_id=resolved_conversation_id,
        spoken_mode=True,
    ):
        if _cancelled():
            cancelled = True
            yield {
                "type": "voice.turn.cancelled",
                "turn_id": resolved_turn_id,
                "conversation_id": resolved_conversation_id,
                "reason": "barge_in_or_client_abort",
                "partial_text": "".join(full_text),
            }
            break
        if isinstance(event, AssistantStreamComplete):
            yield {
                "type": "voice.turn.complete",
                "message_id": event.message_id,
                "model": event.model,
                "text": "".join(full_text),
                "turn_id": resolved_turn_id,
                "conversation_id": resolved_conversation_id,
                "originating_modality": "voice",
                "cancelled": False,
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
            yield {"type": "voice.ttft", "ms": first_text_ms, "turn_id": resolved_turn_id}
        full_text.append(delta)
        text_buffer += delta
        chunks, text_buffer = split_speakable_chunks(text_buffer)
        for chunk in chunks:
            if _cancelled():
                cancelled = True
                break
            if not agent_audio_started:
                agent_audio_started = True
                yield {"type": "voice.agent_speech.start", "turn_id": resolved_turn_id}
            for audio in synthesize_speech_stream(
                settings,
                text=chunk,
                voice_key=resolved_voice,
                model_id=model,
            ):
                if _cancelled():
                    cancelled = True
                    break
                if first_audio_ms is None:
                    first_audio_ms = int((time.perf_counter() - t_start) * 1000)
                    yield {"type": "voice.ttfa", "ms": first_audio_ms, "turn_id": resolved_turn_id}
                yield {
                    "type": "voice.audio.delta",
                    "content_type": "audio/mpeg",
                    "audio_base64": base64.b64encode(audio).decode("ascii"),
                    "text_chunk": chunk,
                    "turn_id": resolved_turn_id,
                }
            if cancelled:
                break
        if cancelled:
            break
    if cancelled:
        if agent_audio_started:
            yield {"type": "voice.agent_speech.end", "cancelled": True, "turn_id": resolved_turn_id}
        yield {
            "type": "voice.session.ended",
            "transcript": "".join(full_text),
            "cancelled": True,
            "turn_id": resolved_turn_id,
            "conversation_id": resolved_conversation_id,
            "originating_modality": "voice",
        }
        return
    # Flush remainder
    rem = text_buffer.strip()
    if rem and not _cancelled():
        if not agent_audio_started:
            yield {"type": "voice.agent_speech.start", "turn_id": resolved_turn_id}
        for audio in synthesize_speech_stream(
            settings, text=rem, voice_key=resolved_voice, model_id=model
        ):
            if _cancelled():
                cancelled = True
                break
            if first_audio_ms is None:
                first_audio_ms = int((time.perf_counter() - t_start) * 1000)
                yield {"type": "voice.ttfa", "ms": first_audio_ms, "turn_id": resolved_turn_id}
            yield {
                "type": "voice.audio.delta",
                "content_type": "audio/mpeg",
                "audio_base64": base64.b64encode(audio).decode("ascii"),
                "text_chunk": rem,
                "turn_id": resolved_turn_id,
            }
    if cancelled:
        yield {
            "type": "voice.turn.cancelled",
            "turn_id": resolved_turn_id,
            "conversation_id": resolved_conversation_id,
            "reason": "barge_in_or_client_abort",
            "partial_text": "".join(full_text),
        }
        yield {
            "type": "voice.session.ended",
            "transcript": "".join(full_text),
            "cancelled": True,
            "turn_id": resolved_turn_id,
            "conversation_id": resolved_conversation_id,
            "originating_modality": "voice",
        }
        return
    if agent_audio_started:
        yield {"type": "voice.agent_speech.end", "turn_id": resolved_turn_id}
    yield {
        "type": "voice.session.ended",
        "transcript": "".join(full_text),
        "cancelled": False,
        "turn_id": resolved_turn_id,
        "conversation_id": resolved_conversation_id,
        "originating_modality": "voice",
    }


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
