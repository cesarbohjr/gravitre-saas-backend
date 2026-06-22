from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import Request

from app.auth.dependencies import get_org_context
from app.config import Settings


def _settings() -> Settings:
    return Settings(
        app_env="dev",
        supabase_url="https://test.supabase.co",
        supabase_anon_key="anon",
        supabase_service_role_key="service",
        supabase_jwt_secret="secret",
    )


def _request(*, org_id: str | None = None) -> Request:
    headers: list[tuple[bytes, bytes]] = []
    if org_id:
        headers.append((b"x-org-id", org_id.encode()))
    return Request(
        {
            "type": "http",
            "headers": headers,
            "query_string": b"",
            "path": "/api/settings",
            "method": "GET",
        }
    )


@pytest.mark.asyncio
async def test_get_org_context_uses_requested_membership():
    client = MagicMock()
    with patch("supabase.create_client", return_value=client):
        with patch("app.auth.dependencies.is_platform_admin", return_value=False):
            with patch(
                "app.services.org_membership.list_member_org_ids",
                return_value=["org-a", "org-b"],
            ):
                with patch("app.services.org_membership.load_user_primary_org_id", return_value=None):
                    org_id = await get_org_context(
                        _request(org_id="org-b"),
                        {"user_id": "user-1", "email": "u@example.com"},
                        _settings(),
                    )
    assert org_id == "org-b"


@pytest.mark.asyncio
async def test_get_org_context_multi_org_defaults_without_500():
    client = MagicMock()
    with patch("supabase.create_client", return_value=client):
        with patch("app.auth.dependencies.is_platform_admin", return_value=False):
            with patch(
                "app.services.org_membership.list_member_org_ids",
                return_value=["org-a", "org-b"],
            ):
                with patch("app.services.org_membership.load_user_primary_org_id", return_value=None):
                    org_id = await get_org_context(
                        _request(),
                        {"user_id": "user-1", "email": "u@example.com"},
                        _settings(),
                    )
    assert org_id == "org-a"


@pytest.mark.asyncio
async def test_get_org_context_prefers_primary_org():
    client = MagicMock()
    with patch("supabase.create_client", return_value=client):
        with patch("app.auth.dependencies.is_platform_admin", return_value=False):
            with patch(
                "app.services.org_membership.list_member_org_ids",
                return_value=["org-a", "org-b"],
            ):
                with patch("app.services.org_membership.load_user_primary_org_id", return_value="org-b"):
                    org_id = await get_org_context(
                        _request(),
                        {"user_id": "user-1", "email": "u@example.com"},
                        _settings(),
                    )
    assert org_id == "org-b"


@pytest.mark.asyncio
async def test_get_org_context_platform_admin_can_use_any_requested_org():
    client = MagicMock()
    with patch("supabase.create_client", return_value=client):
        with patch("app.auth.dependencies.is_platform_admin", return_value=True):
            with patch(
                "app.services.org_membership.list_member_org_ids",
                return_value=["org-a"],
            ):
                org_id = await get_org_context(
                    _request(org_id="org-other"),
                    {"user_id": "user-1", "email": "admin@example.com"},
                    _settings(),
                )
    assert org_id == "org-other"


@pytest.mark.asyncio
async def test_get_org_context_auto_provisions_workspace():
    client = MagicMock()
    with patch("supabase.create_client", return_value=client):
        with patch("app.auth.dependencies.is_platform_admin", return_value=False):
            with patch("app.services.org_membership.list_member_org_ids", return_value=[]):
                with patch(
                    "app.services.org_membership.ensure_user_workspace",
                    return_value="org-new",
                ) as ensure_mock:
                    org_id = await get_org_context(
                        _request(),
                        {"user_id": "user-1", "email": "u@example.com"},
                        _settings(),
                    )
    ensure_mock.assert_called_once()
    assert org_id == "org-new"


@pytest.mark.asyncio
async def test_get_org_context_rejects_unauthorized_requested_org():
    """Non-members must not receive org context for an org they do not belong to."""
    client = MagicMock()
    with patch("supabase.create_client", return_value=client):
        with patch("app.auth.dependencies.is_platform_admin", return_value=False):
            with patch(
                "app.services.org_membership.list_member_org_ids",
                return_value=["org-a"],
            ):
                with patch("app.services.org_membership.load_user_primary_org_id", return_value=None):
                    org_id = await get_org_context(
                        _request(org_id="org-other"),
                        {"user_id": "user-1", "email": "u@example.com"},
                        _settings(),
                    )
    assert org_id == "org-a"


@pytest.mark.asyncio
async def test_get_org_context_does_not_fallback_to_existing_org_without_membership():
    client = MagicMock()
    org_chain = MagicMock()
    org_chain.select.return_value = org_chain
    org_chain.eq.return_value = org_chain
    org_chain.limit.return_value = org_chain
    org_chain.execute.return_value = MagicMock(data=[{"id": "org-other"}])
    client.table.return_value = org_chain

    with patch("supabase.create_client", return_value=client):
        with patch("app.auth.dependencies.is_platform_admin", return_value=False):
            with patch("app.services.org_membership.list_member_org_ids", return_value=[]):
                with patch(
                    "app.services.org_membership.ensure_user_workspace",
                    return_value="org-new",
                ) as ensure_mock:
                    org_id = await get_org_context(
                        _request(org_id="org-other"),
                        {"user_id": "user-1", "email": "u@example.com"},
                        _settings(),
                    )
    ensure_mock.assert_called_once()
    assert org_id == "org-new"
