"""MKT-AUDIT-14.2: Paid asset pricing routes (STA-256)."""
from __future__ import annotations

import pytest
from fastapi import HTTPException, status
from fastapi.testclient import TestClient

from app.auth.dependencies import (
    get_current_user,
    get_environment_context,
    get_org_context,
    require_admin,
    require_platform_admin,
)
from app.config import Settings, get_settings
from app.main import app
from app.marketplace.flags import MarketplaceFlagsError

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


def _authenticate_platform_admin() -> None:
    app.dependency_overrides[get_current_user] = lambda: {"user_id": "platform-1", "email": "admin@gravitre.test"}
    app.dependency_overrides[get_org_context] = lambda: None
    app.dependency_overrides[get_settings] = lambda: _settings()
    app.dependency_overrides[get_environment_context] = lambda: "production"
    app.dependency_overrides[require_platform_admin] = lambda: {"user_id": "platform-1", "email": "admin@gravitre.test"}


def test_org_asset_pricing_requires_admin():
    _authenticate_admin()
    app.dependency_overrides[require_admin] = lambda: (_ for _ in ()).throw(
        HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    )
    response = client.patch(
        "/api/marketplace/assets/sales-pack/pricing",
        json={"pricingType": "paid", "priceCents": 499},
    )
    assert response.status_code == 403


def test_org_asset_pricing_route(monkeypatch):
    _authenticate_admin()
    monkeypatch.setattr(
        "app.routers.marketplace.set_org_asset_pricing",
        lambda *_a, **_k: {"updated": True, "asset": {"slug": "sales-pack", "pricingType": "paid", "priceCents": 499}},
    )
    response = client.patch(
        "/api/marketplace/assets/sales-pack/pricing",
        json={"pricingType": "paid", "priceCents": 499},
    )
    assert response.status_code == 200
    assert response.json()["asset"]["priceCents"] == 499


def test_platform_asset_pricing_route(monkeypatch):
    _authenticate_platform_admin()
    monkeypatch.setattr(
        "app.routers.marketplace.set_asset_pricing",
        lambda *_a, **_k: {"updated": True, "asset": {"slug": "sales-pack", "pricingType": "paid", "priceCents": 999}},
    )
    response = client.patch(
        "/api/marketplace/platform/assets/sales-pack/pricing",
        json={"pricingType": "paid", "priceCents": 999},
    )
    assert response.status_code == 200
    assert response.json()["asset"]["priceCents"] == 999


def test_org_asset_pricing_maps_flags_error(monkeypatch):
    _authenticate_admin()

    def _raise(*_a, **_k):
        raise MarketplaceFlagsError("Pricing can only be updated on draft, pending review, or published public assets")

    monkeypatch.setattr("app.routers.marketplace.set_org_asset_pricing", _raise)
    response = client.patch(
        "/api/marketplace/assets/sales-pack/pricing",
        json={"pricingType": "paid", "priceCents": 499},
    )
    assert response.status_code == 400
