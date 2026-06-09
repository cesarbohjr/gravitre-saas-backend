"""Tests for /api/meson routes."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user, get_environment_context, get_org_context, require_admin
from app.config import Settings, get_settings
from app.main import app
from app.services.meson_service import (
    MesonDeployResult,
    MesonGeneratedConfig,
    MesonInterpretResult,
    MesonService,
    get_meson_service,
)

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
    app.dependency_overrides[get_environment_context] = lambda: "default"


def _mock_meson_service() -> MesonService:
    mock = MagicMock(spec=MesonService)
    plan = MesonInterpretResult(
        intent="Build sales follow-up automation",
        department="sales",
        systems=["crm"],
        outputTypes=["workflows"],
        generatedConfig=MesonGeneratedConfig(
            agent="Sales Agent",
            agent_role="Sales specialist",
            agent_description="Automates follow-ups",
            training=["CRM playbooks"],
            workflows=["Follow-up workflow"],
            sample_outputs=["Weekly pipeline summary"],
        ),
        confidence=0.8,
        explanation="Mock plan",
    )
    mock.interpret_build_request = AsyncMock(return_value=plan)
    mock.deploy_build = AsyncMock(
        return_value=MesonDeployResult(agentId="agent-123", workflowId="wf-456", result=plan)
    )
    return mock


def test_interpret_requires_org():
    app.dependency_overrides[get_current_user] = lambda: {"user_id": "user-1", "email": "u@example.com"}
    app.dependency_overrides[get_org_context] = lambda: None
    app.dependency_overrides[get_settings] = lambda: _settings()
    response = client.post(
        "/api/meson/interpret",
        json={"intent": "Build a support triage agent", "department": "operations", "systems": [], "outputTypes": []},
    )
    assert response.status_code == 403


def test_interpret_returns_plan():
    _authenticate()
    mock = _mock_meson_service()
    app.dependency_overrides[get_meson_service] = lambda: mock
    response = client.post(
        "/api/meson/interpret",
        json={
            "intent": "Build a support triage agent",
            "department": "operations",
            "systems": ["messaging"],
            "outputTypes": ["workflows"],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["generatedConfig"]["agent"] == "Sales Agent"
    assert body["systems"] == ["crm"]
    mock.interpret_build_request.assert_awaited_once()


def test_deploy_creates_resources():
    _authenticate()
    mock = _mock_meson_service()
    app.dependency_overrides[get_meson_service] = lambda: mock
    app.dependency_overrides[require_admin] = lambda: ({"user_id": "user-1"}, "org-1")
    response = client.post(
        "/api/meson/deploy",
        json={
            "intent": "Build a support triage agent",
            "department": "operations",
            "systems": ["messaging"],
            "outputTypes": ["workflows"],
            "generatedConfig": {"agent": "Ops Agent"},
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["agentId"] == "agent-123"
    assert body["workflowId"] == "wf-456"
    mock.deploy_build.assert_awaited_once()
