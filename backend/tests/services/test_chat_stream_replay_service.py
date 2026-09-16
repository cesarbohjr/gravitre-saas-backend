"""Phase F4 completed-turn replay (Redis / in-process)."""
from __future__ import annotations

from app.services.chat_stream_replay_service import (
    load_completed_turn,
    replay_key,
    reset_local_replays_for_tests,
    store_completed_turn,
)


def setup_function() -> None:
    reset_local_replays_for_tests()


def test_store_and_load_replay(monkeypatch) -> None:
    monkeypatch.setattr("app.services.chat_stream_replay_service.get_redis_client", lambda _s=None: None)
    event_id = store_completed_turn(
        "org-1",
        "conv-1",
        user_text="list contacts",
        assistant_text="Here are three contacts.",
        assistant_message_id="msg-9",
    )
    assert event_id == "msg-9"
    payload = load_completed_turn("org-1", "conv-1")
    assert payload is not None
    assert payload["already_have"] is False
    assert payload["assistant_text"] == "Here are three contacts."
    assert replay_key("org-1", "conv-1") != replay_key("org-2", "conv-1")


def test_last_event_id_skips_duplicate(monkeypatch) -> None:
    monkeypatch.setattr("app.services.chat_stream_replay_service.get_redis_client", lambda _s=None: None)
    store_completed_turn(
        "org-1",
        "conv-1",
        user_text="hi",
        assistant_text="hello",
        assistant_message_id="evt-1",
    )
    skipped = load_completed_turn("org-1", "conv-1", last_event_id="evt-1")
    assert skipped is not None
    assert skipped["already_have"] is True


def test_blank_conversation_is_ignored(monkeypatch) -> None:
    monkeypatch.setattr("app.services.chat_stream_replay_service.get_redis_client", lambda _s=None: None)
    assert store_completed_turn("org-1", None, user_text="a", assistant_text="b") is None
    assert load_completed_turn("org-1", "") is None
