"""Phase F1 cooperative chat-turn cancel (in-process fallback)."""
from __future__ import annotations

from unittest.mock import MagicMock

from app.services.chat_turn_cancel_service import (
    clear_stop,
    is_stop_requested,
    request_stop,
    reset_local_stops_for_tests,
    stop_key,
    stream_should_stop,
)


def setup_function() -> None:
    reset_local_stops_for_tests()


def test_request_stop_visible_without_redis(monkeypatch) -> None:
    monkeypatch.setattr("app.services.chat_turn_cancel_service.get_redis_client", lambda _s=None: None)
    assert request_stop("org-1", "conv-1") is True
    assert is_stop_requested("org-1", "conv-1") is True
    assert is_stop_requested("org-1", "conv-other") is False
    assert is_stop_requested("org-2", "conv-1") is False
    clear_stop("org-1", "conv-1")
    assert is_stop_requested("org-1", "conv-1") is False


def test_stop_key_is_org_and_conversation_scoped() -> None:
    assert stop_key("org-a", "c1") != stop_key("org-b", "c1")
    assert stop_key("org-a", "c1") != stop_key("org-a", "c2")


def test_blank_ids_are_ignored(monkeypatch) -> None:
    monkeypatch.setattr("app.services.chat_turn_cancel_service.get_redis_client", lambda _s=None: None)
    assert request_stop("", "conv-1") is False
    assert request_stop("org-1", "") is False
    assert is_stop_requested("org-1", None) is False


def test_redis_setex_used_when_available(monkeypatch) -> None:
    redis = MagicMock()
    redis.setex.return_value = True
    redis.get.return_value = "1"
    monkeypatch.setattr("app.services.chat_turn_cancel_service.get_redis_client", lambda _s=None: redis)
    assert request_stop("org-1", "conv-9") is True
    redis.setex.assert_called_once()
    assert redis.setex.call_args.args[0] == stop_key("org-1", "conv-9")
    assert is_stop_requested("org-1", "conv-9") is True
    redis.get.assert_called()


async def test_stream_should_stop_on_disconnect() -> None:
    class _Req:
        async def is_disconnected(self) -> bool:
            return True

    assert await stream_should_stop(_Req(), "org-1", None) is True


async def test_stream_should_stop_on_flag(monkeypatch) -> None:
    monkeypatch.setattr("app.services.chat_turn_cancel_service.get_redis_client", lambda _s=None: None)
    request_stop("org-1", "conv-1")

    class _Req:
        async def is_disconnected(self) -> bool:
            return False

    assert await stream_should_stop(_Req(), "org-1", "conv-1") is True
