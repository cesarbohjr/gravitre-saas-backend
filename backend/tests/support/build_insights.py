"""Shared helpers for BUILD/ACTIVITY/INSIGHTS regression tests."""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.auth.dependencies import (
    get_current_user,
    get_environment_context,
    get_org_context,
    require_admin,
)
from app.config import Settings, get_settings
from app.main import app

client = TestClient(app)


def make_test_settings(**overrides: Any) -> Settings:
    base = Settings(
        app_env="dev",
        supabase_url="https://test.supabase.co",
        supabase_anon_key="anon-test",
        supabase_service_role_key="service-role-test",
        supabase_jwt_secret="jwt-secret-test",
    )
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


def clear_overrides() -> None:
    app.dependency_overrides.clear()


def authenticate(
    *,
    org_id: str = "org-1",
    user_id: str = "user-1",
    email: str = "u@example.com",
    environment: str = "production",
    as_admin: bool = False,
) -> None:
    app.dependency_overrides[get_current_user] = lambda: {"user_id": user_id, "email": email}
    app.dependency_overrides[get_org_context] = lambda: org_id
    app.dependency_overrides[get_environment_context] = lambda: environment
    app.dependency_overrides[get_settings] = lambda: make_test_settings()
    if as_admin:
        app.dependency_overrides[require_admin] = lambda: ({"user_id": user_id, "email": email}, org_id)


def chain_mock(*, data: list | None = None, count: int | None = None) -> MagicMock:
    chain = MagicMock()
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.gte.return_value = chain
    chain.lte.return_value = chain
    chain.lt.return_value = chain
    chain.in_.return_value = chain
    chain.is_.return_value = chain
    chain.order.return_value = chain
    chain.limit.return_value = chain
    chain.range.return_value = chain
    chain.update.return_value = chain
    chain.insert.return_value = chain
    chain.delete.return_value = chain
    result = SimpleNamespace(data=data or [], error=None)
    if count is not None:
        result.count = count
    chain.execute.return_value = result
    return chain


def table_client(table_map: dict[str, MagicMock]) -> MagicMock:
    client = MagicMock()

    def _table(name: str) -> MagicMock:
        table = MagicMock()
        table.select.return_value = table_map.get(name, chain_mock())
        table.insert.return_value = table_map.get(name, chain_mock())
        table.update.return_value = table_map.get(name, chain_mock())
        table.delete.return_value = table_map.get(name, chain_mock())
        if name in table_map:
            mapped = table_map[name]
            table.select.return_value = mapped
            table.insert.return_value = mapped
            table.update.return_value = mapped
            table.delete.return_value = mapped
        return table

    client.table.side_effect = _table
    return client
