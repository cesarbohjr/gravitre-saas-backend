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
from app.services.tier1_voice_service import VoiceProviderError, synthesize_speech_stream
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

# Single-marker emphasis. Only the ``**``/``__``/backtick forms were stripped
# before, so production voice turns still carried "*skipped*" into TTS
# (measured 2026-09-08). Bounded to marker pairs at word boundaries so an
# identifier keeps its inner punctuation: "assistant_workflow_runs" must not
# collapse to "assistantworkflowruns", which is markdown's own rule for
# intra-word underscores.
_ITALIC_ASTERISK = re.compile(r"(?<![A-Za-z0-9*])\*([^*\n]+)\*(?![A-Za-z0-9*])")
_ITALIC_UNDERSCORE = re.compile(r"(?<![A-Za-z0-9_])_([^_\n]+)_(?![A-Za-z0-9_])")
_STRIKETHROUGH = re.compile(r"~~([^~\n]+)~~")
# Any asterisk still standing after paired forms are resolved is a stray
# marker, never speakable content.
_STRAY_ASTERISK = re.compile(r"\*+")

# Cached TTS of the standing PERCEIVE draft (same sentence every operator turn).
# Keyed by voice/model/format so Metric A is not charged a cold ElevenLabs hop
# on every subsequent turn in this worker.
_PERCEIVE_TTS_CACHE: dict[tuple[str, str, str], list[bytes]] = {}

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


def split_speakable_chunks(
    buffer: str,
    *,
    min_chars: int = 12,
    aggressive: bool = False,
) -> tuple[list[str], str]:
    """Emit speakable chunks at sentence boundaries; keep remainder provisional.

    Short provisional answers (under ~48 chars) flush on a word boundary once
    ``min_chars`` is met so TTFA does not wait for terminal punctuation
    (e.g. "Two plus two" while "equals four." is still generating). Longer
    buffers keep a higher clause floor to avoid a TTS round-trip per phrase.

    When ``aggressive`` is True (Voice 3.0 Phase 4), short-buffer flushes use
    a lower clause floor and may split on commas earlier for faster first audio.
    """
    parts = _SENTENCE_END.split(buffer)
    if len(parts) <= 1:
        stripped = buffer.rstrip()
        # Complete sentence with terminal punct but no trailing whitespace yet
        # (common for short voice answers like "Four.").
        if stripped and stripped[-1] in ".!?" and len(stripped) >= 2:
            return [stripped], ""
        short_threshold = 48
        # Short answers: early word-boundary flush. Longer: higher floor.
        if aggressive:
            clause_floor = min_chars
            cut_tail = 1
            space_tail = 1
        else:
            clause_floor = min_chars if len(buffer) < short_threshold else max(min_chars * 2, 40)
            cut_tail = 2 if len(buffer) < short_threshold else 10
            space_tail = 1 if len(buffer) < short_threshold else 5
        if len(buffer) >= clause_floor and (" " in buffer):
            idx = buffer.rfind(", ", 0, max(len(buffer) - cut_tail, 0))
            if aggressive and idx < min_chars and len(buffer) >= min_chars * 2:
                idx = buffer.rfind(",", 0, max(len(buffer) - 1, min_chars))
            if idx < min_chars:
                idx = buffer.rfind(" ", 0, max(len(buffer) - space_tail, min_chars))
            if idx >= min_chars:
                return [buffer[:idx].strip()], buffer[idx:].lstrip()
        return [], buffer
    ready = [p.strip() for p in parts[:-1] if p.strip()]
    return ready, parts[-1]


def strip_markdown_inline(text: str) -> str:
    """Remove markdown markers from one line, preserving the words themselves.

    Shared by ``normalize_spoken_text`` (TTS) and the client-facing delta filter
    in ``pipecat_voice/spoken_stream_filter.py`` so the two can never disagree
    about what counts as a marker.

    Deliberately does NOT touch leading list/heading markers or whitespace — the
    callers own those, because a streaming caller cannot always tell whether it
    is positioned at the start of a line.
    """
    out = (text or "").replace("**", "").replace("__", "").replace("`", "")
    out = _MARKDOWN_LINK.sub(r"\1", out)
    out = _STRIKETHROUGH.sub(r"\1", out)
    out = _ITALIC_ASTERISK.sub(r"\1", out)
    out = _ITALIC_UNDERSCORE.sub(r"\1", out)
    return _STRAY_ASTERISK.sub("", out)


def normalize_spoken_text(text: str) -> str:
    """Strip visual markdown/list formatting for natural spoken delivery."""
    lines: list[str] = []
    for raw in (text or "").replace("\r\n", "\n").split("\n"):
        line = raw.strip()
        if not line:
            continue
        line = _MARKDOWN_LINK.sub(r"\1", line)
        line = _LEADING_FORMAT.sub("", line)
        line = strip_markdown_inline(line).strip()
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
    t_start = time.perf_counter()
    from app.operators.stream_events import AssistantStreamComplete, AssistantStreamEvent
    from app.services.operator_task_intent import (
        looks_like_operator_task,
        resolve_voice_session_intelligence_mode,
    )
    from app.services.tier1_voice_service import normalize_elevenlabs_output_format

    profile = normalize_voice_profile((agent or {}).get("voice_profile"))
    resolved_voice = voice_id or profile.get("voice_id") or profile.get("voice_key")
    model = tts_model or profile.get("tts_model") or "eleven_flash_v2_5"
    from app.services.pipecat_voice.voice_latency_tuning import resolve_voice_tts_chunk_tuning

    chunk_tuning = resolve_voice_tts_chunk_tuning(settings)
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
    text_buffer = ""
    full_text: list[str] = []
    first_text_ms: int | None = None
    first_audio_ms: int | None = None
    first_text_preview: str | None = None
    loop_stage_spoken = False
    operator_task = False
    metric_a_recorded = False
    agent_audio_started = False
    cancelled = False
    tts_failed = False
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
        nonlocal first_audio_ms, agent_audio_started, cancelled, tts_failed, metric_a_recorded
        spoken_chunk = normalize_spoken_text(chunk)
        if not spoken_chunk:
            return
            yield  # pragma: no cover — keeps this an async generator
        if tts_failed:
            return
            yield  # pragma: no cover — keeps this an async generator
        if _cancelled():
            cancelled = True
            return
            yield  # pragma: no cover — keeps this an async generator
        first_piece = True
        from app.services.voice_slo import EARLY_PERCEIVE_DRAFT

        perceive_text = normalize_spoken_text(EARLY_PERCEIVE_DRAFT)
        cache_key = (
            str(resolved_voice or ""),
            str(model or ""),
            str(tts_output_format),
        )
        cached_pieces = (
            _PERCEIVE_TTS_CACHE.get(cache_key)
            if spoken_chunk == perceive_text
            else None
        )
        collected: list[bytes] = []
        try:
            audio_iter = (
                iter(cached_pieces)
                if cached_pieces is not None
                else synthesize_speech_stream(
                    settings,
                    text=spoken_chunk,
                    voice_key=resolved_voice,
                    model_id=model,
                    output_format=tts_output_format,
                )
            )
            for audio in audio_iter:
                if _cancelled():
                    cancelled = True
                    return
                if not audio:
                    continue
                if first_audio_ms is None:
                    first_audio_ms = int((time.perf_counter() - t_start) * 1000)
                    yield {
                        "type": "voice.ttfa",
                        "ms": first_audio_ms,
                        "turn_id": resolved_turn_id,
                        "metric": "A",
                    }
                    if not metric_a_recorded:
                        metric_a_recorded = True
                        from app.services.pipecat_voice.voice_latency_metrics import (
                            record_voice_slo_metric,
                        )
                        from app.services.voice_slo import METRIC_A_ID, is_metric_a_source

                        record_voice_slo_metric(
                            settings,
                            metric=METRIC_A_ID,
                            org_id=org_id,
                            user_id=user_id,
                            conversation_id=resolved_conversation_id,
                            ms=first_audio_ms,
                            source=is_metric_a_source(
                                first_text_preview,
                                loop_stage="PERCEIVE" if loop_stage_spoken else None,
                            ),
                            operator_task=operator_task or loop_stage_spoken,
                            composed=True,
                        )
                if not agent_audio_started:
                    agent_audio_started = True
                    yield {"type": "voice.agent_speech.start", "turn_id": resolved_turn_id}
                yield {
                    "type": "voice.audio.delta",
                    "content_type": audio_content_type,
                    "audio_base64": base64.b64encode(audio).decode("ascii"),
                    "text_chunk": spoken_chunk if first_piece else "",
                    "turn_id": resolved_turn_id,
                }
                first_piece = False
                if cached_pieces is None and spoken_chunk == perceive_text:
                    collected.append(audio)
            if cached_pieces is None and spoken_chunk == perceive_text and collected:
                _PERCEIVE_TTS_CACHE[cache_key] = collected
        except VoiceProviderError as exc:
            tts_failed = True
            from app.services.response_composer import TTS_SAFE_ERROR

            yield {
                "type": "voice.error",
                "detail": TTS_SAFE_ERROR,
                "error_class": exc.error_class or "service_failure",
                "billing_issue": bool((exc.error_class or "") == "billing" or exc.status_code == 402),
                "provider": "elevenlabs",
                "turn_id": resolved_turn_id,
            }
            return
        except Exception:  # noqa: BLE001
            tts_failed = True
            from app.services.response_composer import TTS_SAFE_ERROR

            yield {
                "type": "voice.error",
                "detail": TTS_SAFE_ERROR,
                "error_class": "service_failure",
                "billing_issue": False,
                "provider": "elevenlabs",
                "turn_id": resolved_turn_id,
            }
            return

    early_perceive_draft: str | None = None
    if looks_like_operator_task(text):
        from app.services.voice_slo import EARLY_PERCEIVE_DRAFT

        early_perceive_draft = EARLY_PERCEIVE_DRAFT
        if early_perceive_draft:
            operator_task = True
            loop_stage_spoken = True
            yield {
                "type": "voice.text.delta",
                "delta": early_perceive_draft,
                "turn_id": resolved_turn_id,
            }
            if first_text_ms is None:
                first_text_ms = int((time.perf_counter() - t_start) * 1000)
                first_text_preview = early_perceive_draft[:200]
                yield {"type": "voice.ttft", "ms": first_text_ms, "turn_id": resolved_turn_id}
            full_text.append(early_perceive_draft)
            async for audio_ev in _emit_tts(early_perceive_draft):
                yield audio_ev

    from app.operators.agent_intelligence import get_agent_intelligence

    intelligence = get_agent_intelligence()
    async for event in intelligence.execute_task_streaming(
        settings=settings,
        org_id=org_id,
        user_id=user_id,
        query=text,
        agent_id=str((agent or {}).get("id") or "") or None,
        conversation_history=conversation_history,
        conversation_id=resolved_conversation_id,
        spoken_mode=True,
        mode=resolve_voice_session_intelligence_mode(text),
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
            # Store terminal model payload; we emit turn.complete once text is final.
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
                if routing.get("cognitiveLoop") or data.get("cognitiveLoop"):
                    yield {
                        "type": "voice.cognitive_loop",
                        "cognitive_loop": {
                            "fullLoop": routing.get("fullLoop"),
                            "operatorTask": routing.get("operatorTask"),
                            "fastPath": routing.get("fastPath"),
                            "stages": routing.get("stages"),
                            "loopId": routing.get("loopId"),
                            "turnId": routing.get("turnId"),
                            "spokenMode": True,
                        },
                        "progress_steps": data.get("progressSteps") or [],
                        "turn_id": resolved_turn_id,
                    }
                if routing.get("operatorTask"):
                    operator_task = True
                raw_breakdown = routing.get("latencyBreakdown")
                if isinstance(raw_breakdown, dict):
                    unified_breakdown = safe_normalize_stored_dict(raw_breakdown)
                # First routing intelligence (before kernel) ≈ classify+setup wall.
                if (
                    classify_done_ms is None
                    and data.get("answerExplanation")
                    in (
                        "Analyzing your request…",
                        "Understanding your request",
                    )
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
        if early_perceive_draft and delta.strip() == early_perceive_draft.strip():
            continue
        yield {"type": "voice.text.delta", "delta": delta, "turn_id": resolved_turn_id}
        if first_text_ms is None:
            first_text_ms = int((time.perf_counter() - t_start) * 1000)
            first_text_preview = delta[:200]
            from app.services.voice_slo import is_metric_a_source

            if is_metric_a_source(delta).startswith("loop_stage:"):
                loop_stage_spoken = True
            yield {"type": "voice.ttft", "ms": first_text_ms, "turn_id": resolved_turn_id}
        full_text.append(delta)
        text_buffer += delta
        chunks, text_buffer = split_speakable_chunks(
            text_buffer,
            min_chars=chunk_tuning.min_chars,
            aggressive=chunk_tuning.v2_enabled,
        )
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
    # Emit turn completion as soon as model text is complete so chat text does not
    # wait on downstream TTS transport. Prefer the kernel's final payload when LIVE
    # streamed Register-5 prose and orchestration later replaced it.
    streamed_joined = "".join(full_text)
    complete_text = (
        str(pending_complete.full_content or "").strip()
        if pending_complete is not None
        else ""
    )
    canonical = complete_text if complete_text else streamed_joined
    spoken_full_text = normalize_spoken_text(canonical) or canonical
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
                    "metric_a_ms": first_audio_ms,
                    "metric_b_ms": int((time.perf_counter() - t_start) * 1000),
                },
        }
        from app.services.pipecat_voice.voice_latency_metrics import record_voice_slo_metric
        from app.services.voice_slo import METRIC_B_ID, operator_task_for_metric_b

        completion_ms = int((time.perf_counter() - t_start) * 1000)
        if operator_task_for_metric_b(
            operator_task=operator_task,
            loop_stage_spoken=loop_stage_spoken,
            tool_results=getattr(pending_complete, "tool_results", None),
        ):
            record_voice_slo_metric(
                settings,
                metric=METRIC_B_ID,
                org_id=org_id,
                user_id=user_id,
                conversation_id=resolved_conversation_id,
                ms=completion_ms,
                source="composed_final",
                operator_task=True,
                composed=True,
            )
    # Flush remainder after turn.complete so audio may continue even after text is rendered.
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
