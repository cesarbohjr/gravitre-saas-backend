"""GET /api/capabilities is authenticated, tenant-scoped, and secret-free."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user, get_org_context, require_org_member
from app.config import Settings, get_settings
from app.main import app

client = TestClient(app, raise_server_exceptions=False)


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
    app.dependency_overrides[require_org_member] = lambda: (
        {"user_id": "user-1"},
        org_id,
        "member",
    )


def test_capabilities_requires_auth():
    response = client.get("/api/capabilities")
    assert response.status_code == 401


def test_capabilities_org_scoped_snapshot_has_no_secrets():
    _authenticate("org-tenant-a")
    snapshot = {
        "orgId": "org-tenant-a",
        "mutation": False,
        "governance": {"writeRequiresApprovalByDefault": True, "noHitlPolicyMeans": "ACT WITH APPROVAL"},
        "agents": [{"id": "a1", "name": "Rescue"}],
        "orgConnectors": [{"id": "c1", "vendor": "hubspot", "status": "connected"}],
        "actions": [{"tool": "hubspot.contacts.search", "access": "read"}],
        "sources": {},
    }
    with patch("app.routers.capabilities.get_supabase_client", return_value=MagicMock()):
        with patch(
            "app.routers.capabilities.tenant_capability_snapshot",
            return_value=snapshot,
        ) as snap:
            response = client.get("/api/capabilities", headers={"x-org-id": "org-tenant-a"})
    assert response.status_code == 200
    body = response.json()
    assert body["orgId"] == "org-tenant-a"
    assert snap.call_args.args[1] == "org-tenant-a"
    blob = json.dumps(body).lower()
    assert "access_token" not in blob
    assert "refresh_token" not in blob
    assert "service-role-test" not in blob


def test_capabilities_does_not_refresh_tokens():
    _authenticate()
    with patch("app.routers.capabilities.get_supabase_client", return_value=MagicMock()):
        with patch(
            "app.routers.capabilities.tenant_capability_snapshot",
            return_value={"orgId": "org-1", "mutation": False},
        ):
            with patch(
                "app.connectors.hubspot_oauth.ensure_hubspot_access_token",
            ) as refresh:
                response = client.get("/api/capabilities")
    assert response.status_code == 200
    assert refresh.call_count == 0
