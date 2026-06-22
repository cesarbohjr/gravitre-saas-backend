"""Regression tests for platform admin helpers."""
from __future__ import annotations

from types import SimpleNamespace

from app.auth.platform_admin import is_org_admin_role, is_platform_admin, is_platform_admin_email


class _ApiResponse:
    """Mimics supabase-py v2 execute() responses (no `.error` attribute)."""

    def __init__(self, data: list[dict] | None) -> None:
        self.data = data


def test_is_org_admin_role_accepts_owner_and_admin():
    assert is_org_admin_role("owner") is True
    assert is_org_admin_role("admin") is True
    assert is_org_admin_role("Admin") is True
    assert is_org_admin_role("member") is False
    assert is_org_admin_role("viewer") is False
    assert is_org_admin_role(None) is False


def test_is_platform_admin_uses_data_only():
    client = SimpleNamespace(
        table=lambda _name: SimpleNamespace(
            select=lambda *_args, **_kwargs: SimpleNamespace(
                eq=lambda *_a, **_k: SimpleNamespace(
                    limit=lambda *_a2, **_k2: SimpleNamespace(
                        execute=lambda: _ApiResponse([{"user_id": "u1"}])
                    )
                )
            )
        )
    )
    assert is_platform_admin(client, "u1") is True


def test_is_platform_admin_email_uses_data_only():
    client = SimpleNamespace(
        table=lambda _name: SimpleNamespace(
            select=lambda *_args, **_kwargs: SimpleNamespace(
                eq=lambda *_a, **_k: SimpleNamespace(
                    limit=lambda *_a2, **_k2: SimpleNamespace(
                        execute=lambda: _ApiResponse([{"email": "admin@example.com"}])
                    )
                )
            )
        )
    )
    assert is_platform_admin_email(client, "admin@example.com") is True


def test_is_platform_admin_email_returns_false_when_table_unavailable():
    from unittest.mock import MagicMock

    client = MagicMock()
    client.table.side_effect = RuntimeError("db down")
    assert is_platform_admin_email(client, "cesar.bohorquez.jr@gmail.com") is False
