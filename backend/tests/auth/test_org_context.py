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
    client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[{"org_id": "org-a"}, {"org_id": "org-b"}]
    )
    with patch("supabase.create_client", return_value=client):
        with patch("app.auth.dependencies.is_platform_admin", return_value=False):
            org_id = await get_org_context(
                _request(org_id="org-b"),
                {"user_id": "user-1", "email": "u@example.com"},
                _settings(),
            )
    assert org_id == "org-b"


@pytest.mark.asyncio
async def test_get_org_context_multi_org_defaults_without_500():
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[{"org_id": "org-a"}, {"org_id": "org-b"}]
    )
    with patch("supabase.create_client", return_value=client):
        with patch("app.auth.dependencies.is_platform_admin", return_value=False):
            org_id = await get_org_context(
                _request(),
                {"user_id": "user-1", "email": "u@example.com"},
                _settings(),
            )
    assert org_id == "org-a"


@pytest.mark.asyncio
async def test_get_org_context_platform_admin_can_use_any_requested_org():
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[{"org_id": "org-a"}]
    )
    with patch("supabase.create_client", return_value=client):
        with patch("app.auth.dependencies.is_platform_admin", return_value=True):
            org_id = await get_org_context(
                _request(org_id="org-other"),
                {"user_id": "user-1", "email": "admin@example.com"},
                _settings(),
            )
    assert org_id == "org-other"
