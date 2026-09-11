"""Phase 6 (conversational-realism): real, per-stage voice turn latency samples.

Writes actual measured stage timings into ``audit_events`` using the exact
same helper (``write_audit_event``) and dashboard (``golden_signals_service``)
already used for every other live signal — per the prompt's own instruction,
this is NOT a separate reporting mechanism.

Two actions are emitted per voice turn (never merged into one fragile,
cross-processor-correlated record):

  - ``voice.turn_latency.llm_stage`` — from inside the Cognitive LLM bridge:
    llm_first_token_ms, llm_first_speakable_chunk_ms, tts_requested_ms
    (all measured from the same turn-start reference actually used in code).
  - ``voice.turn_latency.e2e`` — from the pipeline-level
    ``GravitreVoiceLatencyObserver``: end_to_end_ms (real audio-in-silence to
    real audio-out-start), user_turn_finalization_ms (STT/turn-strategy
    overhead), and TTFB per processor (covers tts_first_byte_ms; also
    llm_first_token_ms independently, when the LLM service's own TTFB
    metrics are enabled — see cognitive_llm.py).

Every field name below maps directly onto a stage named in the
conversational-realism Phase 6 prompt. Fields this module cannot yet measure
honestly (interrupt_detected_ms / audio_cancelled_ms sub-millisecond
framework-internal cancellation) are intentionally NOT emitted here — see
``backchannel_turn_strategy.py``'s own ``decision_latency_ms`` log for the
real, live interruption-classification-latency signal instead of a fabricated
number in this module.
"""
from __future__ import annotations

from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

LLM_STAGE_ACTION = "voice.turn_latency.llm_stage"
E2E_ACTION = "voice.turn_latency.e2e"
# Phase 5 (conversational polish): durable evidence that a barge-in actually
# truncated drafted-but-unheard text, and by which alignment strategy. A log
# line alone cannot distinguish a real truncation from a silent fallback.
BARGE_IN_RECONCILE_ACTION = "voice.barge_in.reconciled"


def _write(
    settings: Any,
    *,
    org_id: str,
    user_id: str | None,
    conversation_id: str | None,
    action: str,
    payload: dict[str, Any],
) -> None:
    """Best-effort audit_events write. Never raises — must not affect voice turns.

    ``audit_events.actor_id`` FKs ``auth.users(id)`` (NOT NULL). ``org_id`` is
    an org UUID, not a user UUID, so it can never stand in for actor_id — an
    earlier version of this function tried that fallback and every single
    write failed silently on foreign-key violation (23503), leaving Phase 6's
    "real per-stage latency" dashboard permanently empty despite the voice
    turns themselves working. The real authenticated ``user_id`` of the
    voice session is the only valid actor for this write; if it is missing
    or not a real user (e.g. a synthetic probe/service session), skip the
    write rather than corrupt or silently drop it.
    """
    if not org_id or not user_id:
        logger.debug(
            "voice_turn_latency_sample_skipped action=%s reason=missing_org_or_user_id", action
        )
        return
    try:
        from app.workflows.audit import write_audit_event
        from app.workflows.repository import get_supabase_client

        client = get_supabase_client(settings)
        write_audit_event(
            client,
            org_id,
            user_id,
            action,
            "conversation",
            conversation_id or org_id,
            payload,
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("voice_turn_latency_sample_write_failed action=%s error=%s", action, exc)


def record_voice_llm_stage_sample(
    settings: Any,
    *,
    org_id: str,
    user_id: str | None,
    conversation_id: str | None,
    llm_first_token_ms: int | None,
    llm_first_speakable_chunk_ms: int | None,
    tts_requested_ms: int | None,
    speculative_outcome: str | None = None,
    speculative_v2: bool | None = None,
    tts_chunk_v2: bool | None = None,
) -> None:
    """Real, measured LLM-bridge stage timings for one voice turn."""
    payload: dict[str, Any] = {
        "llm_first_token_ms": llm_first_token_ms,
        "llm_first_speakable_chunk_ms": llm_first_speakable_chunk_ms,
        "tts_requested_ms": tts_requested_ms,
    }
    if speculative_outcome:
        payload["speculative_outcome"] = speculative_outcome
    if speculative_v2 is not None:
        payload["speculative_v2"] = speculative_v2
    if tts_chunk_v2 is not None:
        payload["tts_chunk_v2"] = tts_chunk_v2
    _write(
        settings,
        org_id=org_id,
        user_id=user_id,
        conversation_id=conversation_id,
        action=LLM_STAGE_ACTION,
        payload=payload,
    )


def record_voice_e2e_latency_sample(
    settings: Any,
    *,
    org_id: str,
    user_id: str | None,
    conversation_id: str | None,
    end_to_end_ms: int | None,
    user_turn_finalization_ms: int | None,
    ttfb_by_processor_ms: dict[str, int],
) -> None:
    """Real, measured end-to-end + per-service TTFB timings for one voice turn."""
    _write(
        settings,
        org_id=org_id,
        user_id=user_id,
        conversation_id=conversation_id,
        action=E2E_ACTION,
        payload={
            "end_to_end_ms": end_to_end_ms,
            "user_turn_finalization_ms": user_turn_finalization_ms,
            "ttfb_by_processor_ms": ttfb_by_processor_ms,
        },
    )


def record_voice_slo_metric(
    settings: Any,
    *,
    metric: str,
    org_id: str,
    user_id: str | None,
    conversation_id: str | None,
    ms: int | None,
    source: str | None = None,
    operator_task: bool | None = None,
    composed: bool | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    """One Metric A or Metric B sample. Never merged into a blended SLO row."""
    from app.services.voice_slo import AUDIT_METRIC_A, AUDIT_METRIC_B, METRIC_A_ID, METRIC_B_ID

    if metric == METRIC_A_ID:
        action = AUDIT_METRIC_A
    elif metric == METRIC_B_ID:
        action = AUDIT_METRIC_B
    else:
        return
    if ms is None:
        return
    payload: dict[str, Any] = {
        "metric": metric,
        "ms": int(ms),
    }
    if source:
        payload["source"] = source
    if operator_task is not None:
        payload["operator_task"] = bool(operator_task)
    if composed is not None:
        payload["composed"] = bool(composed)
    if extra:
        payload.update(extra)
    _write(
        settings,
        org_id=org_id,
        user_id=user_id,
        conversation_id=conversation_id,
        action=action,
        payload=payload,
    )


def record_voice_barge_in_reconciliation(
    settings: Any,
    *,
    org_id: str,
    user_id: str | None,
    conversation_id: str | None,
    reconcile_meta: dict[str, Any],
    playback_offset_ms: float | None,
) -> None:
    """One barge-in reconciliation outcome.

    Carries ``match_strategy`` so a live trace proves whether unheard text was
    genuinely dropped (``dropped_chars > 0`` with an ``*_prefix`` strategy) or
    whether alignment fell back to the untruncated draft. No transcript text is
    written — only counts and the strategy label.
    """
    _write(
        settings,
        org_id=org_id,
        user_id=user_id,
        conversation_id=conversation_id,
        action=BARGE_IN_RECONCILE_ACTION,
        payload={**reconcile_meta, "playback_offset_ms": playback_offset_ms},
    )
