from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest

from app.routers.org import OrganizationMemberInviteRequest, invite_organization_member


def _settings():
    s = MagicMock()
    s.supabase_url = "https://example.supabase.co"
    s.supabase_service_role_key = "service-role"
    s.public_app_url = "https://gravitre.app"
    return s


@pytest.mark.asyncio
@patch("app.routers.org.write_audit_event")
@patch(
    "app.routers.org.invite_org_member_by_email",
    return_value={
        "email": "teammate@example.com",
        "user_id": "0b0c253f-53c6-4f54-8618-f28fe5e3fbc0",
        "role": "viewer",
        "invite_email_sent": True,
        "invite_email_status": "sent",
        "membership_created": True,
    },
)
@patch("app.routers.org._require_org_admin")
@patch("app.routers.org.create_client")
async def test_invite_organization_member_returns_invite_metadata(
    mock_create_client,
    _mock_require_org_admin,
    mock_invite_member,
    mock_audit,
):
    client = MagicMock()
    mock_create_client.return_value = client
    body = OrganizationMemberInviteRequest(
        email="Teammate@example.com",
        role="viewer",
        send_invite=True,
    )

    result = await invite_organization_member(
        UUID("11111111-1111-1111-1111-111111111111"),
        body,
        {"user_id": "admin-1"},
        _settings(),
    )

    assert result["ok"] is True
    assert result["member"]["invite_email_sent"] is True
    mock_invite_member.assert_called_once()
    assert mock_invite_member.call_args.kwargs["send_invite"] is True
    mock_audit.assert_called_once()


@pytest.mark.asyncio
@patch("app.routers.org.write_audit_event")
@patch(
    "app.routers.org.invite_org_member_by_email",
    return_value={
        "email": "existing@example.com",
        "user_id": "7bb20a7e-cae0-46f8-a522-b4dbc0908e89",
        "role": "member",
        "invite_email_sent": False,
        "invite_email_status": "not_requested",
        "membership_created": False,
    },
)
@patch("app.routers.org._require_org_admin")
@patch("app.routers.org.create_client")
async def test_invite_organization_member_honors_send_invite_false(
    mock_create_client,
    _mock_require_org_admin,
    mock_invite_member,
    _mock_audit,
):
    client = MagicMock()
    mock_create_client.return_value = client
    body = OrganizationMemberInviteRequest(
        email="existing@example.com",
        role="member",
        send_invite=False,
    )

    result = await invite_organization_member(
        UUID("22222222-2222-2222-2222-222222222222"),
        body,
        {"user_id": "admin-2"},
        _settings(),
    )

    assert result["ok"] is True
    assert result["member"]["invite_email_sent"] is False
    assert mock_invite_member.call_args.kwargs["send_invite"] is False
