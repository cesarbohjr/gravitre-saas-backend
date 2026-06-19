"""MKT-AUDIT-11.2: Gravitre public review queue routes."""
from __future__ import annotations

import pytest
from fastapi import HTTPException, status
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user, get_environment_context, get_org_context, require_platform_admin
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


def _authenticate_platform_admin() -> None:
    app.dependency_overrides[get_current_user] = lambda: {"user_id": "platform-1", "email": "admin@gravitre.test"}
    app.dependency_overrides[get_org_context] = lambda: None
    app.dependency_overrides[get_settings] = lambda: _settings()
    app.dependency_overrides[get_environment_context] = lambda: "production"
    app.dependency_overrides[require_platform_admin] = lambda: {"user_id": "platform-1", "email": "admin@gravitre.test"}


def _deny_platform_admin() -> dict:
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Platform admin required")


def test_platform_review_queue_requires_platform_admin():
    _authenticate_platform_admin()
    app.dependency_overrides[require_platform_admin] = _deny_platform_admin
    response = client.get("/api/marketplace/platform/review-queue")
    assert response.status_code == 403


def test_platform_review_queue_route(monkeypatch):
    _authenticate_platform_admin()
    monkeypatch.setattr(
        "app.routers.marketplace.list_public_review_queue",
        lambda *_a, **_k: {"assets": [{"slug": "public-agent"}], "total": 1, "limit": 50, "offset": 0},
    )
    response = client.get("/api/marketplace/platform/review-queue")
    assert response.status_code == 200
    assert response.json()["total"] == 1


def test_platform_review_asset_detail_route(monkeypatch):
    _authenticate_platform_admin()
    monkeypatch.setattr(
        "app.routers.marketplace.get_public_review_asset_detail",
        lambda *_a, **_k: {"asset": {"slug": "public-agent", "config": {"prompt": "hi"}}},
    )
    response = client.get("/api/marketplace/platform/assets/public-agent/review")
    assert response.status_code == 200
    assert response.json()["asset"]["slug"] == "public-agent"


def test_platform_approve_public_asset_route(monkeypatch):
    _authenticate_platform_admin()
    monkeypatch.setattr(
        "app.routers.marketplace.approve_asset_for_public_publish",
        lambda *_a, **_k: {"approved": True, "asset": {"slug": "public-agent", "visibility": "public"}},
    )
    response = client.post("/api/marketplace/platform/assets/public-agent/approve")
    assert response.status_code == 200
    assert response.json()["approved"] is True


def test_platform_reject_public_asset_route(monkeypatch):
    _authenticate_platform_admin()
    monkeypatch.setattr(
        "app.routers.marketplace.reject_asset_public_review",
        lambda *_a, **_k: {"rejected": True, "reason": "Needs work", "asset": {"slug": "public-agent"}},
    )
    response = client.post(
        "/api/marketplace/platform/assets/public-agent/reject",
        json={"reason": "Needs work"},
    )
    assert response.status_code == 200
    assert response.json()["rejected"] is True


def test_platform_catalog_route(monkeypatch):
    _authenticate_platform_admin()
    monkeypatch.setattr(
        "app.routers.marketplace.list_platform_public_catalog",
        lambda *_a, **_k: {"assets": [{"slug": "sales-pack", "featured": True}], "total": 1, "limit": 50, "offset": 0},
    )
    response = client.get("/api/marketplace/platform/catalog?featured=true")
    assert response.status_code == 200
    assert response.json()["assets"][0]["featured"] is True


def test_platform_featured_flag_route(monkeypatch):
    _authenticate_platform_admin()
    monkeypatch.setattr(
        "app.routers.marketplace.set_asset_featured",
        lambda *_a, **_k: {"featured": True, "asset": {"slug": "sales-pack", "featured": True}},
    )
    response = client.post(
        "/api/marketplace/platform/assets/sales-pack/featured",
        json={"enabled": True},
    )
    assert response.status_code == 200
    assert response.json()["featured"] is True


def test_platform_verified_flag_route(monkeypatch):
    _authenticate_platform_admin()
    monkeypatch.setattr(
        "app.routers.marketplace.set_asset_verified",
        lambda *_a, **_k: {"verified": True, "asset": {"slug": "sales-pack", "verified": True}},
    )
    response = client.post(
        "/api/marketplace/platform/assets/sales-pack/verified",
        json={"enabled": True},
    )
    assert response.status_code == 200
    assert response.json()["verified"] is True
