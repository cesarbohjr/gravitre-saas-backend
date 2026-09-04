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
from app.core.safe_dict import safe_normalize_stored_dict
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
_MARKDOWN_LINK = re.compile(r"\[([^\]]+)\]\([^)]+\)")
_LEADING_FORMAT = re.compile(r"^\s*(?:#{1,6}\s+|[-*]\s+|\d+\.\s+)")

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
        stripped = buffer.rstrip()
        # Complete sentence with terminal punct but no trailing whitespace yet
        # (common for short voice answers like "Four.").
        if stripped and stripped[-1] in ".!?" and len(stripped) >= 2:
            return [stripped], ""
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


def normalize_spoken_text(text: str) -> str:
    """Strip visual markdown/list formatting for natural spoken delivery."""
    lines: list[str] = []
    for raw in (text or "").replace("\r\n", "\n").split("\n"):
        line = raw.strip()
        if not line:
            continue
        line = _MARKDOWN_LINK.sub(r"\1", line)
        line = _LEADING_FORMAT.sub("", line)
        line = line.replace("**", "").replace("__", "").replace("`", "").strip()
        line = re.sub(r"\s{2,}", " ", line).strip()
        if not line:
            continue
        if line[-1] not in ".!?":
            line = f"{line}."
        lines.append(line)
    return " ".join(lines).strip()


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
    tts_output_format: str = "mp3_44100_128",
) -> AsyncIterator[dict[str, Any]]:
    """Run unified-turn streaming + progressive TTS. Yields typed events."""
    from app.operators.agent_intelligence import get_agent_intelligence
    from app.operators.stream_events import AssistantStreamComplete, AssistantStreamEvent
    from app.services.tier1_voice_service import normalize_elevenlabs_output_format

    profile = normalize_voice_profile((agent or {}).get("voice_profile"))
    resolved_voice = voice_id or profile.get("voice_id") or profile.get("voice_key")
    model = tts_model or profile.get("tts_model") or "eleven_flash_v2_5"
    resolved_turn_id = (turn_id or "").strip() or str(uuid.uuid4())
    resolved_conversation_id = (conversation_id or "").strip() or None
    _fmt, audio_content_type = normalize_elevenlabs_output_format(tts_output_format)
    tts_output_format = _fmt

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
    pending_complete: AssistantStreamComplete | None = None
    stage_ms: dict[str, Any] = {}
    reasoning_depth: str | None = None
    routing_tier: str | None = None
    effective_mode: str | None = None
    cached_prompt_tokens: int | None = None
    cached_prompt_ratio: float | None = None
    pre_act_done_ms: int | None = None
    model_ttft_ms: int | None = None
    pre_model_ms: int | None = None
    wall_to_first_token_ms: int | None = None
    spoken_streamed: bool | None = None
    unified_breakdown: dict[str, Any] = {}
    classify_done_ms: int | None = None

    async def _emit_tts(chunk: str) -> AsyncIterator[dict[str, Any]]:
        nonlocal first_audio_ms, agent_audio_started, cancelled
        spoken_chunk = normalize_spoken_text(chunk)
        if not spoken_chunk:
            return
            yield  # pragma: no cover — keeps this an async generator
        if _cancelled():
            cancelled = True
            return
            yield  # pragma: no cover — keeps this an async generator
        if not agent_audio_started:
            agent_audio_started = True
            yield {"type": "voice.agent_speech.start", "turn_id": resolved_turn_id}
        for audio in synthesize_speech_stream(
            settings,
            text=spoken_chunk,
            voice_key=resolved_voice,
            model_id=model,
            output_format=tts_output_format,
        ):
            if _cancelled():
                cancelled = True
                return
            if first_audio_ms is None:
                first_audio_ms = int((time.perf_counter() - t_start) * 1000)
                yield {"type": "voice.ttfa", "ms": first_audio_ms, "turn_id": resolved_turn_id}
            yield {
                "type": "voice.audio.delta",
                "content_type": audio_content_type,
                "audio_base64": base64.b64encode(audio).decode("ascii"),
                "text_chunk": spoken_chunk,
                "turn_id": resolved_turn_id,
            }

    async for event in intelligence.execute_task_streaming(
        settings=settings,
        org_id=org_id,
        user_id=user_id,
        query=text,
        agent_id=str((agent or {}).get("id") or "") or None,
        conversation_history=conversation_history,
        conversation_id=resolved_conversation_id,
        spoken_mode=True,
        mode="fast",
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
            # Defer complete until TTS flush so ttfa is present on the same turn.
            pending_complete = event
            continue
        if not isinstance(event, AssistantStreamEvent):
            continue
        if event.sse_type == "data-intelligence":
            payload = event.payload if isinstance(event.payload, dict) else {}
            data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
            if isinstance(data, dict):
                routing = data.get("routing") if isinstance(data.get("routing"), dict) else {}
                raw_stage_ms = routing.get("cognitiveStageMs")
                if isinstance(raw_stage_ms, dict):
                    stage_ms = safe_normalize_stored_dict(raw_stage_ms)
                    if pre_act_done_ms is None:
                        pre_act_done_ms = int((time.perf_counter() - t_start) * 1000)
                if routing.get("reasoningDepth"):
                    reasoning_depth = str(routing.get("reasoningDepth"))
                if data.get("routingTier"):
                    routing_tier = str(data.get("routingTier"))
                if data.get("effectiveMode"):
                    effective_mode = str(data.get("effectiveMode"))
                if routing.get("cachedPromptTokens") is not None:
                    try:
                        cached_prompt_tokens = int(routing.get("cachedPromptTokens"))
                    except (TypeError, ValueError):
                        pass
                if routing.get("cachedPromptRatio") is not None:
                    try:
                        cached_prompt_ratio = float(routing.get("cachedPromptRatio"))
                    except (TypeError, ValueError):
                        pass
                if routing.get("modelTtftMs") is not None:
                    try:
                        model_ttft_ms = int(routing.get("modelTtftMs"))
                    except (TypeError, ValueError):
                        pass
                if routing.get("preModelMs") is not None:
                    try:
                        pre_model_ms = int(routing.get("preModelMs"))
                    except (TypeError, ValueError):
                        pass
                if routing.get("wallToFirstTokenMs") is not None:
                    try:
                        wall_to_first_token_ms = int(routing.get("wallToFirstTokenMs"))
                    except (TypeError, ValueError):
                        pass
                if routing.get("spokenStreamed") is not None:
                    spoken_streamed = bool(routing.get("spokenStreamed"))
                raw_breakdown = routing.get("latencyBreakdown")
                if isinstance(raw_breakdown, dict):
                    unified_breakdown = safe_normalize_stored_dict(raw_breakdown)
                # First routing intelligence (before kernel) ≈ classify+setup wall.
                if (
                    classify_done_ms is None
                    and data.get("answerExplanation") == "Analyzing your request…"
                ):
                    classify_done_ms = int((time.perf_counter() - t_start) * 1000)
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
            async for audio_ev in _emit_tts(chunk):
                yield audio_ev
            if cancelled:
                break
        if cancelled:
            break
    if cancelled:
        spoken_partial = normalize_spoken_text("".join(full_text)) or "".join(full_text)
        if agent_audio_started:
            yield {"type": "voice.agent_speech.end", "cancelled": True, "turn_id": resolved_turn_id}
        yield {
            "type": "voice.session.ended",
            "transcript": spoken_partial,
            "cancelled": True,
            "turn_id": resolved_turn_id,
            "conversation_id": resolved_conversation_id,
            "originating_modality": "voice",
        }
        return
    # Flush remainder before turn.complete so TTFA is measured on short answers.
    rem = text_buffer.strip()
    if rem and not _cancelled():
        async for audio_ev in _emit_tts(rem):
            yield audio_ev
        text_buffer = ""
    if cancelled:
        spoken_partial = normalize_spoken_text("".join(full_text)) or "".join(full_text)
        yield {
            "type": "voice.turn.cancelled",
            "turn_id": resolved_turn_id,
            "conversation_id": resolved_conversation_id,
            "reason": "barge_in_or_client_abort",
            "partial_text": spoken_partial,
        }
        yield {
            "type": "voice.session.ended",
            "transcript": spoken_partial,
            "cancelled": True,
            "turn_id": resolved_turn_id,
            "conversation_id": resolved_conversation_id,
            "originating_modality": "voice",
        }
        return
    if agent_audio_started:
        yield {"type": "voice.agent_speech.end", "turn_id": resolved_turn_id}
    spoken_full_text = normalize_spoken_text("".join(full_text)) or "".join(full_text)
    if pending_complete is not None:
        yield {
            "type": "voice.turn.complete",
            "message_id": pending_complete.message_id,
            "model": pending_complete.model,
            "text": spoken_full_text,
            "turn_id": resolved_turn_id,
            "conversation_id": resolved_conversation_id,
            "originating_modality": "voice",
            "cancelled": False,
                "latency_ms": {
                    "total": int((time.perf_counter() - t_start) * 1000),
                    "ttft_ms": first_text_ms,
                    "ttfa_ms": first_audio_ms,
                    "cognitive_stage_ms": stage_ms,
                    "reasoning_depth": reasoning_depth,
                    "routing_tier": routing_tier,
                    "effective_mode": effective_mode,
                    "cached_prompt_tokens": cached_prompt_tokens,
                    "cached_prompt_ratio": cached_prompt_ratio,
                    # Cold-path attribution (wall clocks from voice session start).
                    "classify_setup_ms": classify_done_ms,
                    "pre_act_done_ms": pre_act_done_ms,
                    "pre_act_to_ttft_ms": (
                        None
                        if first_text_ms is None or pre_act_done_ms is None
                        else max(0, int(first_text_ms) - int(pre_act_done_ms))
                    ),
                    "ttft_to_ttfa_ms": (
                        None
                        if first_text_ms is None or first_audio_ms is None
                        else max(0, int(first_audio_ms) - int(first_text_ms))
                    ),
                    "model_ttft_ms": model_ttft_ms,
                    "pre_model_ms": pre_model_ms,
                    "wall_to_first_token_ms": wall_to_first_token_ms,
                    "spoken_streamed": spoken_streamed,
                    "unified_breakdown": unified_breakdown or None,
                },
        }
    yield {
        "type": "voice.session.ended",
        "transcript": spoken_full_text,
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
