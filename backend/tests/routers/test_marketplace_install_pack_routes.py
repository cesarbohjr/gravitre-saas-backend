"""MKT-AUDIT-5.5: Router coverage for department_pack and knowledge_pack install."""
from __future__ import annotations

from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user, get_environment_context, get_org_context, require_admin, require_capability
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
    app.dependency_overrides[require_capability("install_marketplace")] = lambda: ({"user_id": "user-1"}, org_id)


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


def test_install_route_forwards_explicit_agent_snapshot_version(monkeypatch):
    _authenticate_admin()
    store = object()
    installer = Mock(return_value={"installed": True})
    monkeypatch.setattr("app.routers.marketplace.shared_service_client", lambda *_: store)
    monkeypatch.setattr("app.routers.marketplace.install_asset", installer)
    response = client.post("/api/marketplace/assets/content-writer/install", json={"versionNumber": 1})
    assert response.status_code == 200
    assert installer.call_args.args == (store, "org-1", "content-writer")
    assert installer.call_args.kwargs["version_number"] == 1
    assert installer.call_args.kwargs["actor_id"] == "user-1"


@pytest.mark.parametrize("version", [0, True, "1"])
def test_install_route_rejects_invalid_snapshot_version_before_writes(monkeypatch, version):
    _authenticate_admin()
    installer = Mock()
    monkeypatch.setattr("app.routers.marketplace.install_asset", installer)
    response = client.post("/api/marketplace/assets/content-writer/install", json={"versionNumber": version})
    assert response.status_code == 422
    installer.assert_not_called()
