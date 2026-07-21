"""Saved questions API — durable Save Question for /ai."""
from __future__ import annotations

from unittest.mock import MagicMock

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


def test_save_question_inserts_row(monkeypatch):
    _authenticate()
    inserted = {
        "id": "sq-1",
        "org_id": "org-1",
        "user_id": "user-1",
        "conversation_id": None,
        "message_id": "msg-1",
        "question_text": "What ran yesterday?",
        "created_at": "2026-07-21T08:00:00+00:00",
    }
    # First execute = empty existing lookup; second = insert result.
    table = MagicMock()
    select_chain = MagicMock()
    select_chain.eq.return_value = select_chain
    select_chain.limit.return_value = select_chain
    select_chain.execute.return_value = MagicMock(data=[], error=None)
    table.select.return_value = select_chain
    insert_chain = MagicMock()
    insert_chain.execute.return_value = MagicMock(data=[inserted], error=None)
    table.insert.return_value = insert_chain
    supabase = MagicMock()
    supabase.table.return_value = table
    monkeypatch.setattr(
        "app.routers.conversations.create_client",
        lambda *_args, **_kwargs: supabase,
    )
    try:
        response = client.post(
            "/api/conversations/saved-questions",
            json={"question_text": "What ran yesterday?", "message_id": "msg-1"},
        )
        assert response.status_code == 201
        body = response.json()
        assert body["question_text"] == "What ran yesterday?"
        assert body["message_id"] == "msg-1"
        table.insert.assert_called_once()
    finally:
        app.dependency_overrides.clear()


def test_list_saved_questions(monkeypatch):
    _authenticate()
    row = {
        "id": "sq-1",
        "org_id": "org-1",
        "user_id": "user-1",
        "conversation_id": None,
        "message_id": "msg-1",
        "question_text": "Saved?",
        "created_at": "2026-07-21T08:00:00+00:00",
    }
    table = _table_chain([row])
    supabase = MagicMock()
    supabase.table.return_value = table
    monkeypatch.setattr(
        "app.routers.conversations.create_client",
        lambda *_args, **_kwargs: supabase,
    )
    try:
        response = client.get("/api/conversations/saved-questions")
        assert response.status_code == 200
        assert response.json()["saved_questions"][0]["question_text"] == "Saved?"
    finally:
        app.dependency_overrides.clear()
