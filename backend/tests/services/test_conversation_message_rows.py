"""Capstone: conversation_messages batch insert must set id on every row."""
from __future__ import annotations

from app.services.conversation_message_rows import build_conversation_turn_message_rows


def test_build_conversation_turn_message_rows_sets_id_on_both():
    rows, assistant_id = build_conversation_turn_message_rows(
        conversation_id="conv-1",
        user_text="yes",
        assistant_text="Done — Send email",
        tool_results=[],
        created_at="2026-07-27T00:00:00+00:00",
    )
    assert len(rows) == 2
    assert rows[0]["role"] == "user"
    assert rows[1]["role"] == "assistant"
    assert rows[0]["id"], "user row must have explicit id (PostgREST nulls omitted batch cols)"
    assert rows[1]["id"] == assistant_id
    assert rows[0]["id"] != rows[1]["id"]
