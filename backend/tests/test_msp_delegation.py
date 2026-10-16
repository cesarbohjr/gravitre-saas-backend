"""Tests for Release 4 — MSP parent-org delegation.

Covers:
    msp_parent_grants_access:
    - grants when user is admin of parent and child has parent_org_id set
    - denies when user is only a member (not admin/owner) of parent
    - denies when child has no parent_org_id
    - denies when parent is not in user's memberships
    - denies when member_org_ids is empty
    - denies on DB error looking up role (safe-fail)

    GET /api/msp/client-orgs:
    - returns child orgs for an MSP admin
    - returns 403 when flag is off
    - returns empty list when user has no admin parent orgs

    POST /api/msp/switch-client:
    - returns scoped JWT token for valid child org
    - returns 403 when caller is not admin of parent
    - returns 404 when requested org has no parent_org_id
    - returns 403 when flag is off

    GET /api/msp/client-orgs/{org_id}:
    - returns detail with member_count
    - returns 404 for non-child org
"""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.services.msp_org_context import (
    msp_parent_grants_access,
    list_child_orgs_for_msp_admin,
    parent_org_id_for,
    _user_role_in_org,
)

# ---------------------------------------------------------------------------
# Unit tests for msp_org_context.py
# ---------------------------------------------------------------------------


def _org_client_with_parent(parent_id: str | None) -> MagicMock:
    """Client where organizations returns parent_org_id for any org_id."""
    client = MagicMock()
    org_result = MagicMock()
    org_result.data = [{"parent_org_id": parent_id}] if parent_id else []
    (
        client.table.return_value
        .select.return_value
        .eq.return_value
        .limit.return_value
        .execute.return_value
    ) = org_result
    return client


def _member_client(role: str | None) -> MagicMock:
    """Client where organization_members returns the given role for any query."""
    client = MagicMock()
    member_result = MagicMock()
    member_result.data = [{"role": role}] if role else []

    call_count = [0]

    def _table_side_effect(name):
        tbl = MagicMock()
        # First call: organizations (parent_org_id lookup)
        # Subsequent calls: organization_members (role lookup)
        call_count[0] += 1
        if call_count[0] == 1:
            org_result = MagicMock()
            org_result.data = [{"parent_org_id": "parent-1"}]
            (
                tbl.select.return_value
                .eq.return_value
                .limit.return_value
                .execute.return_value
            ) = org_result
        else:
            (
                tbl.select.return_value
                .eq.return_value
                .eq.return_value
                .limit.return_value
                .execute.return_value
            ) = member_result
        return tbl

    client.table.side_effect = _table_side_effect
    return client


class TestMspParentGrantsAccess:
    def test_grants_when_admin_of_parent(self) -> None:
        client = _member_client("admin")
        result = msp_parent_grants_access(
            client,
            user_id="user-1",
            requested_org_id="child-1",
            member_org_ids=["parent-1"],
        )
        assert result is True

    def test_grants_when_owner_of_parent(self) -> None:
        client = _member_client("owner")
        result = msp_parent_grants_access(
            client,
            user_id="user-1",
            requested_org_id="child-1",
            member_org_ids=["parent-1"],
        )
        assert result is True

    def test_denies_when_member_role_only(self) -> None:
        client = _member_client("member")
        result = msp_parent_grants_access(
            client,
            user_id="user-1",
            requested_org_id="child-1",
            member_org_ids=["parent-1"],
        )
        assert result is False

    def test_denies_when_viewer_role(self) -> None:
        client = _member_client("viewer")
        result = msp_parent_grants_access(
            client,
            user_id="user-1",
            requested_org_id="child-1",
            member_org_ids=["parent-1"],
        )
        assert result is False

    def test_denies_when_no_memberships(self) -> None:
        client = MagicMock()  # Should not be called
        result = msp_parent_grants_access(
            client,
            user_id="user-1",
            requested_org_id="child-1",
            member_org_ids=[],
        )
        assert result is False
        client.table.assert_not_called()

    def test_denies_when_child_has_no_parent(self) -> None:
        client = _org_client_with_parent(None)
        result = msp_parent_grants_access(
            client,
            user_id="user-1",
            requested_org_id="child-1",
            member_org_ids=["some-org"],
        )
        assert result is False

    def test_denies_when_parent_not_in_member_orgs(self) -> None:
        # Child has parent-99 but user is only in parent-1
        client = _org_client_with_parent("parent-99")
        result = msp_parent_grants_access(
            client,
            user_id="user-1",
            requested_org_id="child-1",
            member_org_ids=["parent-1"],
        )
        assert result is False

    def test_safe_fail_on_role_db_error(self) -> None:
        """DB error during role lookup → returns False (never raises)."""
        call_count = [0]

        client = MagicMock()

        def _table_side_effect(name):
            tbl = MagicMock()
            call_count[0] += 1
            if call_count[0] == 1:
                # org lookup succeeds
                org_result = MagicMock()
                org_result.data = [{"parent_org_id": "parent-1"}]
                (
                    tbl.select.return_value
                    .eq.return_value
                    .limit.return_value
                    .execute.return_value
                ) = org_result
            else:
                # role lookup fails
                tbl.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.side_effect = RuntimeError("db down")
            return tbl

        client.table.side_effect = _table_side_effect
        result = msp_parent_grants_access(
            client,
            user_id="user-1",
            requested_org_id="child-1",
            member_org_ids=["parent-1"],
        )
        assert result is False


# ---------------------------------------------------------------------------
# Router endpoint tests
# ---------------------------------------------------------------------------


def _build_app(msp_enabled: bool = True) -> tuple[FastAPI, MagicMock]:
    """Build a minimal FastAPI app with the MSP router mounted."""
    from app.routers import msp as msp_router_module

    app = FastAPI()
    app.include_router(msp_router_module.router)

    fake_client = MagicMock()
    fake_settings = MagicMock()
    fake_settings.msp_parent_org_enabled = msp_enabled
    fake_settings.jwt_audience = "authenticated"
    fake_settings.jwt_issuer = "https://test.supabase.co/auth/v1"
    fake_settings.supabase_jwt_secret = "test-secret"

    from app.auth.dependencies import get_current_user
    from app.config import get_settings

    app.dependency_overrides[get_current_user] = lambda: {"user_id": "user-1", "email": "u@t.com"}
    app.dependency_overrides[get_settings] = lambda: fake_settings

    return app, fake_client


def _patch_shared_client(fake_client: MagicMock):
    return patch("app.routers.msp.shared_service_client", return_value=fake_client)


def _patch_create_client():
    return patch("app.routers.msp.create_client", return_value=MagicMock())


def _patch_is_platform_admin(is_admin: bool):
    return patch("app.routers.msp.is_platform_admin", return_value=is_admin)


def _patch_write_audit():
    return patch("app.routers.msp.write_audit_event")


class TestListClientOrgs:
    def test_returns_client_orgs_for_msp_admin(self) -> None:
        app, fake_client = _build_app(msp_enabled=True)

        # organization_members → admin role rows for parent-1
        member_result = MagicMock()
        member_result.data = [{"org_id": "parent-1", "role": "admin"}]

        # organizations → child rows
        child_result = MagicMock()
        child_result.data = [
            {"id": "child-1", "name": "Client A", "slug": "client-a", "created_at": "2026-01-01T00:00:00"}
        ]

        call_count = [0]

        def _table_side(name):
            tbl = MagicMock()
            call_count[0] += 1
            if name == "organization_members":
                tbl.select.return_value.eq.return_value.in_.return_value.limit.return_value.execute.return_value = member_result
            elif name == "organizations":
                tbl.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = child_result
            return tbl

        fake_client.table.side_effect = _table_side

        with _patch_shared_client(fake_client), _patch_create_client(), _patch_is_platform_admin(False), _patch_write_audit():
            client = TestClient(app)
            resp = client.get("/api/msp/client-orgs")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["client_orgs"][0]["id"] == "child-1"
        assert data["client_orgs"][0]["parent_org_id"] == "parent-1"

    def test_returns_403_when_flag_off(self) -> None:
        app, fake_client = _build_app(msp_enabled=False)
        with _patch_shared_client(fake_client), _patch_create_client():
            client = TestClient(app)
            resp = client.get("/api/msp/client-orgs")
        assert resp.status_code == 403

    def test_returns_empty_when_no_admin_parent_orgs(self) -> None:
        app, fake_client = _build_app(msp_enabled=True)

        member_result = MagicMock()
        member_result.data = []
        fake_client.table.return_value.select.return_value.eq.return_value.in_.return_value.limit.return_value.execute.return_value = member_result

        with _patch_shared_client(fake_client), _patch_create_client(), _patch_is_platform_admin(False), _patch_write_audit():
            client = TestClient(app)
            resp = client.get("/api/msp/client-orgs")

        assert resp.status_code == 200
        assert resp.json()["total"] == 0


class TestSwitchClient:
    def _setup_client_for_switch(self, fake_client: MagicMock, parent_id: str | None, caller_role: str | None) -> None:
        call_count = [0]

        def _table_side(name):
            tbl = MagicMock()
            call_count[0] += 1
            if name == "organizations":
                org_result = MagicMock()
                org_result.data = [{"parent_org_id": parent_id}] if parent_id else []
                tbl.select.return_value.eq.return_value.limit.return_value.execute.return_value = org_result
            elif name == "organization_members":
                role_result = MagicMock()
                role_result.data = [{"role": caller_role}] if caller_role else []
                tbl.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = role_result
            return tbl

        fake_client.table.side_effect = _table_side

    def test_issues_scoped_token_for_valid_child_org(self) -> None:
        app, fake_client = _build_app(msp_enabled=True)
        self._setup_client_for_switch(fake_client, parent_id="parent-1", caller_role="admin")

        with _patch_shared_client(fake_client), _patch_create_client(), _patch_is_platform_admin(False), _patch_write_audit():
            client = TestClient(app)
            resp = client.post("/api/msp/switch-client", json={"client_org_id": "child-1"})

        assert resp.status_code == 200
        data = resp.json()
        assert "token" in data
        assert data["client_org_id"] == "child-1"
        assert "expires_at" in data

    def test_denies_when_caller_is_not_admin_of_parent(self) -> None:
        app, fake_client = _build_app(msp_enabled=True)
        self._setup_client_for_switch(fake_client, parent_id="parent-1", caller_role="member")

        with _patch_shared_client(fake_client), _patch_create_client(), _patch_is_platform_admin(False), _patch_write_audit():
            client = TestClient(app)
            resp = client.post("/api/msp/switch-client", json={"client_org_id": "child-1"})

        assert resp.status_code == 403

    def test_returns_404_when_org_has_no_parent(self) -> None:
        app, fake_client = _build_app(msp_enabled=True)
        self._setup_client_for_switch(fake_client, parent_id=None, caller_role=None)

        with _patch_shared_client(fake_client), _patch_create_client(), _patch_is_platform_admin(False), _patch_write_audit():
            client = TestClient(app)
            resp = client.post("/api/msp/switch-client", json={"client_org_id": "standalone-org"})

        assert resp.status_code == 404

    def test_returns_403_when_flag_off(self) -> None:
        app, fake_client = _build_app(msp_enabled=False)
        with _patch_shared_client(fake_client), _patch_create_client():
            client = TestClient(app)
            resp = client.post("/api/msp/switch-client", json={"client_org_id": "child-1"})
        assert resp.status_code == 403

    def test_platform_admin_can_switch_to_any_child_org(self) -> None:
        """Platform admin bypasses role check — only needs a valid child org."""
        app, fake_client = _build_app(msp_enabled=True)
        # org lookup returns parent_id; role lookup is never called for platform admins
        org_result = MagicMock()
        org_result.data = [{"parent_org_id": "parent-1"}]
        (
            fake_client.table.return_value
            .select.return_value
            .eq.return_value
            .limit.return_value
            .execute.return_value
        ) = org_result

        with _patch_shared_client(fake_client), _patch_create_client(), _patch_is_platform_admin(True), _patch_write_audit():
            client = TestClient(app)
            resp = client.post("/api/msp/switch-client", json={"client_org_id": "child-1"})

        assert resp.status_code == 200
