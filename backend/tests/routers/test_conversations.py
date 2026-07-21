"""Tests for /api/conversations."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user, get_org_context
from app.config import Settings, get_settings
from app.main import app

client = TestClient(app)


def _settings() -> Settings:
    return Settings(
        app_env="dev",
        supabase_url="https://test.supabase.co",
        supabase_anon_key="anon-test",
        supabase_service_role_key="service-role-test",
        supabase_jwt_secret="jwt-secret-test",
    )


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


def _authenticate(org_id: str = "org-1") -> None:
    app.dependency_overrides[get_current_user] = lambda: {"user_id": "user-1", "email": "u@example.com"}
    app.dependency_overrides[get_org_context] = lambda: org_id
    app.dependency_overrides[get_settings] = lambda: _settings()


def _table_chain(data: list[dict] | None = None, *, error: Exception | None = None):
    chain = MagicMock()
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.is_.return_value = chain
    chain.ilike.return_value = chain
    chain.gte.return_value = chain
    chain.order.return_value = chain
    chain.limit.return_value = chain
    chain.range.return_value = chain
    chain.in_.return_value = chain
    chain.insert.return_value = chain
    chain.update.return_value = chain
    chain.delete.return_value = chain
    response = MagicMock()
    response.data = data or []
    response.error = error
    chain.execute.return_value = response
    return chain


def test_list_conversations_requires_org():
    _authenticate(org_id=None)
    app.dependency_overrides[get_org_context] = lambda: None
    response = client.get("/api/conversations")
    assert response.status_code == 403


def test_list_conversations_empty_when_table_missing(monkeypatch):
    _authenticate()
    table = _table_chain(error=Exception('relation "conversations" does not exist'))
    supabase = MagicMock()
    supabase.table.return_value = table
    monkeypatch.setattr(
        "app.routers.conversations.create_client",
        lambda *_args, **_kwargs: supabase,
    )
    response = client.get("/api/conversations")
    assert response.status_code == 200
    assert response.json() == {"conversations": []}


def test_create_conversation(monkeypatch):
    _authenticate()
    created = {
        "id": "conv-1",
        "title": "Support thread",
        "preview": None,
        "message_count": 0,
        "created_at": "2026-06-04T12:00:00+00:00",
        "updated_at": "2026-06-04T12:00:00+00:00",
    }
    dedup_chain = _table_chain([])
    insert_chain = _table_chain([created])
    supabase = MagicMock()
    supabase.table.side_effect = [dedup_chain, insert_chain]
    monkeypatch.setattr(
        "app.routers.conversations.create_client",
        lambda *_args, **_kwargs: supabase,
    )
    response = client.post("/api/conversations", json={"title": "Support thread"})
    assert response.status_code == 201
    body = response.json()
    assert body["id"] == "conv-1"
    assert body["title"] == "Support thread"


def test_create_conversation_supabase_v2_response_without_error_attr(monkeypatch):
    """supabase-py v2 APIResponse has no `.error` — must not 500."""
    _authenticate()
    created = {
        "id": "conv-2",
        "title": "hello",
        "preview": None,
        "message_count": 0,
        "created_at": "2026-06-04T12:00:00+00:00",
        "updated_at": "2026-06-04T12:00:00+00:00",
    }

    class V2Response:
        def __init__(self, data: list[dict]) -> None:
            self.data = data

    dedup_chain = MagicMock()
    dedup_chain.select.return_value = dedup_chain
    dedup_chain.eq.return_value = dedup_chain
    dedup_chain.is_.return_value = dedup_chain
    dedup_chain.ilike.return_value = dedup_chain
    dedup_chain.gte.return_value = dedup_chain
    dedup_chain.order.return_value = dedup_chain
    dedup_chain.limit.return_value = dedup_chain
    dedup_chain.execute.return_value = V2Response([])

    insert_chain = MagicMock()
    insert_chain.insert.return_value = insert_chain
    insert_chain.execute.return_value = V2Response([created])
    supabase = MagicMock()
    supabase.table.side_effect = [dedup_chain, insert_chain]
    monkeypatch.setattr(
        "app.routers.conversations.create_client",
        lambda *_args, **_kwargs: supabase,
    )

    response = client.post("/api/conversations", json={"title": "hello"})
    assert response.status_code == 201
    assert response.json()["id"] == "conv-2"


def test_list_messages_empty(monkeypatch):
    _authenticate()
    conversations = _table_chain(
        [
            {
                "id": "conv-1",
                "org_id": "org-1",
                "user_id": "user-1",
                "title": "Thread",
                "preview": None,
                "message_count": 0,
                "created_at": "2026-06-04T12:00:00+00:00",
                "updated_at": "2026-06-04T12:00:00+00:00",
            }
        ]
    )
    messages = _table_chain([])
    supabase = MagicMock()

    def _table(name: str):
        if name == "conversations":
            return conversations
        return messages

    supabase.table.side_effect = _table
    monkeypatch.setattr(
        "app.routers.conversations.create_client",
        lambda *_args, **_kwargs: supabase,
    )
    response = client.get("/api/conversations/conv-1/messages")
    assert response.status_code == 200
    assert response.json() == {"messages": []}


def test_append_conversation_messages(monkeypatch):
    _authenticate()
    owned = {
        "id": "conv-1",
        "org_id": "org-1",
        "user_id": "user-1",
        "title": "HubSpot contacts",
        "preview": None,
        "message_count": 0,
        "created_at": "2026-06-04T12:00:00+00:00",
        "updated_at": "2026-06-04T12:00:00+00:00",
    }
    conversations = _table_chain([owned])
    messages = _table_chain(
        [
            {
                "id": "msg-1",
                "conversation_id": "conv-1",
                "role": "user",
                "content": "do you see any contacts in HubSpot?",
                "tool_calls": None,
                "created_at": "2026-06-04T12:01:00+00:00",
            }
        ]
    )
    supabase = MagicMock()

    def _table(name: str):
        if name == "conversations":
            return conversations
        return messages

    supabase.table.side_effect = _table
    monkeypatch.setattr(
        "app.routers.conversations.create_client",
        lambda *_args, **_kwargs: supabase,
    )
    response = client.post(
        "/api/conversations/conv-1/messages",
        json={
            "messages": [
                {
                    "role": "user",
                    "content": "do you see any contacts in HubSpot?",
                }
            ]
        },
    )
    assert response.status_code == 201
    assert response.json()["messages"][0]["content"] == "do you see any contacts in HubSpot?"
    conversations.update.assert_called_once()


def test_create_conversation_deduplicates_same_day_title(monkeypatch):
    _authenticate()
    existing = {
        "id": "conv-existing",
        "title": "What agents are active?",
        "preview": "prior answer",
        "message_count": 2,
        "created_at": "2026-06-13T08:00:00+00:00",
        "updated_at": "2026-06-13T08:05:00+00:00",
    }
    dedup_chain = _table_chain([existing])
    supabase = MagicMock()
    supabase.table.return_value = dedup_chain
    monkeypatch.setattr(
        "app.routers.conversations.create_client",
        lambda *_args, **_kwargs: supabase,
    )
    response = client.post("/api/conversations", json={"title": "What agents are active?"})
    assert response.status_code == 201
    assert response.json()["id"] == "conv-existing"
    dedup_chain.insert.assert_not_called()


def test_archive_conversation(monkeypatch):
    _authenticate()
    owned = _table_chain(
        [
            {
                "id": "conv-1",
                "org_id": "org-1",
                "user_id": "user-1",
                "title": "Thread",
                "preview": None,
                "message_count": 0,
                "created_at": "2026-06-04T12:00:00+00:00",
                "updated_at": "2026-06-04T12:00:00+00:00",
            }
        ]
    )
    archived = _table_chain(
        [
            {
                "id": "conv-1",
                "title": "Thread",
                "preview": None,
                "message_count": 0,
                "created_at": "2026-06-04T12:00:00+00:00",
                "updated_at": "2026-06-13T08:00:00+00:00",
            }
        ]
    )
    supabase = MagicMock()
    supabase.table.side_effect = [owned, archived]
    monkeypatch.setattr(
        "app.routers.conversations.create_client",
        lambda *_args, **_kwargs: supabase,
    )
    response = client.post("/api/conversations/conv-1/archive")
    assert response.status_code == 200
    assert response.json()["id"] == "conv-1"


def test_pin_conversation(monkeypatch):
    _authenticate()
    owned = _table_chain(
        [
            {
                "id": "conv-1",
                "org_id": "org-1",
                "user_id": "user-1",
                "title": "Thread",
                "preview": None,
                "message_count": 0,
                "created_at": "2026-06-04T12:00:00+00:00",
                "updated_at": "2026-06-04T12:00:00+00:00",
            }
        ]
    )
    pinned = _table_chain(
        [
            {
                "id": "conv-1",
                "title": "Thread",
                "preview": None,
                "message_count": 0,
                "created_at": "2026-06-04T12:00:00+00:00",
                "updated_at": "2026-07-20T12:00:00+00:00",
                "pinned_at": "2026-07-20T12:00:00+00:00",
            }
        ]
    )
    supabase = MagicMock()
    supabase.table.side_effect = [owned, pinned]
    monkeypatch.setattr(
        "app.routers.conversations.create_client",
        lambda *_args, **_kwargs: supabase,
    )
    response = client.post("/api/conversations/conv-1/pin")
    assert response.status_code == 200
    assert response.json()["pinned_at"] == "2026-07-20T12:00:00+00:00"


def test_list_conversations_search_includes_message_content(monkeypatch):
    _authenticate()
    title_chain = _table_chain(
        [
            {
                "id": "conv-title",
                "title": "Budget planning",
                "preview": None,
                "message_count": 1,
                "created_at": "2026-07-20T10:00:00+00:00",
                "updated_at": "2026-07-20T11:00:00+00:00",
                "archived_at": None,
                "pinned_at": None,
            }
        ]
    )
    owned_ids = _table_chain([{"id": "conv-content"}, {"id": "conv-title"}])
    message_hits = _table_chain([{"conversation_id": "conv-content"}])
    content_chain = _table_chain(
        [
            {
                "id": "conv-content",
                "title": "Ops sync",
                "preview": "mentions apollo lists",
                "message_count": 2,
                "created_at": "2026-07-19T10:00:00+00:00",
                "updated_at": "2026-07-20T12:00:00+00:00",
                "archived_at": None,
                "pinned_at": None,
            }
        ]
    )
    supabase = MagicMock()
    # title search query, owned ids for content search, message content query, content conv fetch
    supabase.table.side_effect = [title_chain, owned_ids, message_hits, content_chain]
    monkeypatch.setattr(
        "app.routers.conversations.create_client",
        lambda *_args, **_kwargs: supabase,
    )
    response = client.get("/api/conversations", params={"search": "apollo"})
    assert response.status_code == 200
    ids = [row["id"] for row in response.json()["conversations"]]
    assert "conv-content" in ids
    assert "conv-title" in ids


def test_delete_conversation_soft_delete(monkeypatch):
    _authenticate()
    soft_deleted = _table_chain([{"id": "conv-1"}])
    supabase = MagicMock()
    supabase.table.return_value = soft_deleted
    monkeypatch.setattr(
        "app.routers.conversations.create_client",
        lambda *_args, **_kwargs: supabase,
    )
    response = client.delete("/api/conversations/conv-1")
    assert response.status_code == 204
    soft_deleted.update.assert_called_once()


def test_delete_conversation_falls_back_to_hard_delete(monkeypatch):
    _authenticate()
    soft_fail = _table_chain([], error=Exception('column "deleted_at" of relation "conversations" does not exist'))
    hard_ok = _table_chain([{"id": "conv-1"}])
    supabase = MagicMock()
    supabase.table.side_effect = [soft_fail, hard_ok]
    monkeypatch.setattr(
        "app.routers.conversations.create_client",
        lambda *_args, **_kwargs: supabase,
    )
    response = client.delete("/api/conversations/conv-1")
    assert response.status_code == 204
    hard_ok.delete.assert_called_once()


def test_delete_conversation_falls_back_when_soft_update_matches_nothing(monkeypatch):
    _authenticate()
    soft_empty = _table_chain([])
    hard_ok = _table_chain([{"id": "conv-1"}])
    supabase = MagicMock()
    supabase.table.side_effect = [soft_empty, hard_ok]
    monkeypatch.setattr(
        "app.routers.conversations.create_client",
        lambda *_args, **_kwargs: supabase,
    )
    response = client.delete("/api/conversations/conv-1")
    assert response.status_code == 204
    soft_empty.update.assert_called_once()
    hard_ok.delete.assert_called_once()


def test_bulk_delete_conversations_skips_missing(monkeypatch):
    _authenticate()
    soft_ok = _table_chain([{"id": "conv-1"}])
    soft_empty = _table_chain([])
    hard_missing = _table_chain([])
    supabase = MagicMock()
    supabase.table.side_effect = [soft_ok, soft_empty, hard_missing]
    monkeypatch.setattr(
        "app.routers.conversations.create_client",
        lambda *_args, **_kwargs: supabase,
    )
    response = client.post(
        "/api/conversations/bulk-delete",
        json={"ids": ["conv-1", "conv-missing"]},
    )
    assert response.status_code == 204


def test_bulk_delete_conversations_dedupes_ids(monkeypatch):
    _authenticate()
    soft_ok = _table_chain([{"id": "conv-1"}])
    supabase = MagicMock()
    supabase.table.return_value = soft_ok
    monkeypatch.setattr(
        "app.routers.conversations.create_client",
        lambda *_args, **_kwargs: supabase,
    )
    response = client.post(
        "/api/conversations/bulk-delete",
        json={"ids": ["conv-1", "conv-1", " conv-1 "]},
    )
    assert response.status_code == 204
    assert supabase.table.call_count == 1
