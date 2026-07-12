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
    members.single.return_value = members
    members.execute.return_value = MagicMock(
        data={"id": "mem-1", "department_id": "dept-1", "user_id": "user-2", "role": "viewer"},
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
    members.execute.return_value = MagicMock(data=[{"id": "mem-1"}], error=None)

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
