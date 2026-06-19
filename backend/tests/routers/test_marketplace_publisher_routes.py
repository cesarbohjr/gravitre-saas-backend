"""MKT-AUDIT-11.1: Creator publisher onboarding routes."""
from __future__ import annotations

import pytest
from fastapi import HTTPException, status
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user, get_environment_context, get_org_context, require_admin
from app.config import Settings, get_settings
from app.main import app

client = TestClient(app)

ORG_ID = "org-11111111-1111-1111-1111-111111111111"


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


def _authenticate_admin(org_id: str = ORG_ID) -> None:
    app.dependency_overrides[get_current_user] = lambda: {"user_id": "user-1", "email": "u@example.com"}
    app.dependency_overrides[get_org_context] = lambda: org_id
    app.dependency_overrides[get_settings] = lambda: _settings()
    app.dependency_overrides[get_environment_context] = lambda: "production"
    app.dependency_overrides[require_admin] = lambda: ({"user_id": "user-1"}, org_id)


def _deny_admin() -> tuple[dict, str]:
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")


def test_publisher_profile_requires_admin():
    _authenticate_admin()
    app.dependency_overrides[require_admin] = _deny_admin
    response = client.get("/api/marketplace/publisher/me")
    assert response.status_code == 403


def test_publisher_profile_route(monkeypatch):
    _authenticate_admin()
    sample = {
        "id": "pub-1",
        "slug": "acme-creators",
        "displayName": "Acme Creators",
        "publicPublishingEnabled": True,
        "verified": False,
        "status": "active",
    }
    monkeypatch.setattr(
        "app.routers.marketplace.get_org_publisher_profile",
        lambda *_a, **_k: sample,
    )
    response = client.get("/api/marketplace/publisher/me")
    assert response.status_code == 200
    assert response.json()["publisher"]["slug"] == "acme-creators"


def test_publisher_onboard_route(monkeypatch):
    _authenticate_admin()
    monkeypatch.setattr(
        "app.routers.marketplace.onboard_org_publisher",
        lambda *_a, **_k: {
            "onboarded": True,
            "publisher": {
                "id": "pub-1",
                "slug": "acme-creators",
                "displayName": "Acme Creators",
                "publicPublishingEnabled": True,
                "verified": False,
                "status": "active",
            },
        },
    )
    response = client.post(
        "/api/marketplace/publisher/onboard",
        json={"displayName": "Acme Creators", "slug": "acme-creators"},
    )
    assert response.status_code == 200
    assert response.json()["publisher"]["publicPublishingEnabled"] is True
