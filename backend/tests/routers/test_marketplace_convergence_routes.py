"""MKT-AUDIT-13.1: Federated connector and registry sync routes."""
from __future__ import annotations

import pytest
from fastapi import HTTPException, status
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user, get_environment_context, get_org_context, require_platform_admin
from app.config import Settings, get_settings
from app.main import app
from app.marketplace.convergence import MarketplaceConvergenceError

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


def _authenticate_org_user() -> None:
    app.dependency_overrides[get_current_user] = lambda: {"user_id": "user-1", "email": "user@test.com"}
    app.dependency_overrides[get_org_context] = lambda: "org-1"
    app.dependency_overrides[get_settings] = lambda: _settings()
    app.dependency_overrides[get_environment_context] = lambda: "production"


def _authenticate_platform_admin() -> None:
    app.dependency_overrides[get_current_user] = lambda: {"user_id": "platform-1", "email": "admin@gravitre.test"}
    app.dependency_overrides[get_org_context] = lambda: None
    app.dependency_overrides[get_settings] = lambda: _settings()
    app.dependency_overrides[get_environment_context] = lambda: "production"
    app.dependency_overrides[require_platform_admin] = lambda: {"user_id": "platform-1", "email": "admin@gravitre.test"}


def test_federated_connectors_requires_org_context():
    app.dependency_overrides[get_current_user] = lambda: {"user_id": "user-1", "email": "user@test.com"}
    app.dependency_overrides[get_org_context] = lambda: None
    app.dependency_overrides[get_settings] = lambda: _settings()
    response = client.get("/api/marketplace/federated-connectors")
    assert response.status_code == 403


def test_federated_connectors_route(monkeypatch):
    _authenticate_org_user()
    monkeypatch.setattr(
        "app.routers.marketplace.list_federated_connector_assets",
        lambda *_a, **_k: {"assets": [{"registryId": "reg-1", "title": "Acme"}], "total": 1},
    )
    response = client.get("/api/marketplace/federated-connectors")
    assert response.status_code == 200
    assert response.json()["total"] == 1


def test_platform_sync_registry_asset_route(monkeypatch):
    _authenticate_platform_admin()

    class _Result:
        data = [{"id": "reg-1", "status": "published", "vendor": "acme", "name": "Acme Tools"}]

    registry_table = type("T", (), {"select": lambda *_a, **_k: registry_table, "eq": lambda *_a, **_k: registry_table, "limit": lambda *_a, **_k: registry_table, "execute": lambda *_a, **_k: _Result()})()
    client_mock = type("C", (), {"table": lambda *_a, **_k: registry_table})()
    monkeypatch.setattr("app.routers.marketplace.create_client", lambda *_a, **_k: client_mock)
    monkeypatch.setattr(
        "app.routers.marketplace.upsert_connector_asset_from_registry",
        lambda *_a, **_k: {"created": True, "assetId": "asset-1", "slug": "partner-acme"},
    )

    response = client.post("/api/marketplace/platform/registry/reg-1/sync-asset")
    assert response.status_code == 200
    assert response.json()["assetId"] == "asset-1"


def test_platform_link_asset_registry_route(monkeypatch):
    _authenticate_platform_admin()
    monkeypatch.setattr(
        "app.marketplace.crud._fetch_asset",
        lambda *_a, **_k: {"id": "asset-1", "slug": "partner-acme"},
    )
    monkeypatch.setattr(
        "app.routers.marketplace.link_asset_to_registry",
        lambda *_a, **_k: {"assetId": "asset-1", "registryId": "reg-1", "vendor": "acme"},
    )
    monkeypatch.setattr("app.routers.marketplace.create_client", lambda *_a, **_k: object())

    response = client.post(
        "/api/marketplace/platform/assets/partner-acme/link-registry",
        json={"registryId": "reg-1"},
    )
    assert response.status_code == 200
    assert response.json()["registryId"] == "reg-1"


def test_platform_link_asset_registry_maps_convergence_error(monkeypatch):
    _authenticate_platform_admin()
    monkeypatch.setattr(
        "app.marketplace.crud._fetch_asset",
        lambda *_a, **_k: {"id": "asset-1", "slug": "partner-acme"},
    )

    def _raise(*_a, **_k):
        raise MarketplaceConvergenceError("registry not found or not published", code="NOT_FOUND")

    monkeypatch.setattr("app.routers.marketplace.link_asset_to_registry", _raise)
    monkeypatch.setattr("app.routers.marketplace.create_client", lambda *_a, **_k: object())

    response = client.post(
        "/api/marketplace/platform/assets/partner-acme/link-registry",
        json={"registryId": "reg-missing"},
    )
    assert response.status_code == 404


def test_platform_sync_registry_asset_requires_platform_admin():
    _authenticate_platform_admin()
    app.dependency_overrides[require_platform_admin] = lambda: (_ for _ in ()).throw(
        HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Platform admin required")
    )
    response = client.post("/api/marketplace/platform/registry/reg-1/sync-asset")
    assert response.status_code == 403
