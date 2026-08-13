from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.services.org_member_invite_service import invite_org_member_by_email


def _settings():
    s = MagicMock()
    s.public_app_url = "https://gravitre.app"
    return s


def _make_query_mock(response):
    q = MagicMock()
    q.select.return_value = q
    q.ilike.return_value = q
    q.eq.return_value = q
    q.limit.return_value = q
    q.upsert.return_value = q
    q.execute.return_value = response
    return q


def test_invite_org_member_provisions_and_upserts_membership():
    users = _make_query_mock(MagicMock(data=[], error=None))
    auth_users = _make_query_mock(MagicMock(data=[], error=None))
    org_members = MagicMock()
    org_members.select.return_value = org_members
    org_members.eq.return_value = org_members
    org_members.limit.return_value = org_members
    org_members.upsert.return_value = org_members
    org_members.execute.side_effect = [
        MagicMock(data=[], error=None),
        MagicMock(data=[{"id": "mem-1"}], error=None),
    ]

    client = MagicMock()
    client.table.side_effect = lambda name: {
        "users": users,
        "organization_members": org_members,
    }[name]
    schema = MagicMock()
    schema.table.return_value = auth_users
    client.schema.return_value = schema
    invite_response = MagicMock()
    invite_response.user = MagicMock(id="0f36f9e2-e4ea-46fb-a017-bf3e9a64f11c")
    client.auth.admin.invite_user_by_email.return_value = invite_response

    result = invite_org_member_by_email(
        client,
        _settings(),
        org_id="org-1",
        email="new.member@example.com",
        role="viewer",
        invited_by_user_id="admin-1",
        send_invite=True,
        invite_context="lite_seat_assignment",
    )

    assert result["invite_email_sent"] is True
    assert result["invite_email_status"] == "sent"
    assert result["membership_created"] is True
    assert result["user_id"] == "0f36f9e2-e4ea-46fb-a017-bf3e9a64f11c"


def test_invite_org_member_requires_existing_user_when_send_invite_disabled():
    users = _make_query_mock(MagicMock(data=[], error=None))
    auth_users = _make_query_mock(MagicMock(data=[], error=None))

    client = MagicMock()
    client.table.side_effect = lambda name: {"users": users}[name]
    schema = MagicMock()
    schema.table.return_value = auth_users
    client.schema.return_value = schema

    with pytest.raises(HTTPException) as exc:
        invite_org_member_by_email(
            client,
            _settings(),
            org_id="org-1",
            email="missing@example.com",
            role="member",
            invited_by_user_id="admin-1",
            send_invite=False,
        )
    assert exc.value.status_code == 404


def test_invite_org_member_handles_already_registered_invite_errors():
    users = _make_query_mock(MagicMock(data=[{"auth_user_id": "user-123"}], error=None))
    org_members = MagicMock()
    org_members.select.return_value = org_members
    org_members.eq.return_value = org_members
    org_members.limit.return_value = org_members
    org_members.upsert.return_value = org_members
    org_members.execute.side_effect = [
        MagicMock(data=[{"id": "mem-existing"}], error=None),
        MagicMock(data=[{"id": "mem-existing"}], error=None),
    ]

    client = MagicMock()
    client.table.side_effect = lambda name: {
        "users": users,
        "organization_members": org_members,
    }[name]
    client.auth.admin.invite_user_by_email.side_effect = Exception("User already registered")

    result = invite_org_member_by_email(
        client,
        _settings(),
        org_id="org-1",
        email="existing@example.com",
        role="member",
        invited_by_user_id="admin-1",
        send_invite=True,
    )

    assert result["invite_email_sent"] is False
    assert result["invite_email_status"] == "already_registered"
    assert result["membership_created"] is False
