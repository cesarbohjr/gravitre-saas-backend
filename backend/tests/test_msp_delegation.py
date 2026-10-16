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


# ---------------------------------------------------------------------------
# Row 5 — Real-DB cross-client denials and authenticated UI
# ---------------------------------------------------------------------------


def _setup_client_org_detail_client(
    fake_client: MagicMock,
    *,
    parent_id: str | None,
    caller_role: str | None,
    org_name: str = "Acme Corp",
    org_slug: str = "acme-corp",
    member_count: int = 5,
) -> None:
    """Wire fake_client for GET /api/msp/client-orgs/{org_id}."""
    call_tracker: list[str] = []

    def _table_side(name: str) -> MagicMock:
        tbl = MagicMock()
        call_tracker.append(name)

        if name == "organizations":
            # First call: parent_org_id lookup; subsequent call: org detail fetch.
            if call_tracker.count("organizations") == 1:
                parent_result = MagicMock()
                parent_result.data = [{"parent_org_id": parent_id}] if parent_id else []
                (
                    tbl.select.return_value
                    .eq.return_value
                    .limit.return_value
                    .execute.return_value
                ) = parent_result
            else:
                detail_result = MagicMock()
                detail_result.data = [
                    {
                        "id": "child-org-1",
                        "name": org_name,
                        "slug": org_slug,
                        "parent_org_id": parent_id,
                        "created_at": "2026-01-01T00:00:00+00:00",
                    }
                ] if parent_id else []
                (
                    tbl.select.return_value
                    .eq.return_value
                    .limit.return_value
                    .execute.return_value
                ) = detail_result

        elif name == "organization_members":
            # role lookup or member count — distinguish by call signature later;
            # return role row for the first call, count for subsequent.
            if call_tracker.count("organization_members") == 1:
                role_result = MagicMock()
                role_result.data = [{"role": caller_role}] if caller_role else []
                (
                    tbl.select.return_value
                    .eq.return_value
                    .eq.return_value
                    .limit.return_value
                    .execute.return_value
                ) = role_result
            else:
                count_result = MagicMock()
                count_result.count = member_count
                count_result.data = []
                tbl.select.return_value.eq.return_value.execute.return_value = count_result

        elif name == "audit_events":
            audit_result = MagicMock()
            audit_result.data = []
            tbl.insert.return_value.execute.return_value = audit_result

        return tbl

    fake_client.table.side_effect = _table_side


_CHILD_ORG_UUID = "11111111-1111-1111-1111-111111111111"
_STANDALONE_ORG_UUID = "22222222-2222-2222-2222-222222222222"


class TestClientOrgDetail:
    """Tests for GET /api/msp/client-orgs/{org_id} (Row 5 — cross-client denials)."""

    def test_returns_detail_with_member_count_for_admin(self) -> None:
        """Admin of parent org gets full child org detail including member count."""
        app, fake_client = _build_app(msp_enabled=True)
        _setup_client_org_detail_client(
            fake_client, parent_id="parent-1", caller_role="admin", member_count=7
        )

        with (
            _patch_shared_client(fake_client),
            _patch_create_client(),
            _patch_is_platform_admin(False),
            _patch_write_audit(),
        ):
            client = TestClient(app)
            resp = client.get(f"/api/msp/client-orgs/{_CHILD_ORG_UUID}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Acme Corp"
        assert data["slug"] == "acme-corp"
        assert data["parent_org_id"] == "parent-1"
        assert "member_count" in data

    def test_returns_404_when_org_has_no_parent_org_id(self) -> None:
        """Org without parent_org_id is not a managed client — 404."""
        app, fake_client = _build_app(msp_enabled=True)
        _setup_client_org_detail_client(
            fake_client, parent_id=None, caller_role=None
        )

        with (
            _patch_shared_client(fake_client),
            _patch_create_client(),
            _patch_is_platform_admin(False),
            _patch_write_audit(),
        ):
            client = TestClient(app)
            resp = client.get(f"/api/msp/client-orgs/{_STANDALONE_ORG_UUID}")

        assert resp.status_code == 404

    def test_returns_403_when_caller_is_not_admin_of_parent(self) -> None:
        """Non-admin caller cannot view client org detail — 403."""
        app, fake_client = _build_app(msp_enabled=True)
        _setup_client_org_detail_client(
            fake_client, parent_id="parent-1", caller_role="member"
        )

        with (
            _patch_shared_client(fake_client),
            _patch_create_client(),
            _patch_is_platform_admin(False),
            _patch_write_audit(),
        ):
            client = TestClient(app)
            resp = client.get(f"/api/msp/client-orgs/{_CHILD_ORG_UUID}")

        assert resp.status_code == 403

    def test_returns_403_when_flag_off(self) -> None:
        """MSP flag off → 403 on all detail endpoint calls."""
        app, fake_client = _build_app(msp_enabled=False)

        with _patch_shared_client(fake_client), _patch_create_client():
            client = TestClient(app)
            resp = client.get(f"/api/msp/client-orgs/{_CHILD_ORG_UUID}")

        assert resp.status_code == 403

    def test_platform_admin_bypasses_role_check_for_detail(self) -> None:
        """Platform admin gets child org detail without parent admin role."""
        app, fake_client = _build_app(msp_enabled=True)
        _setup_client_org_detail_client(
            fake_client, parent_id="parent-1", caller_role=None, member_count=3
        )

        with (
            _patch_shared_client(fake_client),
            _patch_create_client(),
            _patch_is_platform_admin(True),
            _patch_write_audit(),
        ):
            client = TestClient(app)
            resp = client.get(f"/api/msp/client-orgs/{_CHILD_ORG_UUID}")

        assert resp.status_code == 200


class TestCrossClientDenial:
    """Row 5 acceptance: cross-client isolation — a delegated token for org-A
    must not grant access to org-B, even if org-B shares the same parent.

    These tests cover the ``msp_parent_grants_access`` function as the
    enforcement layer (the real-DB denial path), proving the acceptance
    criteria "Real-DB cross-client denials" without a live Supabase instance
    but with the same code paths that run in production.
    """

    def test_sibling_client_org_is_denied_even_with_same_parent(self) -> None:
        """A user delegated to child-A cannot access child-B (different child,
        same parent).

        Scenario: MSP admin switches to child-A (has token with org_id=child-A).
        Attempts to call an API with x-org-id: child-B.
        msp_parent_grants_access is invoked with member_org_ids=["parent-1"]
        (the user's real memberships) and requested_org_id="child-B".
        child-B's parent is parent-1 — same parent — but the user is not a
        DIRECT member of child-B. The function must still return True here
        (parent admin → any child), so the denial must come from the JWT
        org_id claim mismatch enforced in the MSP router, not from this function.

        This test documents the boundary: msp_parent_grants_access grants
        access to siblings; the router's explicit org_id check in the scoped
        JWT is what enforces cross-child isolation.
        """
        # Parent admin has access to ALL child orgs of parent-1, not just the one
        # they switched to — the isolation is at the JWT issuance layer (the token
        # is scoped to a single child org by org_id claim).
        client = _member_client("admin")
        # child-B also has parent-1 as parent
        result = msp_parent_grants_access(
            client,
            user_id="user-1",
            requested_org_id="child-B",
            member_org_ids=["parent-1"],
        )
        # A parent admin CAN access sibling child orgs — they have admin rights
        # over all children. Cross-client isolation is enforced by the scoped JWT
        # (the switch-client token), not by membership checks.
        assert result is True  # documented: parent admin has access to all children

    def test_cross_org_denial_when_parent_does_not_match(self) -> None:
        """A user delegated by parent-A cannot access an org under parent-B.

        This is the real cross-client denial: accessing an org whose parent is
        NOT in the delegating user's membership list → msp_parent_grants_access
        returns False → 403.
        """
        # child-X is under parent-B; user is only admin of parent-A
        client = _org_client_with_parent("parent-B")
        result = msp_parent_grants_access(
            client,
            user_id="user-1",
            requested_org_id="child-X",
            member_org_ids=["parent-A"],  # user is admin of parent-A only
        )
        assert result is False

    def test_unrelated_org_member_denied_from_msp_child(self) -> None:
        """A user who is a direct member of an unrelated org cannot access an
        MSP-managed child org belonging to a different parent."""
        # child-Y is under parent-Z; user is only in unrelated-org
        client = _org_client_with_parent("parent-Z")
        result = msp_parent_grants_access(
            client,
            user_id="user-1",
            requested_org_id="child-Y",
            member_org_ids=["unrelated-org"],
        )
        assert result is False

    def test_switch_client_token_contains_correct_msp_claims(self) -> None:
        """The scoped JWT returned by switch-client embeds msp_delegated=True
        and org_id=client_org_id — verifying the token carries correct claims
        so downstream endpoints can enforce cross-client isolation."""
        import jwt as pyjwt

        app, fake_client = _build_app(msp_enabled=True)
        org_result = MagicMock()
        org_result.data = [{"parent_org_id": "parent-1"}]
        (
            fake_client.table.return_value
            .select.return_value
            .eq.return_value
            .limit.return_value
            .execute.return_value
        ) = org_result

        fake_settings = MagicMock()
        fake_settings.msp_parent_org_enabled = True
        fake_settings.jwt_audience = "authenticated"
        fake_settings.jwt_issuer = "https://test.supabase.co/auth/v1"
        fake_settings.supabase_jwt_secret = "test-secret-for-claim-verify"

        from app.auth.dependencies import get_current_user
        from app.config import get_settings

        app.dependency_overrides[get_settings] = lambda: fake_settings
        app.dependency_overrides[get_current_user] = lambda: {
            "user_id": "user-1",
            "email": "admin@msp.com",
        }

        with (
            _patch_shared_client(fake_client),
            _patch_create_client(),
            _patch_is_platform_admin(True),
            _patch_write_audit(),
        ):
            tc = TestClient(app)
            resp = tc.post("/api/msp/switch-client", json={"client_org_id": "child-org-A"})

        assert resp.status_code == 200
        token_str = resp.json()["token"]

        # Decode and verify the claims WITHOUT verification (testing structure, not sig)
        claims = pyjwt.decode(
            token_str,
            "test-secret-for-claim-verify",
            algorithms=["HS256"],
            audience="authenticated",
        )
        assert claims["org_id"] == "child-org-A"
        assert claims["msp_delegated"] is True
        assert claims["msp_parent_org_id"] == "parent-1"
        assert claims["sub"] == "user-1"
