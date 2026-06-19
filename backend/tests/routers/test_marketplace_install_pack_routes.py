"""MKT-AUDIT-5.5: Router coverage for department_pack and knowledge_pack install."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user, get_environment_context, get_org_context, require_admin
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


def _authenticate_admin(org_id: str = "org-1") -> None:
    app.dependency_overrides[get_current_user] = lambda: {"user_id": "user-1", "email": "u@example.com"}
    app.dependency_overrides[get_org_context] = lambda: org_id
    app.dependency_overrides[get_settings] = lambda: _settings()
    app.dependency_overrides[get_environment_context] = lambda: "production"
    app.dependency_overrides[require_admin] = lambda: ({"user_id": "user-1"}, org_id)


def test_install_knowledge_pack_route(monkeypatch):
    _authenticate_admin()
    installed = {
        "installed": True,
        "entities": {
            "entityType": "knowledge_pack",
            "ragSourceIds": ["rag-1", "rag-2"],
        },
    }
    monkeypatch.setattr("app.routers.marketplace.install_asset", lambda *_a, **_k: installed)
    response = client.post("/api/marketplace/assets/marketing-knowledge/install", json={})
    assert response.status_code == 200
    body = response.json()
    assert body["entities"]["entityType"] == "knowledge_pack"
    assert len(body["entities"]["ragSourceIds"]) == 2


def test_install_department_pack_route(monkeypatch):
    _authenticate_admin()
    installed = {
        "installed": True,
        "entities": {
            "entityType": "department_pack",
            "agentIds": ["agent-1"],
            "workflowIds": ["wf-1"],
            "ragSourceIds": ["rag-1"],
            "failures": [],
        },
    }
    monkeypatch.setattr("app.routers.marketplace.install_asset", lambda *_a, **_k: installed)
    response = client.post("/api/marketplace/assets/marketing-ops-pack/install", json={})
    assert response.status_code == 200
    body = response.json()
    assert body["entities"]["entityType"] == "department_pack"
    assert body["entities"]["agentIds"]
    assert body["entities"]["workflowIds"]
