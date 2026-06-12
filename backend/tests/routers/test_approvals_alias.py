"""Regression tests for /api/approvals approve/reject aliases (STA-173)."""
from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user, get_environment_context, get_org_context
from app.config import Settings, get_settings
from app.main import app
from app.routers import workflows as workflows_module

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


def _authenticate(*, org_id: str = "org-1", environment: str = "production") -> None:
    app.dependency_overrides[get_current_user] = lambda: {"user_id": "user-1", "email": "u@example.com"}
    app.dependency_overrides[get_org_context] = lambda: org_id
    app.dependency_overrides[get_environment_context] = lambda: environment
    app.dependency_overrides[get_settings] = lambda: _settings()


def test_approvals_approve_alias_forwards_environment(monkeypatch: pytest.MonkeyPatch):
    run_id = uuid4()
    captured: dict[str, object] = {}

    async def fake_approve(run_id_arg, body, current_user, org_id, environment_name, settings):
        captured["environment_name"] = environment_name
        captured["settings"] = settings
        return {"run_id": str(run_id_arg), "status": "pending_approval"}

    monkeypatch.setattr(workflows_module, "approve_run", fake_approve)
    monkeypatch.setattr(
        workflows_module,
        "get_supabase_client",
        lambda _settings: object(),
    )
    monkeypatch.setattr(workflows_module, "get_plan_for_org", lambda _client, _org: {"features": {"approvals": True}})
    monkeypatch.setattr(workflows_module, "require_feature", lambda _plan, _feature: None)

    _authenticate(environment="production")
    response = client.post(f"/api/approvals/{run_id}/approve", json={})

    assert response.status_code == 200
    assert captured["environment_name"] == "production"
    assert isinstance(captured["settings"], Settings)


def test_approve_run_emits_approval_recorded(monkeypatch: pytest.MonkeyPatch):
    run_id = uuid4()
    emitted: list[str] = []
    mock_client = object()

    monkeypatch.setattr(
        workflows_module,
        "get_supabase_client",
        lambda _settings: mock_client,
    )
    monkeypatch.setattr(workflows_module, "get_plan_for_org", lambda _client, _org: {"features": {"approvals": True}})
    monkeypatch.setattr(workflows_module, "require_feature", lambda _plan, _feature: None)
    monkeypatch.setattr(
        workflows_module,
        "get_run_with_steps",
        lambda _client, _org, _run_id, _env: {
            "run_type": workflows_module.RUN_TYPE_EXECUTE,
            "status": workflows_module.RUN_STATUS_PENDING_APPROVAL,
            "required_approvals": 1,
            "definition_snapshot": {"steps": []},
            "parameters": {},
            "environment": "production",
        },
    )
    monkeypatch.setattr(workflows_module, "get_user_role", lambda *_a, **_k: "admin")
    monkeypatch.setattr(workflows_module, "insert_run_approval", lambda *_a, **_k: {"status": "approved"})
    monkeypatch.setattr(
        workflows_module,
        "emit_execute_approval_recorded",
        lambda *_a, **_k: emitted.append("recorded"),
    )
    monkeypatch.setattr(workflows_module, "get_approval_counts", lambda *_a, **_k: (0, False))

    _authenticate(environment="production")
    response = client.post(f"/api/approvals/{run_id}/approve", json={})

    assert response.status_code == 200
    assert emitted == ["recorded"]


def test_approvals_reject_alias_forwards_environment(monkeypatch: pytest.MonkeyPatch):
    run_id = uuid4()
    captured: dict[str, object] = {}

    async def fake_reject(run_id_arg, body, current_user, org_id, environment_name, settings):
        captured["environment_name"] = environment_name
        return {"run_id": str(run_id_arg), "status": "cancelled"}

    monkeypatch.setattr(workflows_module, "reject_run", fake_reject)
    monkeypatch.setattr(
        workflows_module,
        "get_supabase_client",
        lambda _settings: object(),
    )
    monkeypatch.setattr(workflows_module, "get_plan_for_org", lambda _client, _org: {"features": {"approvals": True}})
    monkeypatch.setattr(workflows_module, "require_feature", lambda _plan, _feature: None)

    _authenticate(environment="production")
    response = client.post(f"/api/approvals/{run_id}/reject", json={"comment": "no"})

    assert response.status_code == 200
    assert captured["environment_name"] == "production"
