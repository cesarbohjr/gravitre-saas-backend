"""Lite seats: per-department resource counts and the department members list."""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.routers import departments as departments_router
from app.routers import settings as settings_router

ORG = "11111111-1111-1111-1111-111111111111"
OTHER_ORG = "99999999-9999-9999-9999-999999999999"


class _Query:
    def __init__(self, store: dict[str, list[dict[str, Any]]], name: str):
        self._store = store
        self._name = name
        self._eq: dict[str, Any] = {}
        self._in: dict[str, set[str]] = {}

    def select(self, *_a, **_k):
        return self

    def eq(self, key, value):
        self._eq[key] = value
        return self

    def in_(self, key, values):
        self._in[key] = {str(v) for v in values}
        return self

    def order(self, *_a, **_k):
        return self

    def limit(self, *_a):
        return self

    def execute(self):
        if self._name not in self._store:
            return SimpleNamespace(data=None, error={"message": f"relation {self._name} does not exist"})
        rows = [
            r
            for r in self._store[self._name]
            if all(r.get(k) == v for k, v in self._eq.items())
            and all(str(r.get(k)) in vals for k, vals in self._in.items())
        ]
        return SimpleNamespace(data=rows, error=None)


class _Client:
    def __init__(self, store):
        self.store = store

    def table(self, name):
        return _Query(self.store, name)


def _store() -> dict[str, list[dict[str, Any]]]:
    return {
        "departments": [
            {"id": "d1", "org_id": ORG, "name": "Sales", "lite_seat_allocation": 3, "created_at": "2026-10-01"},
            {"id": "d2", "org_id": ORG, "name": "Finance", "lite_seat_allocation": 1, "created_at": "2026-10-02"},
            {"id": "dx", "org_id": OTHER_ORG, "name": "Other", "lite_seat_allocation": 9, "created_at": "2026-10-02"},
        ],
        "department_members": [
            {"id": "m1", "department_id": "d1", "user_id": "u1", "role": "viewer", "created_at": "2026-10-03"},
            {"id": "m2", "department_id": "d1", "user_id": "u2", "role": "admin", "created_at": "2026-10-04"},
        ],
        "department_resource_assignments": [
            {"org_id": ORG, "department_id": "d1", "resource_type": "workflow", "resource_id": "w1"},
            {"org_id": ORG, "department_id": "d1", "resource_type": "agent", "resource_id": "a1"},
            {"org_id": OTHER_ORG, "department_id": "dx", "resource_type": "agent", "resource_id": "a9"},
        ],
        "users": [
            {"id": "p1", "auth_user_id": "u1", "email": "ana@example.com", "full_name": "Ana Ruiz"},
            {"id": "u2", "auth_user_id": None, "email": "bo@example.com", "full_name": None},
        ],
    }


def test_lite_seats_reports_resource_count_per_department(monkeypatch):
    client = _Client(_store())
    monkeypatch.setattr(settings_router, "shared_service_client", lambda *_a, **_k: client)
    import app.middleware.entitlements as entitlements

    monkeypatch.setattr(
        entitlements,
        "resolve_entitlements",
        lambda *_a, **_k: {"tier": "control", "limits": {"lite_seats_included": 5}},
    )
    result = settings_router.get_lite_seats_route(_user={"user_id": "u1"}, org_id=ORG, settings=MagicMock())
    by_id = {d["id"]: d for d in result["departments"]}
    assert set(by_id) == {"d1", "d2"}
    assert by_id["d1"]["resource_count"] == 2
    assert by_id["d2"]["resource_count"] == 0
    assert by_id["d1"]["used_seats"] == 2
    assert result["summary"] == {
        "included": 5,
        "included_display": "5",
        "unlimited": False,
        "allocated": 4,
        "used": 2,
        "plan_code": "control",
    }


def test_lite_seats_resource_count_fails_soft_without_assignments_table(monkeypatch):
    store = _store()
    del store["department_resource_assignments"]
    client = _Client(store)
    monkeypatch.setattr(settings_router, "shared_service_client", lambda *_a, **_k: client)
    import app.middleware.entitlements as entitlements

    monkeypatch.setattr(entitlements, "resolve_entitlements", lambda *_a, **_k: {"tier": "command", "limits": {}})
    result = settings_router.get_lite_seats_route(_user={"user_id": "u1"}, org_id=ORG, settings=MagicMock())
    assert all(d["resource_count"] == 0 for d in result["departments"])
    assert result["summary"]["unlimited"] is True


def _patch_departments(monkeypatch, client, seat):
    monkeypatch.setattr(departments_router, "_client", lambda _s: client)
    monkeypatch.setattr(departments_router, "resolve_seat_context", lambda *_a, **_k: seat)


def test_department_members_lists_profiles_for_org_admin(monkeypatch):
    client = _Client(_store())
    _patch_departments(
        monkeypatch,
        client,
        {"is_org_admin": True, "managed_department_ids": [], "member_department_ids": []},
    )
    result = departments_router.list_department_members(
        "d1", current_user={"user_id": "admin"}, org_id=ORG, settings=MagicMock()
    )
    members = {m["user_id"]: m for m in result["members"]}
    assert members["u1"]["email"] == "ana@example.com"
    assert members["u1"]["name"] == "Ana Ruiz"
    assert members["u1"]["role"] == "viewer"
    assert members["u2"]["email"] == "bo@example.com"
    assert members["u2"]["role"] == "admin"


def test_department_members_rejects_lite_user_outside_management(monkeypatch):
    client = _Client(_store())
    _patch_departments(
        monkeypatch,
        client,
        {"is_org_admin": False, "managed_department_ids": [], "member_department_ids": ["d1"]},
    )
    with pytest.raises(HTTPException) as exc:
        departments_router.list_department_members(
            "d1", current_user={"user_id": "u1"}, org_id=ORG, settings=MagicMock()
        )
    assert exc.value.status_code == 403


def test_department_members_scoped_to_org(monkeypatch):
    client = _Client(_store())
    _patch_departments(
        monkeypatch,
        client,
        {"is_org_admin": True, "managed_department_ids": [], "member_department_ids": []},
    )
    with pytest.raises(HTTPException) as exc:
        departments_router.list_department_members(
            "dx", current_user={"user_id": "admin"}, org_id=ORG, settings=MagicMock()
        )
    assert exc.value.status_code == 404
