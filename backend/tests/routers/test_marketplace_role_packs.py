"""Tests for /api/marketplace/role-packs routes (STA-168)."""
from __future__ import annotations

from unittest.mock import MagicMock

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


def _authenticate(org_id: str = "org-1", admin: bool = True) -> None:
    app.dependency_overrides[get_current_user] = lambda: {"user_id": "user-1", "email": "u@example.com"}
    app.dependency_overrides[get_org_context] = lambda: org_id
    app.dependency_overrides[get_settings] = lambda: _settings()
    app.dependency_overrides[get_environment_context] = lambda: "production"
    if admin:
        app.dependency_overrides[require_admin] = lambda: ({"user_id": "user-1"}, org_id)


def test_list_role_packs_requires_org():
    app.dependency_overrides[get_current_user] = lambda: {"user_id": "user-1", "email": "u@example.com"}
    app.dependency_overrides[get_org_context] = lambda: None
    app.dependency_overrides[get_settings] = lambda: _settings()
    response = client.get("/api/marketplace/role-packs")
    assert response.status_code == 403


def test_list_role_packs_returns_catalog(monkeypatch):
    _authenticate()
    sample = [
        {
            "packId": "sales-ops",
            "name": "Sales Operations Pack",
            "department": "sales",
            "installed": False,
            "connectorChecklist": [],
        }
    ]
    monkeypatch.setattr(
        "app.routers.marketplace.list_department_packs",
        lambda *_a, **_k: sample,
    )
    response = client.get("/api/marketplace/role-packs")
    assert response.status_code == 200
    body = response.json()
    assert body["packs"][0]["packId"] == "sales-ops"


def test_install_role_pack_returns_created_resources(monkeypatch):
    _authenticate()
    installed = {
        "packId": "sales-ops",
        "department": "sales",
        "installed": True,
        "agentIds": ["agent-1"],
        "workflowIds": ["wf-1"],
        "ragSourceIds": ["rag-1"],
        "connectorChecklist": [{"connectorType": "hubspot", "label": "HubSpot", "connected": True, "required": True}],
    }
    monkeypatch.setattr(
        "app.routers.marketplace.install_department_pack",
        lambda *_a, **_k: installed,
    )
    response = client.post("/api/marketplace/role-packs/sales-ops/install")
    assert response.status_code == 200
    body = response.json()
    assert body["agentIds"] == ["agent-1"]
    assert body["workflowIds"] == ["wf-1"]
    assert body["connectorChecklist"][0]["connected"] is True
