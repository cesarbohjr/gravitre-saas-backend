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
    chain.order.return_value = chain
    chain.limit.return_value = chain
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
    table = _table_chain([created])
    supabase = MagicMock()
    supabase.table.return_value = table
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

    chain = MagicMock()
    chain.insert.return_value = chain
    chain.execute.return_value = V2Response([created])
    supabase = MagicMock()
    supabase.table.return_value = chain
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
