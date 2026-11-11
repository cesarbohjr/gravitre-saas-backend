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


@pytest.mark.parametrize("pending_type", ["connector_action", "connector_orchestration"])
def test_authenticated_chat_execute_denied_approval_never_dispatches(pending_type):
    """An owned conversation is insufficient authority for a connector write.

    Exercise the actual authenticated HTTP route and its HITL decision, while
    asserting that neither Chat execution adapter can be reached on denial.
    This is an ingress regression, not the independent provider/PG certificate.
    """
    from fastapi.testclient import TestClient
    from app.routers import assistant
    from app.services import chat_connector_execution_service, chat_orchestration_service
    from app.services import conversation_state_service
    from app.workflows import policy

    settings = Settings(
        app_env="dev", supabase_url="https://test.supabase.co",
        supabase_anon_key="anon-test",
        supabase_service_role_key="service-role-test",
        supabase_jwt_secret="jwt-secret-test",
    )
    db = _ScopedClient([
        {"id": "conversation-a", "org_id": "tenant-a", "user_id": "actor-a"},
    ])
    state = {
        "pending_task": {
            "type": pending_type,
            "status": "awaiting_confirm",
            "params": {
                "kind": "write",
                "invoke_action": "hubspot.contacts.update",
                "hitl_action_kind": "write",
            },
        },
    }
    state_service = MagicMock()
    from unittest.mock import AsyncMock
    state_service.get_task_state = AsyncMock(return_value=state)
    hitl = MagicMock()
    hitl.can_approve.return_value = False
    policy_service = MagicMock()
    policy_service.resolve.return_value = hitl

    app.dependency_overrides[get_current_user] = lambda: {"user_id": "actor-a"}
    app.dependency_overrides[get_org_context] = lambda: "tenant-a"
    app.dependency_overrides[get_environment_context] = lambda: "production"
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        with (
            patch.object(assistant, "get_supabase_client", return_value=db),
            patch.object(conversation_state_service, "get_conversation_state_service", return_value=state_service),
            patch.object(policy, "get_user_role", return_value="member"),
            patch("app.services.hitl_policy_service.get_hitl_policy_service", return_value=policy_service),
            patch.object(chat_connector_execution_service, "get_chat_connector_execution_service") as connector_dispatch,
            patch.object(chat_orchestration_service, "get_chat_orchestration_service") as orchestration_dispatch,
        ):
            response = TestClient(app).post(
                "/api/assistant/conversation/conversation-a/execute",
                json={"confirm": True},
            )
        assert response.status_code == 403, response.text
        assert "approval" in response.json()["detail"].lower()
        connector_dispatch.assert_not_called()
        orchestration_dispatch.assert_not_called()
        hitl.can_approve.assert_called_once_with(role="member", user_id="actor-a")
        assert db.queries[0].filters == [
            ("id", "conversation-a"),
            ("org_id", "tenant-a"),
            ("user_id", "actor-a"),
        ]
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize("pending_type", ["connector_action", "connector_orchestration"])
def test_authenticated_approved_chat_routes_to_correct_execution_owner(pending_type):
    """The owned, approved HTTP path must preserve tenant, actor and environment.

    The adapter is substituted only at its downstream service boundary. This
    certifies ingress-to-adapter routing, not durable provider execution.
    """
    from fastapi.testclient import TestClient
    from unittest.mock import AsyncMock
    from app.routers import assistant
    from app.services import chat_connector_execution_service, chat_orchestration_service
    from app.services import conversation_state_service
    from app.workflows import policy

    settings = Settings(
        app_env="dev", supabase_url="https://test.supabase.co",
        supabase_anon_key="anon-test",
        supabase_service_role_key="service-role-test",
        supabase_jwt_secret="jwt-secret-test",
    )
    db = _ScopedClient([
        {"id": "conversation-a", "org_id": "tenant-a", "user_id": "actor-a"},
    ])
    state_service = MagicMock()
    state_service.get_task_state = AsyncMock(return_value={
        "pending_task": {
            "type": pending_type,
            "status": "awaiting_confirm",
            "params": {"kind": "write", "invoke_action": "hubspot.contacts.update",
                       "hitl_action_kind": "write"},
        },
    })
    hitl = MagicMock()
    hitl.can_approve.return_value = True
    policy_service = MagicMock()
    policy_service.resolve.return_value = hitl
    # The HTTP response serializes execution.__dict__; MagicMock internals
    # contain sentinel values that Pydantic cannot JSON-encode.
    execution = SimpleNamespace(
        success=True, title="Approved write", body="Recorded.",
        result_url="/runs/synthetic",
    )
    connector = MagicMock()
    connector.execute_confirmed_task = AsyncMock(return_value=execution)
    orchestration = MagicMock()
    orchestration.execute_confirmed_task = AsyncMock(return_value=execution)

    app.dependency_overrides[get_current_user] = lambda: {"user_id": "actor-a"}
    app.dependency_overrides[get_org_context] = lambda: "tenant-a"
    app.dependency_overrides[get_environment_context] = lambda: "synthetic"
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        with (
            patch.object(assistant, "get_supabase_client", return_value=db),
            patch.object(conversation_state_service, "get_conversation_state_service", return_value=state_service),
            patch.object(policy, "get_user_role", return_value="admin"),
            patch("app.services.hitl_policy_service.get_hitl_policy_service", return_value=policy_service),
            patch.object(chat_connector_execution_service, "get_chat_connector_execution_service", return_value=connector),
            patch.object(chat_orchestration_service, "get_chat_orchestration_service", return_value=orchestration),
            patch.object(assistant, "_persist_conversation_turn", return_value=(True, "synthetic-message")),
            patch("app.services.response_composer.compose_user_reply", new_callable=AsyncMock, return_value="Recorded."),
        ):
            response = TestClient(app).post(
                "/api/assistant/conversation/conversation-a/execute",
                json={"confirm": True},
            )
        assert response.status_code == 200, response.text
        assert response.json()["success"] is True
        selected, other = (
            (connector, orchestration) if pending_type == "connector_action"
            else (orchestration, connector)
        )
        selected.execute_confirmed_task.assert_awaited_once_with(
            org_id="tenant-a", user_id="actor-a",
            conversation_id="conversation-a", client=db,
            environment_name="synthetic",
        )
        other.execute_confirmed_task.assert_not_awaited()
        hitl.can_approve.assert_called_once_with(role="admin", user_id="actor-a")
    finally:
        app.dependency_overrides.clear()


def test_chat_execute_missing_bearer_rejected_by_real_auth_dependency():
    """Do not override authentication: the mounted endpoint must reject an
    unauthenticated request before conversation or provider dispatch.
    """
    from fastapi.testclient import TestClient
    from app.routers import assistant
    from app.services import chat_connector_execution_service, chat_orchestration_service

    settings = Settings(
        app_env="dev", supabase_url="https://test.supabase.co",
        supabase_anon_key="anon-test", supabase_service_role_key="service-role-test",
        supabase_jwt_secret="jwt-secret-test",
    )
    app.dependency_overrides.clear()
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        with (
            patch.object(assistant, "get_supabase_client") as database,
            patch.object(chat_connector_execution_service, "get_chat_connector_execution_service") as connector,
            patch.object(chat_orchestration_service, "get_chat_orchestration_service") as orchestration,
        ):
            response = TestClient(app).post(
                "/api/assistant/conversation/conversation-a/execute",
                json={"confirm": True},
            )
        assert response.status_code == 401, response.text
        database.assert_not_called()
        connector.assert_not_called()
        orchestration.assert_not_called()
    finally:
        app.dependency_overrides.clear()


def test_real_signed_jwt_cannot_execute_another_users_chat():
    """Verify real JWT signature/claims on the mounted HTTP route; the
    synthetic org dependency is the only auth-related boundary substituted.
    The user ownership check must still prevent provider dispatch.
    """
    import time
    import jwt
    from fastapi.testclient import TestClient
    from app.routers import assistant
    from app.services import chat_connector_execution_service, chat_orchestration_service

    settings = Settings(
        app_env="dev", supabase_url="https://test.supabase.co",
        supabase_anon_key="anon-test", supabase_service_role_key="service-role-test",
        supabase_jwt_secret="jwt-secret-test",
    )
    token = jwt.encode({
        "sub": "actor-a", "aud": settings.jwt_audience,
        "iss": settings.jwt_issuer, "iat": int(time.time()),
        "exp": int(time.time()) + 300,
    }, settings.supabase_jwt_secret, algorithm="HS256")
    db = _ScopedClient([{
        "id": "conversation-a", "org_id": "tenant-a", "user_id": "actor-b",
    }])
    app.dependency_overrides.clear()
    app.dependency_overrides[get_org_context] = lambda: "tenant-a"
    app.dependency_overrides[get_environment_context] = lambda: "synthetic"
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        with (
            patch.object(assistant, "get_supabase_client", return_value=db),
            patch.object(chat_connector_execution_service, "get_chat_connector_execution_service") as connector,
            patch.object(chat_orchestration_service, "get_chat_orchestration_service") as orchestration,
        ):
            response = TestClient(app).post(
                "/api/assistant/conversation/conversation-a/execute",
                json={"confirm": True},
                headers={"Authorization": f"Bearer {token}"},
            )
        assert response.status_code == 404, response.text
        assert db.queries[0].filters == [
            ("id", "conversation-a"), ("org_id", "tenant-a"),
            ("user_id", "actor-a"),
        ]
        connector.assert_not_called()
        orchestration.assert_not_called()
    finally:
        app.dependency_overrides.clear()
