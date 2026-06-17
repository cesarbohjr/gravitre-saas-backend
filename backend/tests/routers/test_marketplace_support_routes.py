"""Tests for MKT-5.3 marketplace supporting routes."""
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


def _authenticate(org_id: str = "org-1") -> None:
    app.dependency_overrides[get_current_user] = lambda: {"user_id": "user-1", "email": "u@example.com"}
    app.dependency_overrides[get_org_context] = lambda: org_id
    app.dependency_overrides[get_settings] = lambda: _settings()
    app.dependency_overrides[get_environment_context] = lambda: "production"


def test_list_installs_route(monkeypatch):
    _authenticate()
    monkeypatch.setattr(
        "app.routers.marketplace.list_org_installs",
        lambda *_a, **_k: {
            "installs": [{"id": "install-1", "deepLinks": [{"path": "/workflows/wf-1"}]}],
            "total": 1,
            "limit": 50,
            "offset": 0,
        },
    )
    response = client.get("/api/marketplace/installs")
    assert response.status_code == 200
    assert response.json()["installs"][0]["deepLinks"][0]["path"] == "/workflows/wf-1"


def test_categories_route(monkeypatch):
    _authenticate()
    monkeypatch.setattr(
        "app.routers.marketplace.list_marketplace_categories",
        lambda *_a, **_k: {"categories": [{"key": "ai_agent", "count": 8}], "totalAssets": 27},
    )
    response = client.get("/api/marketplace/categories")
    assert response.status_code == 200
    assert response.json()["totalAssets"] == 27


def test_analytics_summary_route(monkeypatch):
    _authenticate()
    monkeypatch.setattr(
        "app.routers.marketplace.marketplace_analytics_summary",
        lambda *_a, **_k: {"catalog": {"totalAssets": 27}, "org": {"activeInstalls": 0}},
    )
    response = client.get("/api/marketplace/analytics/summary")
    assert response.status_code == 200
    assert response.json()["catalog"]["totalAssets"] == 27


def test_save_and_unsave_routes(monkeypatch):
    _authenticate()
    monkeypatch.setattr(
        "app.routers.marketplace.save_asset",
        lambda *_a, **_k: {"saved": True, "save": {"assetId": "asset-1"}},
    )
    monkeypatch.setattr(
        "app.routers.marketplace.unsave_asset",
        lambda *_a, **_k: {"saved": False, "assetId": "asset-1"},
    )
    save_response = client.post("/api/marketplace/assets/marketing-analyst/save")
    assert save_response.status_code == 201
    unsave_response = client.delete("/api/marketplace/assets/marketing-analyst/save")
    assert unsave_response.status_code == 200


def test_clone_route(monkeypatch):
    _authenticate()
    monkeypatch.setattr(
        "app.routers.marketplace.clone_asset",
        lambda *_a, **_k: {"cloned": True, "asset": {"slug": "marketing-analyst-copy", "status": "draft"}},
    )
    response = client.post("/api/marketplace/assets/marketing-analyst/clone")
    assert response.status_code == 201
    assert response.json()["cloned"] is True


def test_review_upsert_route(monkeypatch):
    _authenticate()
    monkeypatch.setattr(
        "app.routers.marketplace.upsert_my_asset_review",
        lambda *_a, **_k: {"review": {"rating": 5, "title": "Great"}},
    )
    response = client.put(
        "/api/marketplace/assets/marketing-analyst/reviews/mine",
        json={"rating": 5, "title": "Great"},
    )
    assert response.status_code == 200
    assert response.json()["review"]["rating"] == 5
