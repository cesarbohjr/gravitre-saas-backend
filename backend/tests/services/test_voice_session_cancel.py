"""Barge-in cancel registry for voice session turns."""

from app.services.voice_session_service import is_turn_cancelled, request_turn_cancel


def test_request_turn_cancel_marks_turn():
    tid = "turn-test-cancel-1"
    assert is_turn_cancelled(tid) is False
    request_turn_cancel(tid)
    assert is_turn_cancelled(tid) is True


def test_empty_turn_id_ignored():
    request_turn_cancel("")
    assert is_turn_cancelled("") is False
