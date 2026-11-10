"""ECO-001 authenticated Chat HTTP execution ingress authorization boundary.

These focused route tests are not the full provider/ledger integration certificate.
They prove that an authenticated requester cannot execute another tenant's or
another user's conversation before dispatch is reached.
"""
from unittest.mock import MagicMock, patch

import pytest

from app.auth.dependencies import (
    get_current_user, get_environment_context, get_org_context,
)
from app.config import Settings, get_settings
from app.main import app


class _ConversationLookup:
    def __init__(self, rows):
        self.rows = rows
        self.filters = []

    def select(self, *_args):
        return self

    def eq(self, column, value):
        self.filters.append((column, value))
        return self

    def limit(self, *_args):
        return self

    def execute(self):
        matches = [
            row for row in self.rows
            if all(row.get(column) == value for column, value in self.filters)
        ]
        return MagicMock(data=matches)


class _ScopedClient:
    def __init__(self, rows):
        self.rows = rows
        self.queries = []

    def table(self, name):
        assert name == "conversations", (
            "Execution advanced past authenticated conversation ownership gate"
        )
        query = _ConversationLookup(self.rows)
        self.queries.append(query)
        return query


@pytest.mark.parametrize("rows", [
    [{"id": "other-conversation", "org_id": "tenant-a", "user_id": "actor-a"}],
    [{"id": "conversation-a", "org_id": "tenant-b", "user_id": "actor-a"}],
    [{"id": "conversation-a", "org_id": "tenant-a", "user_id": "actor-b"}],
])
def test_authenticated_chat_execute_refuses_unowned_conversation(rows):
    from fastapi.testclient import TestClient
    from app.routers import assistant

    settings = Settings(
        app_env="dev", supabase_url="https://test.supabase.co",
        supabase_anon_key="anon-test",
        supabase_service_role_key="service-role-test",
        supabase_jwt_secret="jwt-secret-test",
    )
    db = _ScopedClient(rows)
    app.dependency_overrides[get_current_user] = lambda: {"user_id": "actor-a"}
    app.dependency_overrides[get_org_context] = lambda: "tenant-a"
    app.dependency_overrides[get_environment_context] = lambda: "production"
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        with patch.object(assistant, "get_supabase_client", return_value=db):
            response = TestClient(app).post(
                "/api/assistant/conversation/conversation-a/execute",
                json={"confirm": True},
            )
        assert response.status_code == 404, response.text
        assert len(db.queries) == 1
        assert db.queries[0].filters == [
            ("id", "conversation-a"),
            ("org_id", "tenant-a"),
            ("user_id", "actor-a"),
        ]
    finally:
        app.dependency_overrides.clear()
