"""MKT-AUDIT-13.2: Strategic hours saved ROI dashboard route."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user, get_environment_context, get_org_context
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


def _authenticate_org_user() -> None:
    app.dependency_overrides[get_current_user] = lambda: {"user_id": "user-1", "email": "user@test.com"}
    app.dependency_overrides[get_org_context] = lambda: "org-1"
    app.dependency_overrides[get_settings] = lambda: _settings()
    app.dependency_overrides[get_environment_context] = lambda: "production"


def test_analytics_roi_requires_org_context():
    app.dependency_overrides[get_current_user] = lambda: {"user_id": "user-1", "email": "user@test.com"}
    app.dependency_overrides[get_org_context] = lambda: None
    app.dependency_overrides[get_settings] = lambda: _settings()
    response = client.get("/api/marketplace/analytics/roi")
    assert response.status_code == 403


def test_analytics_roi_route(monkeypatch):
    _authenticate_org_user()
    monkeypatch.setattr(
        "app.routers.marketplace.marketplace_roi_summary",
        lambda *_a, **_k: {
            "orgId": "org-1",
            "activeInstalls": 2,
            "assetsWithUsage": 1,
            "totalUsageEvents": 3,
            "totalEstimatedHoursSaved": 8.0,
            "totalRealizedHoursSaved": 5.0,
            "realizationRate": 62.5,
            "byAsset": [{"installId": "install-1", "estimatedHoursSaved": 5.0, "realizedHoursSaved": 5.0, "usageEvents": 3}],
        },
    )
    response = client.get("/api/marketplace/analytics/roi?limit=10")
    assert response.status_code == 200
    body = response.json()
    assert body["activeInstalls"] == 2
    assert body["realizationRate"] == 62.5
    assert len(body["byAsset"]) == 1
