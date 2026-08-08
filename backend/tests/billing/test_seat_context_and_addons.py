"""Seat type + Meson addon composition (Phase 0 decisions A1/B1/C1/E1)."""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.billing.seat_context import assert_department_manager, assert_full_seat, resolve_seat_context
from app.middleware import entitlements as ent


class _FakeTable:
    def __init__(self, store: dict[str, list[dict[str, Any]]], name: str):
        self._store = store
        self._name = name
        self._filters: dict[str, Any] = {}

    def select(self, *_a, **_k):
        return self

    def eq(self, k, v):
        self._filters[k] = v
        return self

    def in_(self, k, values):
        self._filters[f"in:{k}"] = list(values)
        return self

    def limit(self, _n):
        return self

    def execute(self):
        rows = list(self._store.get(self._name, []))
        for k, v in self._filters.items():
            if k.startswith("in:"):
                key = k.split(":", 1)[1]
                rows = [r for r in rows if r.get(key) in v]
            else:
                rows = [r for r in rows if r.get(k) == v]
        return MagicMock(data=rows, error=None)


class _FakeClient:
    def __init__(self, store: dict[str, list[dict[str, Any]]]):
        self._store = store

    def table(self, name: str):
        return _FakeTable(self._store, name)


def test_lite_member_is_not_full_seat():
    org = "org-1"
    user = "user-lite"
    client = _FakeClient(
        {
            "organization_members": [{"org_id": org, "user_id": user, "role": "member"}],
            "department_members": [
                {
                    "id": "m1",
                    "department_id": "d1",
                    "user_id": user,
                    "role": "viewer",
                    "departments": {"id": "d1", "name": "Sales", "org_id": org},
                }
            ],
        }
    )
    seat = resolve_seat_context(client, org_id=org, user_id=user)
    assert seat["is_lite"] is True
    assert seat["is_full_seat"] is False
    with pytest.raises(HTTPException) as exc:
        assert_full_seat(seat, action="meson_build")
    assert exc.value.status_code == 403


def test_department_manager_scoped_not_cross_dept():
    org = "org-1"
    user = "user-mgr"
    client = _FakeClient(
        {
            "organization_members": [{"org_id": org, "user_id": user, "role": "member"}],
            "department_members": [
                {
                    "id": "m1",
                    "department_id": "d1",
                    "user_id": user,
                    "role": "admin",
                    "departments": {"id": "d1", "name": "Sales", "org_id": org},
                }
            ],
        }
    )
    seat = resolve_seat_context(client, org_id=org, user_id=user)
    assert seat["is_lite"] is True
    assert seat["is_department_manager"] is True
    assert_department_manager(seat, "d1")
    with pytest.raises(HTTPException):
        assert_department_manager(seat, "d-other")


def test_resolve_entitlements_lite_users_from_plan_and_addon_flags(monkeypatch):
    settings = MagicMock()
    plan = {
        "code": "control",
        "features": {"lite_users": 5, "meson": 10, "approvals": True},
        "workflows_limit": 40,
        "agents_limit": 3,
        "environments_limit": 2,
        "ai_credits_included": 5000,
        "workflow_runs_included": 2500,
    }
    monkeypatch.setattr(ent, "get_supabase_client", lambda _s: MagicMock())
    monkeypatch.setattr(ent, "get_plan_for_org", lambda *_a, **_k: plan)
    monkeypatch.setattr(
        ent,
        "get_org_billing",
        lambda *_a, **_k: {"plan_code": "control", "billing_status": "active"},
    )
    monkeypatch.setattr(
        ent,
        "_select_latest_subscription",
        lambda *_a, **_k: {"seat_count": 2, "lite_seats": 0, "meson_addons": ["voice_interface"]},
    )
    monkeypatch.setattr(ent, "_usage_totals", lambda *_a, **_k: {})

    result = ent.resolve_entitlements(settings, "org-1")
    assert result["limits"]["lite_seats_included"] == 5
    assert "voice_interface" in result["addons"]
    assert result["features"]["meson_addon_voice_interface"] is True
    assert result["features"]["meson_builder"] is True
