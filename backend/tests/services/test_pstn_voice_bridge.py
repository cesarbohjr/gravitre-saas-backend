"""Mutation-proof tests for mid-call PSTN turn bridge wiring."""
from __future__ import annotations

import pytest

from app.services import pstn_voice_bridge


def test_mid_call_bridge_symbol_is_run_mid_call_turn() -> None:
    assert pstn_voice_bridge.MID_CALL_TURN_BRIDGE == "run_mid_call_turn"
    assert callable(pstn_voice_bridge.run_mid_call_turn)


def test_breaking_bridge_symbol_fails_guard() -> None:
    """Deliberate mutation: if bridge is renamed/unwired, this test must fail."""
    import inspect

    src = inspect.getsource(pstn_voice_bridge.run_mid_call_turn)
    assert "stream_voice_turn_events" in src
    assert 'tts_output_format="ulaw_8000"' in src


def test_parse_deepgram_results_message() -> None:
    raw = (
        '{"type":"Results","is_final":true,"channel":{"alternatives":[{"transcript":"hello"}]}}'
    )
    parsed = pstn_voice_bridge.parse_deepgram_ws_message(raw)
    assert parsed["transcript"] == "hello"
    assert parsed["is_final"] is True
