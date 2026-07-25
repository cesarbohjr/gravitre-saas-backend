from __future__ import annotations

from unittest.mock import MagicMock

from app.services.org_membership import pick_default_org_id


def test_pick_default_org_id_prefers_primary():
    org_id = pick_default_org_id(
        ["00000000-0000-0000-0000-000000000001", "org-real"],
        primary_org_id="org-real",
    )
    assert org_id == "org-real"


def test_pick_default_org_id_prefers_non_demo():
    org_id = pick_default_org_id(
        ["00000000-0000-0000-0000-000000000001", "org-real"],
        primary_org_id=None,
    )
    assert org_id == "org-real"


def test_pick_default_org_id_honors_requested_membership():
    org_id = pick_default_org_id(
        ["org-a", "org-b"],
        requested_org_id="org-b",
    )
    assert org_id == "org-b"


def test_ensure_user_workspace_returns_existing_without_insert():
    from app.services.org_membership import ensure_user_workspace

    client = MagicMock()
    memberships = MagicMock()
    memberships.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[{"org_id": "org-existing"}]
    )
    users = MagicMock()
    users.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[{"org_id": "org-existing"}]
    )

    def table(name: str):
        if name == "organization_members":
            return memberships
        if name == "users":
            return users
        return MagicMock()

    client.table.side_effect = table

    org_id = ensure_user_workspace(client, "user-1", email="u@example.com")
    assert org_id == "org-existing"
    client.table("organizations").insert.assert_not_called()


def test_promote_user_to_org_owner_inserts_when_membership_missing():
    from app.services.org_membership import promote_user_to_org_owner

    client = MagicMock()
    members = MagicMock()
    members.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[]
    )
    envs = MagicMock()
    envs.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[{"id": "env-1"}]
    )
    users = MagicMock()

    def table(name: str):
        if name == "organization_members":
            return members
        if name == "environments":
            return envs
        if name == "users":
            return users
        return MagicMock()

    client.table.side_effect = table
    promote_user_to_org_owner(client, "org-1", "user-1")
    members.insert.assert_called_once()
    users.update.assert_called_once()


def test_ensure_founder_admin_access_promotes_gravitre_email():
    from app.services.org_membership import ensure_founder_admin_access

    client = MagicMock()
    platform = MagicMock()
    members = MagicMock()
    members.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[{"id": "m1", "role": "admin"}]
    )
    envs = MagicMock()
    envs.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[{"id": "env-1"}]
    )
    users = MagicMock()

    def table(name: str):
        if name == "platform_admins":
            return platform
        if name == "organization_members":
            return members
        if name == "environments":
            return envs
        if name == "users":
            return users
        return MagicMock()

    client.table.side_effect = table
    ensure_founder_admin_access(
        client,
        user_id="user-1",
        email="cesar@gravitre.app",
        org_id="org-1",
    )
    platform.upsert.assert_called_once()
    members.update.assert_called_once()


def test_ensure_founder_admin_access_ignores_non_founder():
    from app.services.org_membership import ensure_founder_admin_access

    client = MagicMock()
    ensure_founder_admin_access(
        client,
        user_id="user-1",
        email="member@example.com",
        org_id="org-1",
    )
    client.table.assert_not_called()
