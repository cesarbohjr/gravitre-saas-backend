"""P3 — PCM origin and turn-state so probe audio is not treated as user barge-in."""
from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any

ORIGINS = frozenset({"user_mic", "probe_pcm", "tts_echo"})
TURN_STATES = frozenset({"listening", "committing_utterance", "speaking", "warming"})
WARMING = "warming"

USER_MIC = "user_mic"
PROBE_PCM = "probe_pcm"
TTS_ECHO = "tts_echo"

LISTENING = "listening"
COMMITTING = "committing_utterance"
SPEAKING = "speaking"

_current_origin: ContextVar[str] = ContextVar("gravitre_audio_origin", default=USER_MIC)
_current_turn_state: ContextVar[str] = ContextVar("gravitre_turn_state", default=LISTENING)


@dataclass
class VoicePipelineSession:
    """Process-shared origin/turn state for one Pipecat websocket.

    ContextVars do not survive Pipecat processor task hops. Every processor
    on this session must read/write this object, not the ContextVar.
    """

    origin: str = USER_MIC
    turn_state: str = LISTENING
    tts_warming: bool = False

    def set_origin(self, origin: str) -> None:
        self.origin = normalize_origin(origin)
        set_session_origin(self.origin)

    def set_turn_state(self, state: str) -> None:
        value = str(state or LISTENING).strip().lower()
        self.turn_state = value if value in TURN_STATES else LISTENING
        set_turn_state(self.turn_state)
        if self.turn_state == SPEAKING:
            self.tts_warming = False

    def mark_tts_warming(self) -> None:
        self.tts_warming = True


def set_session_origin(origin: str) -> None:
    _current_origin.set(normalize_origin(origin))


def get_session_origin(session: VoicePipelineSession | None = None) -> str:
    if session is not None:
        return normalize_origin(session.origin, default=USER_MIC)
    return normalize_origin(_current_origin.get(), default=USER_MIC)


def set_turn_state(state: str) -> None:
    value = str(state or LISTENING).strip().lower()
    _current_turn_state.set(value if value in TURN_STATES else LISTENING)


def get_turn_state(session: VoicePipelineSession | None = None) -> str:
    if session is not None:
        value = str(session.turn_state or LISTENING)
        return value if value in TURN_STATES else LISTENING
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


def should_drop_barge_in_broadcast(
    *,
    origin: str,
    turn_state: str,
    bot_speaking: bool = False,
    tts_warming: bool = False,
    settings: Any | None = None,
) -> bool:
    """True when this origin must not send InterruptionFrame (warmup or probe TTS)."""
    if not should_suppress_interrupt(origin=origin, turn_state=turn_state, settings=settings):
        return False
    state = str(turn_state or "").strip().lower()
    return bool(bot_speaking or tts_warming or state in {SPEAKING, WARMING})


def should_honor_user_mic_barge_in(*, origin: str, turn_state: str) -> bool:
    return normalize_origin(origin) == USER_MIC and str(turn_state or "") in {
        SPEAKING,
        COMMITTING,
        LISTENING,
    }
