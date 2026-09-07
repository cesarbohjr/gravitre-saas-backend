"""Tests for spoken-chat no-tools gate (latency cut without write regression)."""
from __future__ import annotations

from app.services.conversational_turn_gate import _CONNECTOR_HINT_RE, _DATA_TASK_RE, heuristic_turn_shape


def _spoken_chat_no_tools(message: str, *, spoken: bool = True, depth: str = "conversational") -> bool:
    msg = (message or "").strip()
    heuristic = heuristic_turn_shape(msg) if msg else None
    return bool(
        spoken
        and depth == "conversational"
        and not _DATA_TASK_RE.search(msg)
        and not _CONNECTOR_HINT_RE.search(msg)
        and (heuristic is None or heuristic.shape == "conversational")
    )


def test_two_plus_two_skips_tools():
    assert _spoken_chat_no_tools("What is two plus two?") is True


def test_hubspot_data_keeps_tools():
    assert _spoken_chat_no_tools("Show me our HubSpot pipeline deals") is False


def test_write_shaped_depth_full_keeps_tools_path():
    # Gate is depth-gated; full depth must not take the no-tools shortcut.
    assert _spoken_chat_no_tools("Send an email to Sarah", spoken=True, depth="full") is False


def test_greeting_skips_tools():
    assert _spoken_chat_no_tools("Hey, how's it going?") is True
