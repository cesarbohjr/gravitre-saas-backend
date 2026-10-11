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


def test_a_stored_user_row_is_not_built_again():
    rows, assistant_id = build_conversation_turn_message_rows(
        conversation_id="conv-1",
        user_text="pull the pipeline report",
        assistant_text="Forty two open deals.",
        tool_results=[],
        created_at="2026-10-11T10:00:00+00:00",
        user_row_stored=True,
    )
    assert [(r["role"], r["content"]) for r in rows] == [("assistant", "Forty two open deals.")]
    assert rows[0]["id"] == assistant_id


def test_an_earlier_request_is_stored_first_and_sorts_first():
    """Voice aside: the running task's request was said before the aside's question."""
    rows, _ = build_conversation_turn_message_rows(
        conversation_id="conv-1",
        user_text="why is it taking so long",
        assistant_text="It is pulling every open deal.",
        tool_results=[],
        created_at="2026-10-11T10:00:00+00:00",
        earlier_user_text="pull the pipeline report",
    )
    assert [(r["role"], r["content"]) for r in rows] == [
        ("user", "pull the pipeline report"),
        ("user", "why is it taking so long"),
        ("assistant", "It is pulling every open deal."),
    ]
    assert all(r["id"] and r["conversation_id"] == "conv-1" for r in rows)
    assert len({r["id"] for r in rows}) == 3
    assert rows[0]["created_at"] < rows[1]["created_at"] == rows[2]["created_at"]
