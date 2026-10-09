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


class _Rows:
    def __init__(self, data):
        self.data = data


class _Query:
    def __init__(self, data):
        self._data = data

    def __getattr__(self, _name):
        return lambda *_a, **_k: self

    def execute(self):
        return _Rows(self._data)


class _Client:
    def __init__(self, messages):
        self._messages = messages

    def table(self, name):
        return _Query([{"id": "conv-1"}] if name == "conversations" else self._messages)


def _db_replay(monkeypatch, messages):
    import app.workflows.repository as repository
    from app.services.chat_stream_replay_service import load_completed_turn_from_db

    monkeypatch.setattr(repository, "get_supabase_client", lambda *_a, **_k: _Client(messages))
    return load_completed_turn_from_db(
        object(), org_id="org-1", user_id="user-1", conversation_id="conv-1"
    )


def test_db_replay_carries_the_prompt_it_answered(monkeypatch) -> None:
    payload = _db_replay(
        monkeypatch,
        [
            {"id": "a2", "role": "assistant", "content": "Sent."},
            {"id": "u2", "role": "user", "content": "email Sarah the deck"},
        ],
    )
    assert payload is not None
    assert payload["user_text"] == "email Sarah the deck"
    assert payload["assistant_text"] == "Sent."


def test_db_replay_skips_a_prompt_still_waiting_for_its_reply(monkeypatch) -> None:
    payload = _db_replay(
        monkeypatch,
        [
            {"id": "u3", "role": "user", "content": "email Sarah the deck"},
            {"id": "a2", "role": "assistant", "content": "You have 3 deals."},
        ],
    )
    assert payload is None
