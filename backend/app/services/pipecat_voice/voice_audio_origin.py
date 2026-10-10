"""P3 — PCM origin and turn-state so probe audio is not treated as user barge-in."""
from __future__ import annotations

import re
import time
from contextvars import ContextVar
from dataclasses import dataclass, field
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

# The bot's own voice coming back through a phone or laptop speaker is
# transcribed like speech. Text the bot said this recently is compared with
# what the mic heard so the echo is not taken for the user cutting in.
ECHO_WINDOW_S = 15.0
_ECHO_MIN_OVERLAP = 0.6
# A two-word reply ("which pages", "the first") can reuse the bot's words on
# purpose, so it takes three words before a phrase can count as echo.
_ECHO_MIN_WORDS = 3


def _speech_words(text: str) -> list[str]:
    return re.sub(r"[^\w\s']", " ", (text or "").casefold()).split()


def is_echo_of(
    heard: str,
    spoken: list[str],
    *,
    min_words: int = _ECHO_MIN_WORDS,
    min_overlap: float = _ECHO_MIN_OVERLAP,
) -> bool:
    """True when ``heard`` is mostly a replay of the bot's recent ``spoken`` text."""
    words = _speech_words(heard)
    if len(words) < max(_ECHO_MIN_WORDS, min_words):
        return False
    bot_words = [w for text in spoken for w in _speech_words(text)]
    if not bot_words:
        return False
    bot_pairs = set(zip(bot_words, bot_words[1:]))
    pairs = list(zip(words, words[1:]))
    matched = sum(1 for pair in pairs if pair in bot_pairs)
    return matched / len(pairs) >= min_overlap

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
    # Zero-arg callable set by the interrupt reporter: True once the bot has
    # spoken a question that is still waiting for the user's answer. A short
    # "yes"/"sure" then is that answer, not a backchannel to ignore.
    answer_expected: Any = None
    # (monotonic time, text) of what the bot recently said, newest last.
    recent_bot_speech: list[tuple[float, str]] = field(default_factory=list)
    # Increases once per answered user turn. Outbound audio and the
    # interruption event carry it, so the browser can drop the cancelled
    # reply's late frames by identity instead of by a timer.
    reply_id: int = 0

    def begin_reply(self) -> int:
        self.reply_id += 1
        return self.reply_id

    def note_bot_speech(self, text: str) -> None:
        text = (text or "").strip()
        if not text:
            return
        now = time.monotonic()
        self.recent_bot_speech = [
            (at, said) for at, said in self.recent_bot_speech if now - at <= ECHO_WINDOW_S
        ][-20:]
        self.recent_bot_speech.append((now, text))

    def is_echo_of_bot(self, heard: str, *, strict: bool = False) -> bool:
        """``strict`` is for a finished turn, where the bot may be silent: a
        person can quote a few of the bot's words back, so it takes a longer,
        near-verbatim replay to call it echo."""
        now = time.monotonic()
        recent = [said for at, said in self.recent_bot_speech if now - at <= ECHO_WINDOW_S]
        if strict:
            return is_echo_of(heard, recent, min_words=6, min_overlap=0.85)
        return is_echo_of(heard, recent)

    def expects_answer(self) -> bool:
        probe = self.answer_expected
        if probe is None:
            return False
        try:
            return bool(probe())
        except Exception:  # noqa: BLE001
            return False

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
