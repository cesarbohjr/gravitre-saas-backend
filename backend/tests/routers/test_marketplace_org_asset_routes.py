"""MKT-AUDIT-9.1 / 9.2: Org asset CRUD and internal publish routes."""
from __future__ import annotations

import pytest
from fastapi import HTTPException, status
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user, get_environment_context, get_org_context, require_admin
from app.config import Settings, get_settings
from app.main import app
from app.workflows.constants import SCHEMA_VERSION

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


def _authenticate(org_id: str = ORG_ID, *, admin: bool = False) -> None:
    app.dependency_overrides[get_current_user] = lambda: {"user_id": "user-1", "email": "u@example.com"}
    app.dependency_overrides[get_org_context] = lambda: org_id
    app.dependency_overrides[get_settings] = lambda: _settings()
    app.dependency_overrides[get_environment_context] = lambda: "production"
    if admin:
        app.dependency_overrides[require_admin] = lambda: ({"user_id": "user-1"}, org_id)


def _draft_asset(**overrides) -> dict:
    base = {
        "id": "asset-1",
        "slug": "custom-agent",
        "title": "Custom Agent",
        "assetType": "ai_agent",
        "status": "draft",
        "visibility": "private",
        "orgId": ORG_ID,
        "config": {
            "name": "Custom Agent",
            "purpose": "Analyze campaigns",
            "role": "Analyst",
            "department": "Marketing",
            "systems": [],
        },
    }
    base.update(overrides)
    return base


def _deny_admin() -> tuple[dict, str]:
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")


def test_create_asset_requires_admin():
    _authenticate(admin=False)
    app.dependency_overrides[require_admin] = _deny_admin
    response = client.post(
        "/api/marketplace/assets",
        json={
            "slug": "custom-agent",
            "title": "Custom Agent",
            "assetType": "ai_agent",
            "config": {"name": "Custom Agent", "purpose": "x", "role": "Analyst", "systems": []},
        },
    )
    assert response.status_code == 403


def test_create_asset_as_admin(monkeypatch):
    _authenticate(admin=True)
    created = {"created": True, "asset": _draft_asset()}
    monkeypatch.setattr("app.routers.marketplace.create_org_asset", lambda *_a, **_k: created)
    response = client.post(
        "/api/marketplace/assets",
        json={
            "slug": "custom-agent",
            "title": "Custom Agent",
            "assetType": "ai_agent",
            "config": {
                "name": "Custom Agent",
                "purpose": "Analyze campaigns",
                "role": "Analyst",
                "department": "Marketing",
                "systems": [],
            },
        },
    )
    assert response.status_code == 201
    assert response.json()["asset"]["status"] == "draft"


def test_patch_asset_rejects_non_admin():
    _authenticate(admin=False)
    app.dependency_overrides[require_admin] = _deny_admin
    response = client.patch(
        "/api/marketplace/assets/custom-agent",
        json={"title": "Updated"},
    )
    assert response.status_code == 403


def test_archive_asset_route(monkeypatch):
    _authenticate(admin=True)
    archived = {"archived": True, "asset": _draft_asset(status="archived")}
    monkeypatch.setattr("app.routers.marketplace.archive_org_asset", lambda *_a, **_k: archived)
    response = client.delete("/api/marketplace/assets/custom-agent")
    assert response.status_code == 200
    assert response.json()["archived"] is True


def test_submit_for_review_route(monkeypatch):
    _authenticate(admin=True)
    submitted = {"submitted": True, "asset": _draft_asset(status="pending_review")}
    monkeypatch.setattr("app.routers.marketplace.submit_asset_for_review", lambda *_a, **_k: submitted)
    response = client.post("/api/marketplace/assets/custom-agent/submit-for-review")
    assert response.status_code == 200
    assert response.json()["asset"]["status"] == "pending_review"


def test_approve_internal_publish_route(monkeypatch):
    _authenticate(admin=True)
    approved = {
        "approved": True,
        "asset": _draft_asset(status="published", visibility="internal"),
    }
    monkeypatch.setattr(
        "app.routers.marketplace.approve_asset_for_internal_publish",
        lambda *_a, **_k: approved,
    )
    response = client.post("/api/marketplace/assets/custom-agent/approve")
    assert response.status_code == 200
    assert response.json()["asset"]["visibility"] == "internal"


def test_reject_review_route(monkeypatch):
    _authenticate(admin=True)
    rejected = {
        "rejected": True,
        "reason": "Needs clearer business outcome",
        "asset": _draft_asset(status="draft"),
    }
    monkeypatch.setattr("app.routers.marketplace.reject_asset_review", lambda *_a, **_k: rejected)
    response = client.post(
        "/api/marketplace/assets/custom-agent/reject",
        json={"reason": "Needs clearer business outcome"},
    )
    assert response.status_code == 200
    assert response.json()["asset"]["status"] == "draft"


def test_list_org_assets_route(monkeypatch):
    _authenticate(admin=True)
    listing = {
        "assets": [_draft_asset(status="pending_review")],
        "total": 1,
        "limit": 50,
        "offset": 0,
    }
    monkeypatch.setattr("app.routers.marketplace.list_org_assets", lambda *_a, **_k: listing)
    response = client.get("/api/marketplace/org/assets?status=pending_review")
    assert response.status_code == 200
    assert response.json()["assets"][0]["status"] == "pending_review"
