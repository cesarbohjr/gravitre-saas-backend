"""MKT-AUDIT-14.1: Publisher revenue analytics route."""
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


def test_publisher_analytics_requires_admin():
    _authenticate_admin()
    app.dependency_overrides[require_admin] = _deny_admin
    response = client.get("/api/marketplace/publisher/analytics")
    assert response.status_code == 403


def test_publisher_analytics_route(monkeypatch):
    _authenticate_admin()
    monkeypatch.setattr("app.routers.marketplace.is_platform_admin", lambda *_a, **_k: False)
    monkeypatch.setattr(
        "app.routers.marketplace.get_publisher_revenue_analytics",
        lambda *_a, **_k: {
            "partnerOrgId": ORG_ID,
            "earnings": {
                "combined": {"grossCents": 5000, "partnerEarningsCents": 4000, "transferredCents": 3000},
                "connectorUsage": {"grossCents": 3000, "partnerEarningsCents": 2400},
                "assetSales": {"grossCents": 2000, "partnerEarningsCents": 1600},
            },
            "adoption": {"publishedAssets": 2, "totalInstalls": 10, "usageEventCount": 5, "paidSaleCount": 1},
            "topAssetsByEarnings": [],
            "recentAssetPayouts": [],
            "recentUsageEvents": [],
        },
    )
    response = client.get("/api/marketplace/publisher/analytics")
    assert response.status_code == 200
    body = response.json()
    assert body["partnerOrgId"] == ORG_ID
    assert body["earnings"]["combined"]["partnerEarningsCents"] == 4000
    assert "platformTopAssets" not in body


def test_publisher_analytics_includes_platform_insights_for_platform_admin(monkeypatch):
    _authenticate_admin()
    monkeypatch.setattr("app.routers.marketplace.is_platform_admin", lambda *_a, **_k: True)
    monkeypatch.setattr(
        "app.routers.marketplace.get_publisher_revenue_analytics",
        lambda *_a, include_platform_insights=False, **_k: {
            "partnerOrgId": ORG_ID,
            "earnings": {"combined": {}, "connectorUsage": {}, "assetSales": {}},
            "adoption": {},
            "topAssetsByEarnings": [],
            "recentAssetPayouts": [],
            "recentUsageEvents": [],
            **({"platformTopAssets": [{"assetId": "asset-1"}]} if include_platform_insights else {}),
        },
    )
    response = client.get("/api/marketplace/publisher/analytics")
    assert response.status_code == 200
    assert response.json()["platformTopAssets"][0]["assetId"] == "asset-1"
