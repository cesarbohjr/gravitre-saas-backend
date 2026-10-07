"""Read-only Plays API contract tests."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.auth.dependencies import (
    get_current_user,
    get_environment_context,
    get_org_context,
    require_org_member,
)
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


def _auth(org_id: str = "org-1") -> None:
    app.dependency_overrides[get_current_user] = lambda: {
        "user_id": "user-1",
        "email": "user@example.com",
    }
    app.dependency_overrides[get_org_context] = lambda: org_id
    app.dependency_overrides[get_environment_context] = lambda: "production"
    app.dependency_overrides[get_settings] = lambda: _settings()
    app.dependency_overrides[require_org_member] = lambda: (
        {"user_id": "user-1"},
        org_id,
        "member",
    )


def test_plays_requires_auth():
    response = client.get("/api/plays")
    assert response.status_code == 401


def test_plays_list_is_read_only_and_fail_closed_for_policy():
    _auth()
    fake_client = MagicMock()
    with patch("app.routers.plays.get_supabase_client", return_value=fake_client),          patch("app.routers.plays.connected_vendors", return_value={"hubspot", "quickbooks"}),          patch("app.routers.plays.list_play_workflow_bindings", return_value=[]),          patch("app.routers.plays.resolve_play_readiness") as ready:
        ready.return_value.as_dict.return_value = {
            "play_key": "x",
            "dependency_status": "AVAILABLE",
            "observe_ready": True,
            "recommend_ready": True,
            "act_with_approval_ready": True,
            "act_within_policy_ready": False,
            "blockers": [],
        }
        response = client.get("/api/plays")
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == len(body["plays"])
    assert body["count"] >= 9
    assert body["executionAuthority"] == "canonical_workflow_runtime"
    assert all(item["play"]["executable"] is False for item in body["plays"])
    assert all(item["readiness"]["act_within_policy_ready"] is False for item in body["plays"])
    assert "effective runtime policy" in body["policyNote"]


def test_revenue_recovery_observe_never_claims_action_or_recovered_revenue():
    _auth()
    fake_client = MagicMock()
    with patch("app.routers.plays.get_supabase_client", return_value=fake_client),          patch("app.routers.plays.connected_vendors", return_value={"quickbooks"}),          patch("app.routers.plays.resolve_play_readiness") as ready,          patch("app.routers.plays.list_revenue_recovery_signals", return_value=[]):
        ready.return_value.as_dict.return_value = {
            "play_key": "revenue-recovery",
            "dependency_status": "AVAILABLE",
            "observe_ready": True,
            "recommend_ready": True,
            "act_with_approval_ready": False,
            "act_within_policy_ready": False,
            "blockers": [],
        }
        response = client.get("/api/plays/revenue-recovery/observe")
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "OBSERVE"
    assert body["actionTaken"] is False
    assert body["verifiedRecoveredRevenue"] is None
    assert "source-of-record verification" in body["truthRule"]


def test_play_outcomes_are_org_scoped():
    _auth("org-tenant-a")
    fake_client = MagicMock()
    with patch("app.routers.plays.get_supabase_client", return_value=fake_client),          patch("app.routers.plays.list_play_business_results", return_value=[]) as listing:
        response = client.get("/api/plays/revenue-recovery/outcomes")
    assert response.status_code == 200
    listing.assert_called_once()
    assert listing.call_args.args[1] == "org-tenant-a"
    assert response.json()["outcomes"] == []


def test_play_impact_is_org_scoped():
    _auth("org-tenant-b")
    with patch("app.routers.plays.get_supabase_client", return_value="client"), patch(
        "app.routers.plays.play_impact_summary",
        return_value={
            "plays": [],
            "verifiedResultCount": 0,
            "pendingVerificationCount": 0,
            "verifiedMetrics": [],
            "truthRule": "Only source-of-record VERIFIED SUCCESS results contribute to verified impact totals.",
        },
    ) as summary:
        response = client.get("/api/plays/impact")
    assert response.status_code == 200
    summary.assert_called_once_with("client", "org-tenant-b", range_key=None)
    assert "VERIFIED SUCCESS" in response.json()["truthRule"]


def test_installation_read_is_org_scoped():
    _auth("org-tenant-a")
    fake_client = MagicMock()
    query = fake_client.table.return_value.select.return_value
    query.eq.return_value = query
    query.limit.return_value.execute.return_value.data = []
    with patch("app.routers.plays.get_supabase_client", return_value=fake_client):
        response = client.get("/api/plays/customer-rescue/installation")
    assert response.status_code == 200
    fake_client.table.assert_called_with("play_installations")
    org_filters = [call.args for call in query.eq.call_args_list]
    assert ("org_id", "org-tenant-a") in org_filters
    assert response.json()["installation"] is None


def test_installation_put_rejects_unearned_act_within_policy():
    _auth()
    ready = MagicMock(
        observe_ready=True,
        recommend_ready=True,
        act_with_approval_ready=True,
        act_within_policy_ready=False,
    )
    with patch("app.routers.plays.get_supabase_client"), patch(
        "app.routers.plays._resolve_current_readiness",
        return_value=ready,
    ):
        response = client.put(
            "/api/plays/customer-rescue/installation",
            json={"playVersion": "1.0.0", "operatingMode": "ACT WITHIN POLICY"},
        )
    assert response.status_code == 409
    assert "effective runtime action authorization" in response.json()["detail"] or "has not earned" in response.json()["detail"]


def test_observe_mode_cannot_start_a_play_run():
    _auth()
    with patch("app.routers.plays.get_supabase_client"), patch(
        "app.routers.plays._load_installation",
        return_value={"id": "inst-1", "operating_mode": "OBSERVE", "status": "ready"},
    ):
        response = client.post(
            "/api/plays/customer-rescue/runs",
            json={"installationId": "inst-1"},
        )
    assert response.status_code == 409
    assert "does not permit external actions" in response.json()["detail"]


def test_act_within_policy_run_fails_closed():
    _auth()
    ready = MagicMock(act_with_approval_ready=True)
    with patch("app.routers.plays.get_supabase_client"), patch(
        "app.routers.plays._load_installation",
        return_value={"id": "inst-1", "operating_mode": "ACT WITHIN POLICY", "status": "ready"},
    ), patch("app.routers.plays.connected_vendors", return_value=set()), patch(
        "app.routers.plays.resolve_play_readiness",
        return_value=ready,
    ):
        response = client.post(
            "/api/plays/customer-rescue/runs",
            json={"installationId": "inst-1"},
        )
    assert response.status_code == 409
    assert "effective runtime action authorization" in response.json()["detail"]
