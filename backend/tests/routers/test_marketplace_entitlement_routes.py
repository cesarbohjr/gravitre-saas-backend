"""MKT-AUDIT-12.1: Paid install entitlement and checkout routes."""
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
        stripe_secret_key="sk_test",
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


def test_asset_entitlement_route(monkeypatch):
    _authenticate_admin()
    monkeypatch.setattr(
        "app.routers.marketplace.fetch_marketplace_asset",
        lambda *_a, **_k: {
            "id": "asset-1",
            "org_id": "publisher-org",
            "pricing_type": "paid",
            "price_cents": 2500,
            "currency": "usd",
        },
    )
    monkeypatch.setattr(
        "app.routers.marketplace.get_entitlement_status",
        lambda *_a, **_k: {
            "requiresPayment": True,
            "hasEntitlement": False,
            "pricingType": "paid",
            "priceCents": 2500,
            "currency": "usd",
        },
    )
    response = client.get("/api/marketplace/assets/paid-pack/entitlement")
    assert response.status_code == 200
    assert response.json()["requiresPayment"] is True


def test_asset_checkout_requires_admin():
    _authenticate_admin()
    app.dependency_overrides[require_admin] = _deny_admin
    response = client.post(
        "/api/marketplace/assets/paid-pack/checkout",
        json={
            "successUrl": "https://app/success",
            "cancelUrl": "https://app/cancel",
        },
    )
    assert response.status_code == 403


def test_asset_checkout_route(monkeypatch):
    _authenticate_admin()
    monkeypatch.setattr(
        "app.routers.marketplace.create_asset_checkout_session",
        lambda *_a, **_k: {
            "checkoutUrl": "https://checkout.stripe.test/session",
            "sessionId": "cs_test",
            "entitlementId": "ent-1",
            "mode": "payment",
        },
    )
    monkeypatch.setattr("app.routers.marketplace.write_audit_event", lambda *_a, **_k: None)
    response = client.post(
        "/api/marketplace/assets/paid-pack/checkout",
        json={
            "successUrl": "https://app/success",
            "cancelUrl": "https://app/cancel",
        },
    )
    assert response.status_code == 200
    assert response.json()["checkoutUrl"].startswith("https://checkout")


def test_install_check_includes_payment_fields(monkeypatch):
    _authenticate_admin()
    monkeypatch.setattr(
        "app.routers.marketplace.preview_install",
        lambda *_a, **_k: {
            "canInstall": False,
            "requiresPayment": True,
            "hasEntitlement": False,
            "priceCents": 9900,
            "blockers": [{"connector": "payment", "reason": "Purchase required before install"}],
            "connectorChecklist": [],
        },
    )
    response = client.get("/api/marketplace/assets/paid-pack/install-check")
    assert response.status_code == 200
    body = response.json()
    assert body["requiresPayment"] is True
    assert body["hasEntitlement"] is False
