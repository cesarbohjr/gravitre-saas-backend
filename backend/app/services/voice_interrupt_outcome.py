"""3.0-C interrupt outcome labels for traces.

TRUE_INTERRUPT — user took the floor; stop playback.
BACKCHANNEL — do not interrupt Gravitre.
FALSE_INTERRUPT — empty/timeout overlap treated as interrupt (safe default) but
recorded separately so we can tune grace windows.
"""
from __future__ import annotations

from typing import Any

from app.services.pipecat_voice.backchannel_classifier import BackchannelClassification

TRUE_INTERRUPT = "TRUE_INTERRUPT"
BACKCHANNEL = "BACKCHANNEL"
FALSE_INTERRUPT = "FALSE_INTERRUPT"
AUDIT_ACTION = "voice.interrupt.outcome"


def interrupt_outcome(
    classification: BackchannelClassification,
    *,
    text: str = "",
    resolved_by_timeout: bool = False,
) -> str:
    if classification is BackchannelClassification.BACKCHANNEL:
        return BACKCHANNEL
    if resolved_by_timeout and not (text or "").strip():
        return FALSE_INTERRUPT
    return TRUE_INTERRUPT


def record_interrupt_outcome(
    settings: Any,
    *,
    org_id: str,
    user_id: str | None,
    conversation_id: str | None,
    classification: BackchannelClassification,
    text: str,
    decision_latency_ms: float,
    resolved_by_timeout: bool,
) -> str:
    outcome = interrupt_outcome(
        classification,
        text=text,
        resolved_by_timeout=resolved_by_timeout,
    )
    if not org_id or not user_id:
        return outcome
    try:
        from app.workflows.audit import write_audit_event
        from app.workflows.repository import get_supabase_client

        write_audit_event(
            get_supabase_client(settings),
            org_id,
            user_id,
            AUDIT_ACTION,
            "conversation",
            conversation_id or org_id,
            {
                "outcome": outcome,
                "classification": classification.value,
                "decision_latency_ms": round(float(decision_latency_ms), 1),
                "resolved_by_timeout": bool(resolved_by_timeout),
                "text_chars": len((text or "").strip()),
            },
        )
    except Exception:  # noqa: BLE001
        pass
    return outcome
