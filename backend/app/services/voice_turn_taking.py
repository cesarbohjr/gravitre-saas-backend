"""Provisional, continuously-revised turn attribution (not fixed silence thresholds).

Modelled after production voice-agent practice: newest speech stays provisional;
a turn finalizes only once the speaker has sustained the floor long enough for
reliable attribution. Brief agent acknowledgments during user speech do not
steal the floor.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TurnSensitivity(str, Enum):
    EAGER = "eager"
    NORMAL = "normal"
    PATIENT = "patient"


# Sustained-floor windows (ms) before provisional → final. Not "silence ms".
SENSITIVITY_FLOOR_MS: dict[TurnSensitivity, int] = {
    TurnSensitivity.EAGER: 350,
    TurnSensitivity.NORMAL: 650,
    TurnSensitivity.PATIENT: 1100,
}

# Overlap: agent ack shorter than this while user still speaking → ignore for floor.
AGENT_ACK_MAX_MS = 900


class FloorHolder(str, Enum):
    NONE = "none"
    USER = "user"
    AGENT = "agent"
    OVERLAP = "overlap"


@dataclass
class TranscriptSegment:
    text: str
    speaker: str  # "user" | "agent"
    is_final: bool
    started_at_ms: float
    updated_at_ms: float
    provisional: bool = True


@dataclass
class TurnTakingState:
    sensitivity: TurnSensitivity = TurnSensitivity.NORMAL
    floor: FloorHolder = FloorHolder.NONE
    provisional_user_text: str = ""
    finalized_user_text: str = ""
    user_speech_started_at_ms: float | None = None
    last_user_update_ms: float | None = None
    last_vad_speech_ms: float | None = None
    agent_speaking: bool = False
    agent_speech_started_at_ms: float | None = None
    pending_finalize: bool = False
    history: list[TranscriptSegment] = field(default_factory=list)

    def floor_ms(self) -> int:
        return SENSITIVITY_FLOOR_MS[self.sensitivity]


def parse_sensitivity(raw: str | None) -> TurnSensitivity:
    key = (raw or "normal").strip().lower()
    try:
        return TurnSensitivity(key)
    except ValueError:
        return TurnSensitivity.NORMAL


def on_user_partial(
    state: TurnTakingState,
    *,
    text: str,
    now_ms: float,
    vad_speech: bool = True,
) -> TurnTakingState:
    """Newest user speech revises provisional attribution."""
    clean = (text or "").strip()
    if not clean and not vad_speech:
        return state
    if state.user_speech_started_at_ms is None:
        state.user_speech_started_at_ms = now_ms
    state.last_user_update_ms = now_ms
    if vad_speech:
        state.last_vad_speech_ms = now_ms
    state.provisional_user_text = clean or state.provisional_user_text
    # User keeps / regains floor unless agent has sustained non-ack speech.
    if state.agent_speaking and _agent_is_brief_ack(state, now_ms):
        state.floor = FloorHolder.OVERLAP
    else:
        state.floor = FloorHolder.USER
        state.pending_finalize = False
    return state


def on_user_utterance_end(
    state: TurnTakingState,
    *,
    text: str,
    now_ms: float,
) -> TurnTakingState:
    """Deepgram utterance_end / VAD silence — candidate for finalize, not automatic."""
    if text.strip():
        state.provisional_user_text = text.strip()
    state.last_user_update_ms = now_ms
    state.pending_finalize = True
    return state


def on_agent_speech_start(state: TurnTakingState, *, now_ms: float) -> TurnTakingState:
    state.agent_speaking = True
    state.agent_speech_started_at_ms = now_ms
    if state.floor == FloorHolder.USER and state.provisional_user_text:
        # Brief ack while user holds floor → overlap, do not steal.
        state.floor = FloorHolder.OVERLAP
    else:
        state.floor = FloorHolder.AGENT
    return state


def on_agent_speech_end(state: TurnTakingState, *, now_ms: float) -> TurnTakingState:
    duration = 0.0
    if state.agent_speech_started_at_ms is not None:
        duration = now_ms - state.agent_speech_started_at_ms
    state.agent_speaking = False
    state.agent_speech_started_at_ms = None
    if state.provisional_user_text and duration <= AGENT_ACK_MAX_MS:
        state.floor = FloorHolder.USER
    elif state.provisional_user_text:
        state.floor = FloorHolder.USER
    else:
        state.floor = FloorHolder.NONE
    return state


def _agent_is_brief_ack(state: TurnTakingState, now_ms: float) -> bool:
    if state.agent_speech_started_at_ms is None:
        return False
    return (now_ms - state.agent_speech_started_at_ms) <= AGENT_ACK_MAX_MS


def maybe_finalize_user_turn(state: TurnTakingState, *, now_ms: float) -> str | None:
    """Finalize only when user sustained the floor long enough after last revision.

    Returns finalized transcript or None if still provisional.
    """
    if not state.provisional_user_text:
        return None
    if state.floor not in {FloorHolder.USER, FloorHolder.NONE} and not state.pending_finalize:
        return None
    # Require sustained quiet after last user update (attribution window).
    last = state.last_user_update_ms
    if last is None:
        return None
    elapsed = now_ms - last
    if elapsed < state.floor_ms():
        return None
    # If agent is mid long utterance, wait (user barge-in revises via on_user_partial).
    if state.agent_speaking and not _agent_is_brief_ack(state, now_ms):
        return None
    finalized = state.provisional_user_text.strip()
    if not finalized:
        return None
    state.finalized_user_text = finalized
    state.history.append(
        TranscriptSegment(
            text=finalized,
            speaker="user",
            is_final=True,
            started_at_ms=state.user_speech_started_at_ms or last,
            updated_at_ms=now_ms,
            provisional=False,
        )
    )
    state.provisional_user_text = ""
    state.user_speech_started_at_ms = None
    state.pending_finalize = False
    state.floor = FloorHolder.NONE
    return finalized


def snapshot(state: TurnTakingState) -> dict[str, Any]:
    return {
        "sensitivity": state.sensitivity.value,
        "floor_ms": state.floor_ms(),
        "floor": state.floor.value,
        "provisional_user_text": state.provisional_user_text,
        "pending_finalize": state.pending_finalize,
        "agent_speaking": state.agent_speaking,
        "finalized_turns": len([h for h in state.history if h.is_final]),
    }
