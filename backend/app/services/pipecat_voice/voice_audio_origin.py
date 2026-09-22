"""P3 — PCM origin and turn-state so probe audio is not treated as user barge-in."""
from __future__ import annotations

from contextvars import ContextVar
from typing import Any

ORIGINS = frozenset({"user_mic", "probe_pcm", "tts_echo"})
TURN_STATES = frozenset({"listening", "committing_utterance", "speaking"})

USER_MIC = "user_mic"
PROBE_PCM = "probe_pcm"
TTS_ECHO = "tts_echo"

LISTENING = "listening"
COMMITTING = "committing_utterance"
SPEAKING = "speaking"

_current_origin: ContextVar[str] = ContextVar("gravitre_audio_origin", default=USER_MIC)
_current_turn_state: ContextVar[str] = ContextVar("gravitre_turn_state", default=LISTENING)


def set_session_origin(origin: str) -> None:
    _current_origin.set(normalize_origin(origin))


def get_session_origin() -> str:
    return normalize_origin(_current_origin.get(), default=USER_MIC)


def set_turn_state(state: str) -> None:
    value = str(state or LISTENING).strip().lower()
    _current_turn_state.set(value if value in TURN_STATES else LISTENING)


def get_turn_state() -> str:
    value = str(_current_turn_state.get() or LISTENING)
    return value if value in TURN_STATES else LISTENING


def p3_origin_policy_enabled(settings: Any | None) -> bool:
    if settings is None:
        return True
    return bool(getattr(settings, "convergence_p3_pcm_origin_v1", True))


def normalize_origin(raw: Any, *, default: str = USER_MIC) -> str:
    value = str(raw or "").strip().lower()
    if value in ORIGINS:
        return value
    if value in {"probe", "sapi", "harness", "synthetic"}:
        return PROBE_PCM
    if value in {"echo", "tts", "loopback"}:
        return TTS_ECHO
    return default if default in ORIGINS else USER_MIC


def should_suppress_interrupt(
    *,
    origin: str,
    turn_state: str,
    settings: Any | None = None,
) -> bool:
    """True → do not treat this as user barge-in.

    Real `user_mic` during `speaking` stays live. Probe/TTS echo never barge-in.
    Never globally holds until STT final.
    """
    if not p3_origin_policy_enabled(settings):
        return False
    origin_n = normalize_origin(origin)
    if origin_n != USER_MIC:
        return True
    return False


def should_honor_user_mic_barge_in(*, origin: str, turn_state: str) -> bool:
    return normalize_origin(origin) == USER_MIC and str(turn_state or "") in {
        SPEAKING,
        COMMITTING,
        LISTENING,
    }
