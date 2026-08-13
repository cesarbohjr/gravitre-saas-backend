"""Part D P6: department_members mutations write audit events (STA-311)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.routers.settings import (
    DepartmentMemberAddRequest,
    add_department_member_route,
    remove_department_member_route,
)


def _settings():
    s = MagicMock()
    s.supabase_url = "https://example.supabase.co"
    s.supabase_service_role_key = "service-role"
    return s


@pytest.mark.asyncio
@patch("app.routers.settings.write_audit_event")
@patch("app.routers.settings._resolve_org_user_id", return_value="user-2")
@patch("app.routers.settings.create_client")
async def test_add_department_member_writes_audit(mock_client, _resolve, mock_audit):
    client = MagicMock()
    mock_client.return_value = client
    dept = MagicMock()
    dept.select.return_value = dept
    dept.eq.return_value = dept
    dept.limit.return_value = dept
    dept.execute.return_value = MagicMock(data=[{"id": "dept-1", "lite_seat_allocation": 5}], error=None)

    members = MagicMock()
    members.upsert.return_value = members
    members.select.return_value = members
    members.eq.return_value = members
    members.limit.return_value = members
    members.execute.return_value = MagicMock(
        data=[{"id": "mem-1", "department_id": "dept-1", "user_id": "user-2", "role": "viewer"}],
        error=None,
    )

    def table(name):
        if name == "departments":
            return dept
        if name == "department_members":
            return members
        return MagicMock()

    client.table.side_effect = table
    admin = ({"user_id": "admin-1"}, "org-1")
    body = DepartmentMemberAddRequest(
        department_id="dept-1",
        user_email="member@example.com",
        role="viewer",
    )
    result = await add_department_member_route(body, admin, _settings())
    assert result["member"]["id"] == "mem-1"
    mock_audit.assert_called_once()
    assert mock_audit.call_args.kwargs["action"] == "department_member.added"


@pytest.mark.asyncio
@patch("app.routers.settings.write_audit_event")
@patch(
    "app.routers.settings.invite_org_member_by_email",
    return_value={
        "user_id": "user-3",
        "email": "new.member@example.com",
        "role": "viewer",
        "invite_email_sent": True,
        "invite_email_status": "sent",
        "membership_created": True,
    },
)
@patch("app.routers.settings._resolve_org_user_id", return_value=None)
@patch("app.routers.settings.create_client")
async def test_add_department_member_invites_when_user_missing(mock_client, _resolve, mock_invite, mock_audit):
    client = MagicMock()
    mock_client.return_value = client
    dept = MagicMock()
    dept.select.return_value = dept
    dept.eq.return_value = dept
    dept.limit.return_value = dept
    dept.execute.return_value = MagicMock(data=[{"id": "dept-1", "lite_seat_allocation": 5}], error=None)

    members = MagicMock()
    members.upsert.return_value = members
    members.select.return_value = members
    members.eq.return_value = members
    members.limit.return_value = members
    members.execute.return_value = MagicMock(
        data=[{"id": "mem-2", "department_id": "dept-1", "user_id": "user-3", "role": "admin"}],
        error=None,
    )

    def table(name):
        if name == "departments":
            return dept
        if name == "department_members":
            return members
        return MagicMock()

    client.table.side_effect = table
    admin = ({"user_id": "admin-1"}, "org-1")
    body = DepartmentMemberAddRequest(
        department_id="dept-1",
        user_email="new.member@example.com",
        role="admin",
        send_invite=True,
    )

    result = await add_department_member_route(body, admin, _settings())
    assert result["member"]["id"] == "mem-2"
    assert result["invite"]["invite_email_sent"] is True
    mock_invite.assert_called_once()
    assert mock_invite.call_args.kwargs["invite_context"] == "lite_seat_assignment"
    mock_audit.assert_called_once()


def test_resolve_org_user_id_uses_organization_members_not_org_members():
    from app.routers.settings import _resolve_org_user_id

    client = MagicMock()
    users = MagicMock()
    users.select.return_value = users
    users.ilike.return_value = users
    users.limit.return_value = users
    users.execute.return_value = MagicMock(
        data=[{"id": "u-1", "auth_user_id": "auth-1", "email": "a@ex.com"}],
        error=None,
    )
    org_members = MagicMock()
    org_members.select.return_value = org_members
    org_members.eq.return_value = org_members
    org_members.limit.return_value = org_members
    org_members.execute.return_value = MagicMock(
        data=[{"user_id": "auth-1"}],
        error=None,
    )
    seen: list[str] = []

    def table(name):
        seen.append(name)
        if name == "users":
            return users
        if name == "organization_members":
            return org_members
        raise AssertionError(f"unexpected table {name}")

    client.table.side_effect = table
    assert _resolve_org_user_id(client, "org-1", "a@ex.com") == "auth-1"
    assert "organization_members" in seen
    assert "org_members" not in seen


@pytest.mark.asyncio
@patch("app.routers.settings.write_audit_event")
@patch("app.routers.settings.create_client")
async def test_remove_department_member_writes_audit(mock_client, mock_audit):
    client = MagicMock()
    mock_client.return_value = client
    dept = MagicMock()
    dept.select.return_value = dept
    dept.eq.return_value = dept
    dept.limit.return_value = dept
    dept.execute.return_value = MagicMock(data=[{"id": "dept-1"}], error=None)

    members = MagicMock()
    members.delete.return_value = members
    members.eq.return_value = members
    # Prod supabase-py APIResponse has no .error attribute — simulate that shape.
    api_resp = MagicMock(spec=["data"])
    api_resp.data = [{"id": "mem-1"}]
    members.execute.return_value = api_resp

    def table(name):
        if name == "departments":
            return dept
        if name == "department_members":
            return members
        return MagicMock()

    client.table.side_effect = table
    admin = ({"user_id": "admin-1"}, "org-1")
    result = await remove_department_member_route(
        admin,
        _settings(),
        department_id="dept-1",
        user_id="user-2",
    )
    assert result["success"] is True
    mock_audit.assert_called_once()
    assert mock_audit.call_args.kwargs["action"] == "department_member.removed"


@pytest.mark.asyncio
@patch("app.routers.settings.write_audit_event")
@patch("app.routers.settings.create_client")
async def test_remove_department_member_tolerates_missing_error_attr(mock_client, mock_audit):
    """Regression: accessing deleted.error raised AttributeError → HTTP 500 on prod."""
    client = MagicMock()
    mock_client.return_value = client
    dept = MagicMock()
    dept.select.return_value = dept
    dept.eq.return_value = dept
    dept.limit.return_value = dept
    dept.execute.return_value = MagicMock(data=[{"id": "dept-1"}], error=None)

    class _NoErrorAttr:
        data = [{"id": "mem-1"}]

    members = MagicMock()
    members.delete.return_value = members
    members.eq.return_value = members
    members.execute.return_value = _NoErrorAttr()

    def table(name):
        if name == "departments":
            return dept
        if name == "department_members":
            return members
        return MagicMock()

    client.table.side_effect = table
    admin = ({"user_id": "admin-1"}, "org-1")
    result = await remove_department_member_route(
        admin,
        _settings(),
        department_id="dept-1",
        user_id="user-2",
    )
    assert result["success"] is True
    mock_audit.assert_called_once()
