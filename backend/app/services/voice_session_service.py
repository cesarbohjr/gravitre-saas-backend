"""Streaming voice session over the existing unified-turn / SSE chat backbone.

Flow:
  Deepgram live partials → provisional turn-taking → finalize user turn
  → execute_task_streaming(spoken_mode=True) → sentence-chunk TTS stream
  → same write-confirm / GIBE paths as text.
"""
from __future__ import annotations

import asyncio
import base64
import re
import time
import uuid
from collections.abc import AsyncIterator, Callable
from typing import Any

from app.config import Settings
from app.core.logging import get_logger
from app.core.safe_dict import safe_normalize_stored_dict
from app.services.pipecat_voice.spoken_formatting import split_sentence_chunks
from app.services.tier1_voice_service import VoiceProviderError, synthesize_speech_stream
from app.services.voice_agent_profile import normalize_voice_profile, resolve_session_voice
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

logger = get_logger(__name__)

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

# Cached TTS of the standing drafts (the same sentence on every matching turn:
# the PERCEIVE draft and the plan-hold draft, see voice_slo.standing_spoken_drafts).
# Keyed by voice/model/format/text so Metric A is not charged a cold ElevenLabs
# hop on every subsequent turn in this worker.
_PERCEIVE_TTS_CACHE: dict[tuple[str, str, str, str], list[bytes]] = {}


def _standing_draft_texts() -> set[str]:
    from app.services.voice_slo import standing_spoken_drafts

    return {t for t in (normalize_spoken_text(d) for d in standing_spoken_drafts()) if t}


def warm_perceive_tts_cache(settings: Settings, *, voice_key: str | None = None) -> bool:
    """Pre-synthesize the standing drafts for the default voice (worker startup)."""
    texts = sorted(_standing_draft_texts())
    if not texts:
        return False
    resolved_voice = voice_key or "sarah"
    model = "eleven_flash_v2_5"
    fmt = "mp3_44100_128"
    warmed = False
    for spoken in texts:
        cache_key = (str(resolved_voice), str(model), str(fmt), spoken)
        if cache_key in _PERCEIVE_TTS_CACHE:
            warmed = True
            continue
        try:
            chunks = list(
                synthesize_speech_stream(
                    settings,
                    text=spoken,
                    voice_key=resolved_voice,
                    model_id=model,
                    output_format=fmt,
                )
            )
        except Exception as exc:  # noqa: BLE001 — best-effort warm, never fail startup
            logger.debug("voice_standing_draft_tts_warm_failed err=%s", exc)
            continue
        if chunks:
            _PERCEIVE_TTS_CACHE[cache_key] = chunks
            warmed = True
    return warmed


def peek_cached_perceive_chunks(
    *,
    voice_key: str | None = None,
    model: str = "eleven_flash_v2_5",
    output_format: str = "mp3_44100_128",
) -> list[bytes]:
    """In-process PERCEIVE TTS warmup (same worker). Empty on cache miss."""
    from app.services.voice_slo import EARLY_PERCEIVE_DRAFT

    perceive_text = normalize_spoken_text(EARLY_PERCEIVE_DRAFT)
    if not perceive_text:
        return []
    resolved = (voice_key or "sarah").strip() or "sarah"
    key = (str(resolved), str(model), str(output_format), perceive_text)
    return list(_PERCEIVE_TTS_CACHE.get(key) or [])


def _org_in_allowlist(raw: str | None, org_id: str | None) -> bool:
    """Comma-separated org ids; ``*`` means every org; empty means none."""
    org = (org_id or "").strip().lower()
    if not org:
        return False
    entries = {p.strip().lower() for p in str(raw or "").split(",") if p.strip()}
    return "*" in entries or org in entries


def early_plan_ack_enabled_for(settings: Any, org_id: str | None) -> bool:
    """VOICE_EARLY_PLAN_ACK_ENABLED and the org is on VOICE_EARLY_PLAN_ACK_ORG_IDS."""
    if not bool(getattr(settings, "voice_early_plan_ack_enabled", False)):
        return False
    return _org_in_allowlist(getattr(settings, "voice_early_plan_ack_org_ids", ""), org_id)


def tts_overlap_enabled_for(settings: Any, org_id: str | None) -> bool:
    """VOICE_TTS_OVERLAP_ENABLED and the org is on VOICE_TTS_OVERLAP_ORG_IDS."""
    if not bool(getattr(settings, "voice_tts_overlap_enabled", False)):
        return False
    return _org_in_allowlist(getattr(settings, "voice_tts_overlap_org_ids", ""), org_id)


def _consume_task_result(task: asyncio.Task[Any]) -> None:
    """Retrieve a background task's outcome so it never logs as unhandled."""
    if not task.cancelled():
        task.exception()


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
    """Emit complete speakable thoughts and keep partial phrases provisional.

    ElevenLabs realtime WebSocket auto_mode is optimized for full sentences;
    sending partial sentences markedly reduces synthesis quality. The previous
    implementation flushed short word-boundary fragments (sometimes ~12 chars)
    and normalize_spoken_text then made each fragment look terminal. That
    repeatedly reset prosody and produced choppy, robotic speech.

    The live path now waits for sentence punctuation. A very long unpunctuated
    buffer gets one bounded emergency split so malformed/model-streamed text
    cannot hold audio forever. aggressive only lowers that emergency ceiling;
    it no longer turns ordinary partial phrases into standalone utterances.
    """
    # Sentence ends, skipping periods that do not end one ("e.g.", "Dr.",
    # "U.S.", initials, decimals, times, versions, domains and addresses).
    sentences = split_sentence_chunks(buffer)
    if sentences is not None:
        return sentences

    hard_ceiling = max(120 if aggressive else 180, max(1, min_chars) * 8)
    if len(buffer) < hard_ceiling:
        return [], buffer

    floor = max(48, min_chars * 3)
    search_end = max(floor + 1, hard_ceiling - 24)
    candidates: list[int] = []
    for marker in ("; ", ": ", ", ", " — ", " – "):
        idx = buffer.rfind(marker, floor, search_end)
        if idx >= floor:
            candidates.append(idx + len(marker.rstrip()))
    if candidates:
        idx = max(candidates)
        return [buffer[:idx].strip()], buffer[idx:].lstrip()

    idx = buffer.rfind(" ", floor, search_end)
    if idx >= floor:
        return [buffer[:idx].strip()], buffer[idx:].lstrip()

    return [], buffer


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
        # A line that is only links ("[View in Gmail](…)") is for the screen.
        if _MARKDOWN_LINK.search(line) and not _MARKDOWN_LINK.sub("", line).strip(" .,;·|-"):
            continue
        line = _MARKDOWN_LINK.sub(r"\1", line)
        line = _LEADING_FORMAT.sub("", line)
        line = strip_markdown_inline(line).strip()
        line = re.sub(r"\s{2,}", " ", line).strip()
        if not line:
            continue
        if line[-1] not in ".!?:":
            line = f"{line}."
        lines.append(line)
    return " ".join(lines).strip()


_DIGIT_WORDS = {
    "zero": "0",
    "oh": "0",
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
}

_SPOKEN_EMAIL = re.compile(
    r"(?i)\bemail\s+"
    r"([A-Za-z][A-Za-z0-9 \-]{1,96}?)"
    r"\s+at\s+"
    r"((?:[A-Za-z0-9]+\s+dot\s+){1,}[A-Za-z0-9]+(?:\s+dot\s+[A-Za-z0-9]+)*)"
)


def _spoken_local_part(raw: str) -> str:
    pieces: list[str] = []
    for token in re.split(r"[\s\-]+", raw.strip()):
        low = token.lower().strip(".,:;\"'")
        if not low:
            continue
        if low in _DIGIT_WORDS:
            pieces.append(_DIGIT_WORDS[low])
        else:
            pieces.append(re.sub(r"[^a-z0-9]+", "", low))
    return "".join(pieces)


_DIGIT_WORD_RUN = re.compile(
    r"(?i)(?:(?:zero|oh|one|two|three|four|five|six|seven|eight|nine)(?:\s+)){2,}"
    r"(?:zero|oh|one|two|three|four|five|six|seven|eight|nine)\b"
)


def _collapse_digit_word_runs(text: str) -> str:
    def _replace(match: re.Match[str]) -> str:
        digits: list[str] = []
        for token in match.group(0).split():
            mapped = _DIGIT_WORDS.get(token.lower())
            if mapped is None:
                return match.group(0)
            digits.append(mapped)
        return "".join(digits)

    return _DIGIT_WORD_RUN.sub(_replace, text)


def reconstitute_spoken_identity_fields(text: str) -> str:
    """Recover RFC emails and digit-word runs from ASR before planning.

    Does not invent identities. Email rewrite requires ``email … at … dot …``.
    Digit-word collapse requires three or more consecutive number words.
    """
    if not text:
        return text
    rewritten = text
    if " dot " in f" {text.lower()} ":

        def _replace_email(match: re.Match[str]) -> str:
            local = _spoken_local_part(match.group(1))
            domain = re.sub(r"\s+dot\s+", ".", match.group(2).strip(), flags=re.I)
            domain = re.sub(r"\s+", "", domain).lower()
            if not local or "@" in local or "." not in domain:
                return match.group(0)
            return f"email {local}@{domain}"

        rewritten = _SPOKEN_EMAIL.sub(_replace_email, rewritten)
    return _collapse_digit_word_runs(rewritten)


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
    skip_early_perceive: bool = False,
) -> AsyncIterator[dict[str, Any]]:
    """Run unified-turn streaming + progressive TTS. Yields typed events.

    Background work a turn starts (the TTS overlap workers) is cancelled when
    the consumer stops early (client disconnect), so the engine never keeps
    running for a turn nobody is listening to.
    """
    background: list[asyncio.Task[Any]] = []
    inner = _stream_voice_turn_events(
        settings=settings,
        org_id=org_id,
        user_id=user_id,
        text=text,
        agent=agent,
        conversation_id=conversation_id,
        conversation_history=conversation_history,
        voice_id=voice_id,
        tts_model=tts_model,
        turn_id=turn_id,
        should_cancel=should_cancel,
        tts_output_format=tts_output_format,
        skip_early_perceive=skip_early_perceive,
        _background_tasks=background,
    )
    try:
        async for event in inner:
            yield event
    finally:
        for task in background:
            if not task.done():
                task.cancel()
        await inner.aclose()


async def _stream_voice_turn_events(
    *,
    settings: Settings,
    org_id: str,
    user_id: str,
    text: str,
    agent: dict[str, Any] | None,
    conversation_id: str | None,
    conversation_history: list[dict[str, Any]] | None,
    voice_id: str | None,
    tts_model: str | None,
    turn_id: str | None,
    should_cancel: Callable[[], bool] | None,
    tts_output_format: str,
    skip_early_perceive: bool,
    _background_tasks: list[asyncio.Task[Any]],
) -> AsyncIterator[dict[str, Any]]:
    t_start = time.perf_counter()
    from app.operators.stream_events import AssistantStreamComplete, AssistantStreamEvent
    from app.services.operator_task_intent import (
        looks_like_operator_task,
        resolve_voice_turn_routing,
    )
    from app.services.tier1_voice_service import normalize_elevenlabs_output_format

    profile = normalize_voice_profile((agent or {}).get("voice_profile"))
    # Agent profile wins over the request voice (same precedence as Pipecat WS).
    resolved_voice = resolve_session_voice(agent, voice_id)
    model = tts_model or profile.get("tts_model") or "eleven_flash_v2_5"
    from app.services.pipecat_voice.voice_latency_tuning import resolve_voice_tts_chunk_tuning

    chunk_tuning = resolve_voice_tts_chunk_tuning(settings)
    resolved_turn_id = (turn_id or "").strip() or str(uuid.uuid4())
    resolved_conversation_id = (conversation_id or "").strip() or None
    _fmt, audio_content_type = normalize_elevenlabs_output_format(tts_output_format)
    tts_output_format = _fmt
    write_stop_armed = False

    def _cancelled() -> bool:
        nonlocal write_stop_armed
        hit = False
        if should_cancel and should_cancel():
            hit = True
        elif is_turn_cancelled(resolved_turn_id):
            hit = True
        if hit and not write_stop_armed and org_id and resolved_conversation_id:
            write_stop_armed = True
            from app.services.voice_barge_in_write import mark_voice_barge_in_stop

            mark_voice_barge_in_stop(
                org_id=org_id,
                conversation_id=resolved_conversation_id,
                settings=settings,
                user_id=user_id,
            )
        return hit

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
    persist_task: asyncio.Task[tuple[str | None, str | None]] | None = None

    async def _persist_turn(complete: AssistantStreamComplete, assistant_text: str) -> tuple[str | None, str | None]:
        """Save the finished turn server-side, the same store and memory as text and Pipecat."""
        from app.services.shared_turn_preparation import persist_completed_turn, persist_turn_summary

        try:
            persisted_id, assistant_id = await asyncio.to_thread(
                persist_completed_turn,
                settings,
                org_id=org_id,
                user_id=user_id,
                conversation_id=resolved_conversation_id,
                user_text=text,
                assistant_text=assistant_text,
                complete=complete,
            )
            if persisted_id:
                await asyncio.to_thread(
                    persist_turn_summary,
                    settings,
                    conversation_id=persisted_id,
                    org_id=org_id,
                    user_id=user_id,
                    complete=complete,
                )
            return persisted_id, assistant_id
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "voice_http_turn_persist_failed org_id=%s conversation_id=%s error=%s",
                org_id,
                resolved_conversation_id,
                str(exc),
            )
            return None, None

    async def _finish_persist() -> None:
        nonlocal resolved_conversation_id, persist_task
        if persist_task is None:
            return
        task, persist_task = persist_task, None
        persisted_id, _ = await task
        if persisted_id:
            resolved_conversation_id = persisted_id

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
        standing = spoken_chunk in _standing_draft_texts()
        cache_key = (
            str(resolved_voice or ""),
            str(model or ""),
            str(tts_output_format),
            spoken_chunk,
        )
        cached_pieces = _PERCEIVE_TTS_CACHE.get(cache_key) if standing else None
        collected: list[bytes] = []
        try:
            if cached_pieces is not None:
                audio_chunks = cached_pieces
            else:

                def _fetch_chunks() -> list[bytes]:
                    return list(
                        synthesize_speech_stream(
                            settings,
                            text=spoken_chunk,
                            voice_key=resolved_voice,
                            model_id=model,
                            output_format=tts_output_format,
                        )
                    )

                audio_chunks = await asyncio.to_thread(_fetch_chunks)
                if cached_pieces is None and standing and audio_chunks:
                    _PERCEIVE_TTS_CACHE[cache_key] = audio_chunks
            for audio in audio_chunks:
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
                                loop_stage=(early_loop_stage or "PERCEIVE") if loop_stage_spoken else None,
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
                if cached_pieces is None and standing:
                    collected.append(audio)
            if (
                cached_pieces is None
                and standing
                and collected
                and cache_key not in _PERCEIVE_TTS_CACHE
            ):
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

    from app.operators.agent_intelligence import get_agent_intelligence
    from app.services.cognitive_loop_controller import is_plan_without_execute_turn
    from app.services.shared_turn_preparation import (
        TurnGuardrailBlocked,
        build_turn_system_prompt,
        guard_spoken_turn,
        harden_against_injection,
    )

    # Same prompt and guardrails as text chat; only the refusal's presentation differs.
    voice_tier, voice_mode = resolve_voice_turn_routing(text, history=conversation_history)
    logger.info(
        "voice_http_conversation_tier org_id=%s tier=%s reason=%s mode=%s",
        org_id,
        voice_tier.tier,
        voice_tier.reason,
        voice_mode,
    )

    # A fixed early sentence may be said ahead of the engine, but never before
    # the shared safety gate below has allowed the turn. Which sentence (if
    # any) is decided from the words alone, with the same plan-hold test the
    # engine uses, so routing and authorization never depend on it.
    early_perceive_draft: str | None = None
    early_loop_stage: str | None = None
    early_ack_gated = early_plan_ack_enabled_for(settings, org_id)
    if looks_like_operator_task(text):
        if is_plan_without_execute_turn(text):
            # Plan-hold: the engine says this exact sentence at its PLAN stage,
            # but only after retrieval and planning (seconds). It is true as
            # soon as the turn is allowed, so (behind the flag) say it then and
            # drop the engine's copy below. Connector-status asks get no stage
            # speech from the engine either.
            from app.services.connector_status_reply_service import (
                is_connector_status_question,
            )

            if early_ack_gated and not is_connector_status_question(text):
                from app.services.voice_slo import EARLY_PLAN_HOLD_DRAFT

                early_perceive_draft = EARLY_PLAN_HOLD_DRAFT
                early_loop_stage = "PLAN"
        else:
            from app.services.voice_slo import EARLY_PERCEIVE_DRAFT

            early_perceive_draft = EARLY_PERCEIVE_DRAFT or None
            early_loop_stage = "PERCEIVE" if early_perceive_draft else None

    agent_id_for_turn = str((agent or {}).get("id") or "") or None

    async def _build_base_prompt() -> str | None:
        try:
            prompt: str | None = await asyncio.to_thread(
                build_turn_system_prompt,
                settings,
                org_id,
                user_id=user_id,
                agent_id=agent_id_for_turn,
                query=text,
            )
        except Exception as exc:  # noqa: BLE001 - never make Talk unavailable
            logger.warning("voice_http_base_prompt_build_failed org_id=%s err=%s", org_id, exc)
            prompt = None
        if prompt:
            prompt = await harden_against_injection(
                settings,
                org_id=org_id,
                conversation_id=resolved_conversation_id,
                system_prompt=prompt,
                user_text=text,
                surface="voice",
            )
        return prompt

    # The safety gate is the shared guard itself (kill switch, rate limit,
    # budget, input moderation, model policy), not a voice-only check. It
    # screens only what the caller said (guard_spoken_turn never sends the
    # system prompt to moderation), so it does not depend on the prompt build
    # and both start now: the turn waits for the slower of the two instead of
    # their sum.
    gate_started = time.perf_counter()
    guard_task: asyncio.Task[None] = asyncio.create_task(
        guard_spoken_turn(
            settings,
            org_id=org_id,
            user_text=text,
            system_prompt="",
            history=conversation_history,
            mode=voice_mode,
        )
    )
    prompt_task: asyncio.Task[str | None] = asyncio.create_task(_build_base_prompt())
    guard_task.add_done_callback(_consume_task_result)
    prompt_task.add_done_callback(_consume_task_result)
    _background_tasks.extend((guard_task, prompt_task))
    try:
        await guard_task
    except TurnGuardrailBlocked as blocked:
        # Refusal path unchanged: no early sentence, the spoken refusal is the
        # answer. The prompt build finishes first so its injection audit is
        # written exactly as before.
        await prompt_task
        if early_ack_gated:
            yield {
                "type": "voice.safety_gate",
                "verdict": "refused",
                "ms": int((time.perf_counter() - gate_started) * 1000),
                "early_ack": False,
                "turn_id": resolved_turn_id,
            }
        yield {"type": "voice.text.delta", "delta": blocked.spoken, "turn_id": resolved_turn_id}
        async for audio_ev in _emit_tts(blocked.spoken):
            yield audio_ev
        yield {
            "type": "voice.turn.complete",
            "message_id": None,
            "model": f"guardrail:{blocked.kind}",
            "text": blocked.spoken,
            "turn_id": resolved_turn_id,
            "conversation_id": resolved_conversation_id,
            "originating_modality": "voice",
            "cancelled": False,
        }
        return
    except BaseException:
        prompt_task.cancel()
        raise

    early_ack_withheld: str | None = None
    if early_perceive_draft and early_loop_stage == "PLAN":
        from app.services.ai_guardrails import detect_prompt_injection

        if getattr(settings, "prompt_injection_detection_enabled", True) and detect_prompt_injection(text)[0]:
            # The guard allowed it, but the words look like an injection: say
            # nothing ahead of the engine, which runs with the hardened prompt.
            early_ack_withheld = "injection_suspected"
        elif _cancelled():
            early_ack_withheld = "cancelled"
        if early_ack_withheld:
            early_perceive_draft = None
            early_loop_stage = None
    if early_ack_gated:
        yield {
            "type": "voice.safety_gate",
            "verdict": "allowed",
            "ms": int((time.perf_counter() - gate_started) * 1000),
            "early_ack": bool(early_perceive_draft and early_loop_stage == "PLAN"),
            "withheld": early_ack_withheld,
            "turn_id": resolved_turn_id,
        }

    # Set when an early sentence was said, so the engine's identical sentence
    # is dropped once instead of spoken twice.
    early_spoken: str | None = None
    if early_perceive_draft:
        operator_task = True
        loop_stage_spoken = True
        early_spoken = early_perceive_draft
        # The router only pre-speaks the cached PERCEIVE draft.
        if skip_early_perceive and early_loop_stage == "PERCEIVE":
            full_text.append(early_perceive_draft)
        else:
            delta_event: dict[str, Any] = {
                "type": "voice.text.delta",
                "delta": early_perceive_draft,
                "turn_id": resolved_turn_id,
            }
            if early_loop_stage == "PLAN":
                delta_event["early_ack"] = True
            yield delta_event
            if first_text_ms is None:
                first_text_ms = int((time.perf_counter() - t_start) * 1000)
                first_text_preview = early_perceive_draft[:200]
                yield {"type": "voice.ttft", "ms": first_text_ms, "turn_id": resolved_turn_id}
            full_text.append(early_perceive_draft)
            async for audio_ev in _emit_tts(early_perceive_draft):
                yield audio_ev
        if cancelled or _cancelled():
            # Barge-in during the early sentence: stop here. The engine never
            # starts, so nothing runs and nothing is said twice.
            prompt_task.cancel()
            spoken_partial = normalize_spoken_text("".join(full_text)) or "".join(full_text)
            yield {
                "type": "voice.turn.cancelled",
                "turn_id": resolved_turn_id,
                "conversation_id": resolved_conversation_id,
                "reason": "barge_in_or_client_abort",
                "partial_text": spoken_partial,
            }
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

    base_prompt: str | None = await prompt_task

    intelligence = get_agent_intelligence()
    kernel_stream = intelligence.execute_task_streaming(
        settings=settings,
        org_id=org_id,
        user_id=user_id,
        query=text,
        agent_id=agent_id_for_turn,
        conversation_history=conversation_history,
        conversation_id=resolved_conversation_id,
        spoken_mode=True,
        mode=voice_mode,
        assistant_base_prompt=base_prompt,
    )

    # TTS overlap (flagged): finished sentences are synthesized by one
    # background worker, in order, while the engine keeps running. Without it
    # the engine is paused on every sentence's TTS round trip, which Metric B
    # (time to the final composed answer) pays once per sentence. The engine,
    # its inputs and every policy check are the same either way.
    tts_queue: asyncio.Queue[str | None] | None = None
    overlap_out: asyncio.Queue[tuple[str, Any]] | None = None
    if tts_overlap_enabled_for(settings, org_id):
        tts_queue = asyncio.Queue()
        overlap_out = asyncio.Queue()

        async def _pump_kernel() -> None:
            assert overlap_out is not None
            try:
                async for kernel_event in kernel_stream:
                    overlap_out.put_nowait(("kernel", kernel_event))
            except Exception as exc:  # noqa: BLE001 - re-raised by the consumer
                overlap_out.put_nowait(("kernel_error", exc))
                return
            overlap_out.put_nowait(("kernel_done", None))

        async def _pump_audio() -> None:
            assert tts_queue is not None and overlap_out is not None
            while True:
                chunk = await tts_queue.get()
                if chunk is None:
                    break
                async for audio_event in _emit_tts(chunk):
                    overlap_out.put_nowait(("audio", audio_event))
                if cancelled:
                    break
            overlap_out.put_nowait(("audio_done", None))

        for coro in (_pump_kernel(), _pump_audio()):
            task = asyncio.create_task(coro)
            task.add_done_callback(_consume_task_result)
            _background_tasks.append(task)

    async def _turn_events() -> AsyncIterator[tuple[str, Any]]:
        if overlap_out is None:
            async for kernel_event in kernel_stream:
                yield "kernel", kernel_event
            return
        while True:
            kind, item = await overlap_out.get()
            if kind == "kernel_done":
                return
            if kind == "kernel_error":
                raise item
            yield kind, item

    async def _speak(chunk: str) -> AsyncIterator[dict[str, Any]]:
        if tts_queue is not None:
            tts_queue.put_nowait(chunk)
            return
            yield  # pragma: no cover — keeps this an async generator
        async for audio_event in _emit_tts(chunk):
            yield audio_event

    async def _finish_overlap_audio() -> AsyncIterator[dict[str, Any]]:
        """After the engine is done, let the queued sentences finish speaking."""
        if tts_queue is None or overlap_out is None:
            return
            yield  # pragma: no cover — keeps this an async generator
        tts_queue.put_nowait(None)
        while True:
            kind, item = await overlap_out.get()
            if kind == "audio_done":
                return
            if kind == "audio":
                yield item

    def _stop_background() -> None:
        for task in _background_tasks:
            if not task.done():
                task.cancel()

    turn_events = _turn_events()
    async for source, event in turn_events:
        if source == "audio":
            yield event
            if cancelled:
                break
            continue
        if source == "audio_done":
            # The TTS worker only stops early on a barge-in.
            if cancelled:
                break
            continue
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
        if early_spoken:
            # The engine's own copy of a sentence already said: drop it,
            # whether it arrives alone or at the head of a longer delta.
            said = early_spoken.strip()
            if delta.strip() == said:
                continue
            if delta.lstrip().startswith(said):
                delta = delta.lstrip()[len(said):].lstrip()
                if not delta:
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
            async for audio_ev in _speak(chunk):
                yield audio_ev
            if cancelled:
                break
        if cancelled:
            break
    await turn_events.aclose()
    if cancelled:
        _stop_background()
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
        # Persist in the background so the remaining audio is not held up by the write.
        persist_task = asyncio.create_task(_persist_turn(pending_complete, canonical.strip()))
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
        try:
            from app.services.turn_latency_trace import (
                build_voice_http_turn_marks,
                record_voice_turn_critical_path,
            )

            breakdown_ints: dict[str, int] = {}
            if isinstance(unified_breakdown, dict):
                for key, raw in unified_breakdown.items():
                    if isinstance(raw, (int, float)):
                        breakdown_ints[str(key)] = int(raw)
            voice_marks = build_voice_http_turn_marks(
                completion_ms=completion_ms,
                first_text_ms=first_text_ms,
                first_audio_ms=first_audio_ms,
                classify_done_ms=classify_done_ms,
                pre_act_done_ms=pre_act_done_ms,
                unified_breakdown=breakdown_ints or None,
            )
            record_voice_turn_critical_path(
                settings,
                org_id=org_id,
                user_id=user_id,
                conversation_id=resolved_conversation_id,
                turn_id=resolved_turn_id,
                marks=voice_marks,
                transport="http_talk",
            )
        except Exception:  # noqa: BLE001
            pass
    # Flush remainder after turn.complete so audio may continue even after text is rendered.
    rem = text_buffer.strip()
    if rem and not _cancelled():
        async for audio_ev in _speak(rem):
            yield audio_ev
        text_buffer = ""
    async for audio_ev in _finish_overlap_audio():
        yield audio_ev
    _stop_background()
    await _finish_persist()
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
