"""Provisional turn-taking — not fixed silence thresholds."""
from __future__ import annotations

from app.services.voice_turn_taking import (
    TurnSensitivity,
    TurnTakingState,
    maybe_finalize_user_turn,
    on_agent_speech_end,
    on_agent_speech_start,
    on_user_partial,
    on_user_utterance_end,
)


def test_partial_stays_provisional_until_floor_window():
    state = TurnTakingState(sensitivity=TurnSensitivity.NORMAL)
    state = on_user_partial(state, text="hey there", now_ms=0)
    assert maybe_finalize_user_turn(state, now_ms=200) is None
    assert state.provisional_user_text == "hey there"
    finalized = maybe_finalize_user_turn(state, now_ms=700)
    assert finalized == "hey there"
    assert state.provisional_user_text == ""


def test_newer_speech_revises_provisional():
    state = TurnTakingState(sensitivity=TurnSensitivity.EAGER)
    state = on_user_partial(state, text="create a", now_ms=0)
    state = on_user_partial(state, text="create a hubspot list", now_ms=100)
    assert state.provisional_user_text == "create a hubspot list"
    assert maybe_finalize_user_turn(state, now_ms=200) is None


def test_brief_agent_ack_does_not_steal_floor():
    state = TurnTakingState(sensitivity=TurnSensitivity.NORMAL)
    state = on_user_partial(state, text="and also send", now_ms=0)
    state = on_agent_speech_start(state, now_ms=50)
    # Brief ack while user still talking
    assert state.floor.value == "overlap"
    state = on_agent_speech_end(state, now_ms=200)
    assert state.floor.value == "user"
    assert maybe_finalize_user_turn(state, now_ms=300) is None


def test_utterance_end_pending_then_finalize():
    state = TurnTakingState(sensitivity=TurnSensitivity.PATIENT)
    state = on_user_partial(state, text="what's your name", now_ms=0)
    state = on_user_utterance_end(state, text="what's your name", now_ms=100)
    assert state.pending_finalize is True
    assert maybe_finalize_user_turn(state, now_ms=500) is None  # patient = 1100ms
    assert maybe_finalize_user_turn(state, now_ms=1300) == "what's your name"
