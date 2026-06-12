"""Regression tests for /api/runs rollback alias (STA-173)."""
from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.auth.dependencies import get_environment_context, require_admin
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


def _authenticate_admin(*, org_id: str = "org-1", environment: str = "production") -> None:
    app.dependency_overrides[require_admin] = lambda: (
        {"user_id": "user-1", "email": "u@example.com"},
        org_id,
    )
    app.dependency_overrides[get_environment_context] = lambda: environment
    app.dependency_overrides[get_settings] = lambda: _settings()


def test_rollback_alias_forwards_arguments(monkeypatch: pytest.MonkeyPatch):
    run_id = uuid4()
    captured: dict[str, object] = {}

    async def fake_rollback(run_id_arg, current_user, org_id, environment_name, settings):
        captured["run_id"] = run_id_arg
        captured["current_user"] = current_user
        captured["org_id"] = org_id
        captured["environment_name"] = environment_name
        captured["settings"] = settings
        return {"run_id": str(run_id_arg), "status": "running"}

    monkeypatch.setattr(workflows_module, "rollback_run", fake_rollback)

    _authenticate_admin(environment="production")
    response = client.post(f"/api/runs/{run_id}/rollback", json={})

    assert response.status_code == 200
    assert captured["org_id"] == "org-1"
    assert captured["environment_name"] == "production"
    assert captured["current_user"] == {"user_id": "user-1", "email": "u@example.com"}
    assert isinstance(captured["settings"], Settings)


def test_rollback_alias_missing_run_returns_404(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(workflows_module, "get_run_with_steps", lambda *args, **kwargs: None)
    monkeypatch.setattr(workflows_module, "get_supabase_client", lambda _settings: object())

    _authenticate_admin(environment="production")
    response = client.post(f"/api/runs/{uuid4()}/rollback", json={})

    assert response.status_code == 404
    payload = response.json()
    assert payload.get("detail") == "Run not found" or payload.get("error") == "Run not found"
