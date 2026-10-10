"""One latency record per spoken turn, every stage on one clock.

The existing samples (``voice.turn_latency.llm_stage`` from the LLM bridge and
``voice.turn_latency.e2e`` from the latency observer) are separate rows with
separate clocks, so no single row says where one turn's time went. This
collects the stage timestamps that the observer, the LLM bridge, the brain
(its ``_mark`` checkpoints) and the browser (``playback.started``) already
see, and writes them as one ``runtime.turn_latency.critical_path`` row per turn
through ``record_voice_turn_critical_path`` — the same table and helper as
before, not a parallel metrics system.

All timestamps are ``time.perf_counter()`` seconds. The reference point of a
turn is the end of the user's speech as the server can see it: the last
interim transcript before the turn's final transcript (Flux stops sending
interims when speech stops), falling back to the eager / committed end of turn.
"""
from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

from app.core.logging import get_logger
from app.core.safe_dict import safe_normalize_stored_dict

logger = get_logger(__name__)

# How long a finished turn waits for the browser's playback report before it is
# written without one (the report normally arrives within one round trip).
PLAYBACK_REPORT_GRACE_S = 4.0
# Brain checkpoints recorded after the model already answered; they never
# close the pre-LLM stretch.
_POST_LLM_MARKS = frozenset(
    {"composer_complete", "first_sse", "turn_complete", "shortcut_composer_end", "shortcut_first_text_delta"}
)
# Brain checkpoints that bracket intent / tier classification.
_CLASSIFICATION_SPANS = (
    ("workspace_focus_resolved", "intent_gateway"),
    ("engine_settings", "routing_classified"),
)


def resolve_turn_tier(data: dict[str, Any] | None, bridge_tier: str | None = None) -> tuple[str | None, str]:
    """The turn's conversation tier as the brain recorded it.

    The brain classifies every turn (``loop_trace.conversation_tier``) and puts
    it on the intelligence event as ``routing.conversationTier``; that wins.
    Before that event arrives (or when the brain never emits it, e.g. a refused
    turn) the bridge's own classification of the same text and history is used.
    Nothing is inferred from mode or checkpoints.
    """
    data = data if isinstance(data, dict) else {}
    routing = data.get("routing") if isinstance(data.get("routing"), dict) else {}
    for source in (routing, data):
        for key in ("conversationTier", "conversation_tier"):
            value = str(source.get(key) or "").strip().lower()
            if value in _TIERS:
                return value, "brain"
    value = str(bridge_tier or "").strip().lower()
    if value in _TIERS:
        return value, "bridge"
    return None, "unknown"


_TIERS = frozenset({"light", "medium", "deep"})


def _ms(later: float | None, earlier: float | None) -> int | None:
    if later is None or earlier is None:
        return None
    return int(round((later - earlier) * 1000))


@dataclass
class _TurnTimes:
    speech_end: float | None = None
    eager_eot: float | None = None
    stt_final: float | None = None
    user_stopped: float | None = None
    committed: float | None = None
    durable_ready: float | None = None
    prompt_ready: float | None = None
    guard_done: float | None = None
    brain_t0: float | None = None
    brain_marks: dict[str, int] = field(default_factory=dict)
    first_token: float | None = None
    first_speakable: float | None = None
    tts_requested: float | None = None
    tts_first_audio: float | None = None
    audio_out: float | None = None
    playback_report_rx: float | None = None
    client_receive_to_playback_ms: float | None = None
    bridge_done: float | None = None
    e2e_ms: int | None = None
    ttfb_by_processor_ms: dict[str, int] = field(default_factory=dict)
    intelligence: dict[str, Any] = field(default_factory=dict)
    turn_id: str | None = None
    speculative_outcome: str | None = None
    speculation: dict[str, Any] = field(default_factory=dict)
    tier_override: str | None = None


class VoiceTurnTrace:
    """Per-socket collector; one ``_TurnTimes`` per committed user turn."""

    def __init__(
        self,
        *,
        writer: Callable[..., Any] | None = None,
        clock: Callable[[], float] = time.perf_counter,
        transport: str = "pipecat_duplex",
    ) -> None:
        self._writer = writer
        self._clock = clock
        self._transport = transport
        # User-speech timestamps arrive before the turn they belong to is committed.
        self._pending_user = _TurnTimes()
        self._last_interim: float | None = None
        self._turn: _TurnTimes | None = None
        self._flush_handle: asyncio.TimerHandle | None = None
        self.written: list[dict[str, Any]] = []

    def now(self) -> float:
        return self._clock()

    # ---- user speech (latency observer) ------------------------------------
    def on_interim(self, at: float | None = None) -> None:
        self._last_interim = at if at is not None else self.now()

    def on_eager_end_of_turn(self, at: float | None = None) -> None:
        at = at if at is not None else self.now()
        if self._pending_user.eager_eot is None:
            self._pending_user.eager_eot = at
            self._pending_user.speech_end = self._last_interim or at

    def on_stt_final(self, at: float | None = None) -> None:
        at = at if at is not None else self.now()
        if self._pending_user.stt_final is None:
            self._pending_user.stt_final = at
        if self._pending_user.speech_end is None:
            self._pending_user.speech_end = self._last_interim or at

    def on_user_stopped(self, at: float | None = None) -> None:
        at = at if at is not None else self.now()
        if self._pending_user.user_stopped is None:
            self._pending_user.user_stopped = at
        if self._pending_user.speech_end is None:
            self._pending_user.speech_end = self._last_interim or at

    # ---- LLM bridge ---------------------------------------------------------
    def begin_turn(self, at: float | None = None) -> None:
        """The bridge received a committed user turn."""
        self.flush_pending()
        turn = self._pending_user
        self._pending_user = _TurnTimes()
        self._last_interim = None
        turn.committed = at if at is not None else self.now()
        if turn.speech_end is None:
            turn.speech_end = turn.committed
        self._turn = turn

    def note(self, name: str, at: float | None = None) -> None:
        """Bridge stage timestamp: durable_ready, prompt_ready, guard_done,
        first_token, first_speakable, tts_requested."""
        turn = self._turn
        if turn is None or not hasattr(turn, name):
            return
        if getattr(turn, name) is None:
            setattr(turn, name, at if at is not None else self.now())

    def attach_brain_marks(self, marks: dict[str, Any] | None) -> None:
        """The brain's own ``_mark`` checkpoints (ms from its start) plus its start."""
        turn = self._turn
        if turn is None or not isinstance(marks, dict):
            return
        t0 = marks.get("_t0_perf")
        if isinstance(t0, (int, float)):
            turn.brain_t0 = float(t0)
        for key, value in marks.items():
            if not str(key).startswith("_") and isinstance(value, (int, float)):
                turn.brain_marks[str(key)] = int(value)

    def attach_intelligence(self, data: dict[str, Any] | None) -> None:
        turn = self._turn
        if turn is None or not isinstance(data, dict):
            return
        for key in ("effectiveMode", "routingTier", "pipelineTier", "conversationTier", "conversation_tier"):
            if data.get(key) is not None:
                turn.intelligence[key] = data.get(key)
        routing = data.get("routing")
        if isinstance(routing, dict):
            merged = safe_normalize_stored_dict(turn.intelligence, key="routing")
            for key in (
                "reasoningDepth",
                "modelTtftMs",
                "preModelMs",
                "conversationTier",
                "conversation_tier",
                "conversationTierReason",
                "spokenLitePath",
            ):
                if routing.get(key) is not None:
                    merged[key] = routing.get(key)
            turn.intelligence["routing"] = merged

    def set_turn_meta(
        self,
        *,
        turn_id: str | None = None,
        speculative_outcome: str | None = None,
        tier: str | None = None,
        speculation: dict[str, Any] | None = None,
    ) -> None:
        turn = self._turn
        if turn is None:
            return
        if speculation:
            turn.speculation = dict(speculation)
        if turn_id:
            turn.turn_id = turn_id
        if speculative_outcome:
            turn.speculative_outcome = speculative_outcome
        if tier:
            turn.tier_override = tier

    def end_turn(self) -> None:
        """The bridge finished the turn; write once the playback report is in."""
        turn = self._turn
        if turn is None or turn.bridge_done is not None:
            return
        turn.bridge_done = self.now()
        if turn.playback_report_rx is not None or turn.audio_out is None:
            self.flush_pending()
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            self.flush_pending()
            return
        if self._flush_handle is not None:
            self._flush_handle.cancel()
        self._flush_handle = loop.call_later(PLAYBACK_REPORT_GRACE_S, self.flush_pending)

    # ---- TTS / transport / browser -----------------------------------------
    def on_tts_audio(self, at: float | None = None) -> None:
        turn = self._turn
        if turn is not None and turn.tts_requested is not None and turn.tts_first_audio is None:
            turn.tts_first_audio = at if at is not None else self.now()

    def on_bot_started_speaking(self, at: float | None = None) -> None:
        turn = self._turn
        if turn is not None and turn.audio_out is None:
            turn.audio_out = at if at is not None else self.now()

    def on_observer_breakdown(self, *, e2e_ms: int | None, ttfb_by_processor_ms: dict[str, int] | None) -> None:
        turn = self._turn
        if turn is None:
            return
        if e2e_ms is not None and turn.e2e_ms is None:
            turn.e2e_ms = int(e2e_ms)
        for key, value in (ttfb_by_processor_ms or {}).items():
            turn.ttfb_by_processor_ms.setdefault(str(key), int(value))

    def on_client_playback_started(self, receive_to_playback_ms: Any, at: float | None = None) -> None:
        """Browser report: first audio of the reply received -> audible playback scheduled."""
        turn = self._turn
        if turn is None or turn.audio_out is None or turn.playback_report_rx is not None:
            return
        try:
            delta = float(receive_to_playback_ms)
        except (TypeError, ValueError):
            delta = None
        if delta is not None and not (0 <= delta < 60_000):
            delta = None
        turn.playback_report_rx = at if at is not None else self.now()
        turn.client_receive_to_playback_ms = delta
        if turn.bridge_done is not None:
            self.flush_pending()

    # ---- output -------------------------------------------------------------
    def flush_pending(self) -> dict[str, Any] | None:
        if self._flush_handle is not None:
            self._flush_handle.cancel()
            self._flush_handle = None
        turn, self._turn = self._turn, None
        if turn is None or turn.committed is None:
            return None
        record = build_turn_record(turn)
        self.written.append(record)
        if self._writer is not None:
            try:
                result = self._writer(record)
                if asyncio.iscoroutine(result):
                    try:
                        asyncio.get_running_loop().create_task(result)
                    except RuntimeError:
                        result.close()
            except Exception as exc:  # noqa: BLE001 - latency evidence must never break a turn
                logger.debug("voice_turn_trace_write_failed error=%s", exc)
        return record


def build_turn_record(turn: _TurnTimes) -> dict[str, Any]:
    """Cumulative marks + per-stage durations for one turn."""
    ref = turn.speech_end if turn.speech_end is not None else turn.committed
    brain_abs: dict[str, float] = {}
    if turn.brain_t0 is not None:
        brain_abs = {name: turn.brain_t0 + ms / 1000.0 for name, ms in turn.brain_marks.items()}
    # Last brain checkpoint before the first token closes the pre-LLM work.
    pre_llm_end: float | None = None
    if brain_abs:
        before_token = [
            at
            for name, at in brain_abs.items()
            if name not in _POST_LLM_MARKS and (turn.first_token is None or at <= turn.first_token)
        ]
        pre_llm_end = max(before_token) if before_token else None

    transport_est_ms: int | None = None
    client_first_audio: float | None = None
    playback_at: float | None = None
    if turn.playback_report_rx is not None and turn.audio_out is not None:
        round_trip = turn.playback_report_rx - turn.audio_out
        local = (turn.client_receive_to_playback_ms or 0.0) / 1000.0
        one_way = max(0.0, (round_trip - local) / 2.0)
        transport_est_ms = int(round(one_way * 1000))
        client_first_audio = turn.audio_out + one_way
        if turn.client_receive_to_playback_ms is not None:
            playback_at = client_first_audio + local

    tts_ttfb_ms = _ms(turn.tts_first_audio, turn.tts_requested)
    if tts_ttfb_ms is None:
        tts_ttfb_ms = next(
            (v for k, v in turn.ttfb_by_processor_ms.items() if "TTS" in k or "ElevenLabs" in k),
            None,
        )

    classification_ms: int | None = None
    spans = [
        turn.brain_marks[b] - turn.brain_marks[a]
        for a, b in _CLASSIFICATION_SPANS
        if a in turn.brain_marks and b in turn.brain_marks
    ]
    if spans:
        classification_ms = int(sum(spans))

    durations: dict[str, int | None] = {
        "eot_detection_ms": _ms(turn.committed, ref),
        "stt_finalization_ms": _ms(turn.stt_final, ref),
        "eager_eot_ms": _ms(turn.eager_eot, ref),
        "durable_context_ms": _ms(turn.durable_ready, turn.committed),
        "prompt_assembly_ms": _ms(turn.prompt_ready, turn.durable_ready or turn.committed),
        "moderation_guard_ms": _ms(turn.guard_done, turn.prompt_ready),
        "intent_tier_classification_ms": classification_ms,
        "brain_pre_llm_ms": _ms(pre_llm_end, turn.brain_t0),
        "model_ttft_ms": _ms(turn.first_token, pre_llm_end or turn.prompt_ready),
        "first_speakable_ms": _ms(turn.first_speakable, turn.first_token),
        "tts_ttfb_ms": tts_ttfb_ms,
        "server_audio_out_ms": _ms(turn.audio_out, turn.tts_first_audio),
        "transport_est_ms": transport_est_ms,
        "browser_playback_startup_ms": (
            int(round(turn.client_receive_to_playback_ms))
            if turn.client_receive_to_playback_ms is not None
            else None
        ),
        "speech_end_to_first_token_ms": _ms(turn.first_token, ref),
        "speech_end_to_server_audio_ms": _ms(turn.audio_out, ref),
        "speech_end_to_playback_ms": _ms(playback_at, ref),
        "observer_e2e_ms": turn.e2e_ms,
    }
    for name, ms in sorted(turn.brain_marks.items(), key=lambda kv: kv[1]):
        durations[f"brain.{name}"] = ms

    cumulative: dict[str, float | None] = {
        "eager_end_of_turn": turn.eager_eot,
        "stt_final": turn.stt_final,
        "user_stopped": turn.user_stopped,
        "turn_committed": turn.committed,
        "durable_context_ready": turn.durable_ready,
        "prompt_assembled": turn.prompt_ready,
        "moderation_guard_done": turn.guard_done,
        "brain_started": turn.brain_t0,
        "brain_pre_llm_done": pre_llm_end,
        "llm_first_token_ms": turn.first_token,
        "first_speakable_chunk": turn.first_speakable,
        "tts_requested_ms": turn.tts_requested,
        "tts_first_audio": turn.tts_first_audio,
        "server_first_audio_out": turn.audio_out,
        "client_first_audio_est": client_first_audio,
        "browser_playback_started": playback_at,
    }
    marks = {"client_ready": 0}
    for name, at in cumulative.items():
        ms = _ms(at, ref)
        if ms is not None:
            marks[name] = max(0, ms)

    tier, tier_source = resolve_turn_tier(turn.intelligence, turn.tier_override)
    routing = turn.intelligence.get("routing") or {}
    return {
        "turn_id": turn.turn_id or str(uuid.uuid4()),
        "tier": tier,
        "tier_source": tier_source,
        "marks": marks,
        "stage_durations_ms": {k: v for k, v in durations.items() if v is not None},
        "extra": {
            "speculative_outcome": turn.speculative_outcome,
            "speculation": dict(turn.speculation) or None,
            "effective_mode": turn.intelligence.get("effectiveMode"),
            "routing_tier": turn.intelligence.get("routingTier"),
            "tier_reason": routing.get("conversationTierReason") if isinstance(routing, dict) else None,
            "reasoning_depth": routing.get("reasoningDepth") if isinstance(routing, dict) else None,
            "reported_model_ttft_ms": routing.get("modelTtftMs") if isinstance(routing, dict) else None,
            "ttfb_by_processor_ms": dict(turn.ttfb_by_processor_ms),
            "transport_estimate": "half of (playback report rx - first audio out - browser startup)",
        },
    }


def audit_writer(settings: Any, *, org_id: str, user_id: str | None, conversation_id_getter: Callable[[], str | None]):
    """Writer that records a trace through ``record_voice_turn_critical_path`` off the loop."""

    async def _write(record: dict[str, Any]) -> None:
        from app.services.turn_latency_trace import record_voice_turn_critical_path

        await asyncio.to_thread(
            record_voice_turn_critical_path,
            settings,
            org_id=org_id,
            user_id=user_id,
            conversation_id=conversation_id_getter(),
            turn_id=record.get("turn_id"),
            marks=record.get("marks"),
            transport="pipecat_duplex",
            tier=record.get("tier"),
            stage_durations_ms=record.get("stage_durations_ms"),
            extra={"tier_source": record.get("tier_source"), **(record.get("extra") or {})},
        )

    return _write
