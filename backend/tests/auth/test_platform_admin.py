"""Tests for platform admin helpers and org admin role checks."""
from __future__ import annotations

from app.auth.platform_admin import is_org_admin_role


def test_is_org_admin_role_accepts_owner_and_admin():
    assert is_org_admin_role("owner") is True
    assert is_org_admin_role("admin") is True
    assert is_org_admin_role("Admin") is True
    assert is_org_admin_role("member") is False
    assert is_org_admin_role("viewer") is False
    assert is_org_admin_role(None) is False
