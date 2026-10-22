"""Every registered Play must fail closed before the canonical write gate.

These are isolated API governance tests, NOT synthetic successful workflow execution.
No live provider, customer, or production write is used.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.auth.dependencies import (
    get_current_user, get_environment_context, get_org_context, require_org_member,
)
from app.config import Settings, get_settings
from app.main import app
from app.plays.catalog import platform_play_templates


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    app.dependency_overrides.clear()


def auth():
    app.dependency_overrides[get_current_user] = lambda: {
        "user_id": "synthetic-user", "email": "synthetic@example.invalid",
    }
    app.dependency_overrides[get_org_context] = lambda: "synthetic-org"
    app.dependency_overrides[get_environment_context] = lambda: "production"
    app.dependency_overrides[require_org_member] = lambda: (
        {"user_id": "synthetic-user"}, "synthetic-org", "member",
    )
    app.dependency_overrides[get_settings] = lambda: Settings(
        app_env="dev",
        supabase_url="https://test.supabase.co",
        supabase_anon_key="anon-test",
        supabase_service_role_key="service-role-test",
        supabase_jwt_secret="jwt-secret-test",
    )


@pytest.mark.parametrize("play_key", [p.key for p in platform_play_templates()])
def test_every_play_observe_blocks_run_before_external_write(play_key):
    auth()
    with patch("app.routers.plays.get_supabase_client") as database, patch(
        "app.routers.plays._load_installation",
        return_value={"id": "synthetic-install", "operating_mode": "OBSERVE", "status": "ready"},
    ):
        response = TestClient(app, raise_server_exceptions=False).post(
            f"/api/plays/{play_key}/runs",
            json={"installationId": "synthetic-install"},
        )
    assert response.status_code == 409, (play_key, response.status_code, response.text)
    assert "does not permit external actions" in response.json()["detail"]
    # A client may be obtained for the installation lookup, but no mutation
    # should be issued to the database or provider.
    assert not database.return_value.table.called, play_key


@pytest.mark.parametrize("play_key", [p.key for p in platform_play_templates()])
def test_every_play_act_within_policy_blocks_unearned_authority(play_key):
    auth()
    ready = MagicMock(act_with_approval_ready=True)
    with patch("app.routers.plays.get_supabase_client") as database, patch(
        "app.routers.plays._load_installation",
        return_value={"id": "synthetic-install", "operating_mode": "ACT WITHIN POLICY", "status": "ready"},
    ), patch("app.routers.plays.connected_vendors", return_value=set()), patch(
        "app.routers.plays.resolve_play_readiness", return_value=ready,
    ):
        response = TestClient(app, raise_server_exceptions=False).post(
            f"/api/plays/{play_key}/runs",
            json={"installationId": "synthetic-install"},
        )
    assert response.status_code == 409, (play_key, response.status_code, response.text)
    assert "effective runtime action authorization" in response.json()["detail"]
    assert not database.return_value.table.called, play_key
