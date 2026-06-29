"""Cross-tier route guard tests for Control/Command-exclusive features."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user, get_org_context, require_admin
from app.config import Settings, get_settings
from app.main import app
from app.middleware.entitlements import get_entitlements_dependency, resolve_entitlements
from app.services.meson_service import MesonGeneratedConfig, MesonInterpretResult, MesonService, get_meson_service

client = TestClient(app)


def _settings() -> Settings:
    return Settings(
        app_env="dev",
        supabase_url="https://test.supabase.co",
        supabase_anon_key="anon-test",
        supabase_service_role_key="service-role-test",
        supabase_jwt_secret="jwt-secret-test",
    )


def _authenticate(org_id: str = "org-node") -> None:
    app.dependency_overrides[get_current_user] = lambda: {"user_id": "user-1", "email": "u@example.com"}
    app.dependency_overrides[get_org_context] = lambda: org_id
    app.dependency_overrides[get_settings] = lambda: _settings()
    app.dependency_overrides[require_admin] = lambda: ({"user_id": "user-1"}, org_id)


def _entitlements(tier: str) -> dict:
    from app.middleware.entitlements import TIER_FEATURES, TIER_LIMITS

    return {
        "tier": tier,
        "status": "active",
        "seat_count": 1,
        "lite_seats": 0,
        "limits": dict(TIER_LIMITS[tier]),
        "features": dict(TIER_FEATURES[tier]),
        "addons": [],
        "usage": {},
    }


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


FEDERATION_ROUTES = [
    ("GET", "/api/federation/partnerships"),
    ("POST", "/api/federation/partnerships"),
    ("GET", "/api/federation/handoffs"),
    ("POST", "/api/federation/handoffs"),
    ("GET", "/api/federation/connector-grants"),
    ("POST", "/api/federation/connector-grants"),
    ("GET", "/api/federation/delegated-tasks"),
    ("POST", "/api/federation/delegated-tasks"),
]

MESON_ROUTES = [
    ("POST", "/api/meson/interpret"),
    ("POST", "/api/meson/deploy"),
    ("GET", "/api/meson/alerts"),
    ("GET", "/api/meson/insights"),
]


@pytest.mark.parametrize("method,path", FEDERATION_ROUTES)
def test_node_tier_blocked_from_federation_route(method: str, path: str):
    _authenticate()
    app.dependency_overrides[get_entitlements_dependency] = lambda: _entitlements("node")
    response = client.request(method, path, json={})
    assert response.status_code == 403


@pytest.mark.parametrize("method,path", MESON_ROUTES)
def test_node_tier_blocked_from_meson_route(method: str, path: str):
    _authenticate()
    app.dependency_overrides[get_entitlements_dependency] = lambda: _entitlements("node")
    body = {"intent": "Build sales automation", "department": "sales"} if method == "POST" else None
    response = client.request(method, path, json=body)
    assert response.status_code == 403


def test_node_tier_blocked_via_direct_api_call_not_just_ui():
    _authenticate()
    app.dependency_overrides[get_entitlements_dependency] = lambda: _entitlements("node")
    response = client.get("/api/federation/partnerships")
    assert response.status_code == 403
    payload = response.json()
    assert payload.get("code") == "UNAUTHORIZED" or "Upgrade" in str(payload.get("error", ""))


def test_command_tier_can_access_federation_route(monkeypatch):
    _authenticate()
    app.dependency_overrides[get_entitlements_dependency] = lambda: _entitlements("command")
    monkeypatch.setattr(
        "app.routers.federation.list_partnerships",
        lambda client, org_id: [],
    )
    monkeypatch.setattr(
        "app.routers.federation._client",
        lambda settings: MagicMock(),
    )
    response = client.get("/api/federation/partnerships")
    assert response.status_code == 200


def test_control_tier_can_access_meson_route():
    _authenticate()
    app.dependency_overrides[get_entitlements_dependency] = lambda: _entitlements("control")
    mock = MagicMock(spec=MesonService)
    mock.interpret_build_request = AsyncMock(
        return_value=MesonInterpretResult(
            intent="test",
            department="sales",
            systems=[],
            outputTypes=["workflows"],
            generatedConfig=MesonGeneratedConfig(
                agent="Agent",
                agent_role="Role",
                agent_description="Desc",
                training=[],
                workflows=[],
                sample_outputs=[],
            ),
            confidence=0.5,
            explanation="ok",
        )
    )
    app.dependency_overrides[get_meson_service] = lambda: mock
    response = client.post(
        "/api/meson/interpret",
        json={"intent": "Build sales automation", "department": "sales"},
    )
    assert response.status_code == 200
