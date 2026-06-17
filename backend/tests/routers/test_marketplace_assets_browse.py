"""Tests for unified /api/marketplace/assets browse routes (MKT-5.1)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user, get_environment_context, get_org_context, require_admin
from app.config import Settings, get_settings
from app.main import app
from app.marketplace.browse import MarketplaceBrowseError

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


def _authenticate(org_id: str = "org-1", admin: bool = False) -> None:
    app.dependency_overrides[get_current_user] = lambda: {"user_id": "user-1", "email": "u@example.com"}
    app.dependency_overrides[get_org_context] = lambda: org_id
    app.dependency_overrides[get_settings] = lambda: _settings()
    app.dependency_overrides[get_environment_context] = lambda: "production"
    if admin:
        app.dependency_overrides[require_admin] = lambda: ({"user_id": "user-1"}, org_id)


def test_list_assets_requires_org():
    app.dependency_overrides[get_current_user] = lambda: {"user_id": "user-1", "email": "u@example.com"}
    app.dependency_overrides[get_org_context] = lambda: None
    app.dependency_overrides[get_settings] = lambda: _settings()
    response = client.get("/api/marketplace/assets")
    assert response.status_code == 403


def test_list_assets_returns_catalog(monkeypatch):
    _authenticate()
    sample = {
        "assets": [
            {
                "id": "asset-1",
                "slug": "marketing-analyst",
                "title": "Marketing Analyst",
                "assetType": "ai_agent",
                "canInstall": True,
                "connectorChecklist": [],
            }
        ],
        "total": 1,
        "limit": 50,
        "offset": 0,
    }
    monkeypatch.setattr(
        "app.routers.marketplace.list_marketplace_assets",
        lambda *_a, **_k: sample,
    )
    response = client.get("/api/marketplace/assets?assetType=ai_agent&search=marketing")
    assert response.status_code == 200
    body = response.json()
    assert body["assets"][0]["slug"] == "marketing-analyst"
    assert body["total"] == 1


def test_get_asset_by_slug_returns_detail(monkeypatch):
    _authenticate()
    detail = {
        "asset": {
            "id": "asset-1",
            "slug": "marketing-analyst",
            "title": "Marketing Analyst",
            "assetType": "ai_agent",
            "canInstall": False,
            "blockers": [{"connector": "hubspot", "reason": "HubSpot is not connected", "action_url": "/connectors?type=hubspot"}],
            "connectorChecklist": [{"connectorType": "hubspot", "connected": False, "required": True}],
            "config": {"name": "Marketing Analyst"},
            "packItems": [],
        }
    }
    monkeypatch.setattr(
        "app.routers.marketplace.get_marketplace_asset",
        lambda *_a, **_k: detail,
    )
    response = client.get("/api/marketplace/assets/marketing-analyst")
    assert response.status_code == 200
    body = response.json()
    assert body["asset"]["slug"] == "marketing-analyst"
    assert body["asset"]["blockers"][0]["connector"] == "hubspot"


def test_get_asset_not_found(monkeypatch):
    _authenticate()

    def _raise(*_a, **_k):
        raise MarketplaceBrowseError("Marketplace asset not found", code="NOT_FOUND")

    monkeypatch.setattr("app.routers.marketplace.get_marketplace_asset", _raise)
    response = client.get("/api/marketplace/assets/missing-slug")
    assert response.status_code == 404
