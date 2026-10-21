"""Editable role permissions: validation, stored matrix and the require_capability gate."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.auth import dependencies as deps
from app.auth.org_role_permissions import (
    CAPABILITY_KEYS,
    RolePermissionsError,
    get_org_role_permissions_matrix,
    role_capabilities,
    stored_role_definitions,
    validate_role_definitions,
)

ORG = "11111111-1111-4111-8111-111111111111"


def _defaults():
    return [{k: v for k, v in row.items() if k != "custom"} for row in stored_role_definitions({})]


def test_defaults_match_the_published_matrix():
    rows = {row["key"]: row for row in stored_role_definitions({})}
    assert set(rows) == {"admin", "member", "viewer"}
    assert set(rows["admin"]["capabilities"]) == set(CAPABILITY_KEYS)
    assert "approve_writes" in rows["member"]["capabilities"]
    assert "approve_writes" not in rows["viewer"]["capabilities"]


def test_new_role_gets_a_key_and_admin_stays_full():
    roles = _defaults()
    roles[0]["capabilities"] = []  # admin can't be narrowed
    roles.append({"name": "Support lead", "description": "Answers tickets", "capabilities": ["run_ai_chat", "approve_writes"]})
    saved = validate_role_definitions(roles)
    by_key = {row["key"]: row for row in saved}
    assert by_key["support_lead"]["capabilities"] == ["run_ai_chat", "approve_writes"]
    assert set(by_key["admin"]["capabilities"]) == set(CAPABILITY_KEYS)
    settings = {"role_permissions": {"roles": saved}}
    assert role_capabilities(settings, "support_lead") == frozenset({"run_ai_chat", "approve_writes"})
    matrix = get_org_role_permissions_matrix(settings)
    assert matrix["custom_roles"] == ["support_lead"]
    assert matrix["locked_roles"] == ["admin"]
    assert matrix["role_names"]["support_lead"] == "Support lead"
    approve = next(cap for cap in matrix["capabilities"] if cap["key"] == "approve_writes")
    assert approve["access"]["support_lead"] is True


@pytest.mark.parametrize(
    "mutate, message",
    [
        (lambda roles: roles.pop(2), "Built in roles can't be deleted"),
        (lambda roles: roles.append({"name": "member", "capabilities": []}), "Two roles are named"),
        (lambda roles: roles.append({"name": "X", "capabilities": ["launch_rockets"]}), "Unknown capabilities"),
        (lambda roles: roles.append({"key": "owner", "name": "Boss", "capabilities": []}), "invalid key"),
        (lambda roles: roles.append({"name": " ", "capabilities": []}), "needs a name"),
    ],
)
def test_invalid_updates_are_refused(mutate, message):
    roles = _defaults()
    mutate(roles)
    with pytest.raises(RolePermissionsError, match=message):
        validate_role_definitions(roles)


def test_a_role_with_people_on_it_cannot_be_deleted():
    current = stored_role_definitions({"role_permissions": {"roles": _defaults() + [{"key": "ops", "name": "Ops", "capabilities": []}]}})
    with pytest.raises(RolePermissionsError, match="Move the people on Ops"):
        validate_role_definitions(_defaults(), member_counts={"ops": 2}, current=current)
    assert len(validate_role_definitions(_defaults(), member_counts={"ops": 0}, current=current)) == 3


# ------------------------------------------------------------ require_capability


class _Db:
    def __init__(self, role, settings=None):
        self.rows = {
            "organization_members": [{"org_id": ORG, "user_id": "u1", "role": role}],
            "organizations": [{"id": ORG, "settings": settings or {}}],
        }

    def table(self, name):
        db = self

        class _Q:
            filters: list = []

            def select(self, *_a, **_k):
                self.filters = []
                return self

            def eq(self, key, value):
                self.filters = [*self.filters, (key, str(value))]
                return self

            def limit(self, *_a):
                return self

            def execute(self):
                data = [r for r in db.rows.get(name, []) if all(str(r.get(k)) == v for k, v in self.filters)]
                return SimpleNamespace(data=data)

        return _Q()


def _call(monkeypatch, db, capability):
    monkeypatch.setattr(deps, "_get_cached_service_client", lambda _s: db)
    monkeypatch.setattr(deps, "is_platform_admin", lambda *_a: False)
    dep = deps.require_capability(capability)
    return asyncio.run(dep(current_user={"user_id": "u1"}, org_id=ORG, settings=SimpleNamespace()))


def test_require_capability_is_one_dependency_per_key():
    assert deps.require_capability("approve_writes") is deps.require_capability("approve_writes")
    with pytest.raises(ValueError):
        deps.require_capability("launch_rockets")


def test_defaults_let_members_approve_but_not_viewers(monkeypatch):
    assert _call(monkeypatch, _Db("member"), "approve_writes") == ({"user_id": "u1"}, ORG)
    with pytest.raises(HTTPException) as exc:
        _call(monkeypatch, _Db("viewer"), "approve_writes")
    assert exc.value.status_code == 403


def test_saved_matrix_is_enforced(monkeypatch):
    roles = _defaults()
    roles[1]["capabilities"] = []  # member loses everything
    roles.append({"key": "auditor", "name": "Auditor", "capabilities": ["audit_export"]})
    settings = {"role_permissions": {"roles": validate_role_definitions(roles)}}
    with pytest.raises(HTTPException):
        _call(monkeypatch, _Db("member", settings), "approve_writes")
    assert _call(monkeypatch, _Db("auditor", settings), "audit_export")[1] == ORG
    with pytest.raises(HTTPException):
        _call(monkeypatch, _Db("auditor", settings), "manage_connectors")
    assert _call(monkeypatch, _Db("admin", settings), "team_roles")[1] == ORG


def test_role_removed_from_the_matrix_has_no_capabilities(monkeypatch):
    with pytest.raises(HTTPException):
        _call(monkeypatch, _Db("ghost_role"), "run_ai_chat")
