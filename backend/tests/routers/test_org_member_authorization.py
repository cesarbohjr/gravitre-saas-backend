"""Membership changes: admin only, owners protected, an owner always remains.

Drives the real org routers with an in-memory organization_members table, as a
caller authenticated via get_current_user / require_admin overrides.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user, require_admin
from app.config import get_settings
from app.routers import org as org_router

ORG = "11111111-1111-4111-8111-111111111111"
OTHER_ORG = "99999999-9999-4999-8999-999999999999"
OWNER = "aaaaaaaa-0000-4000-8000-000000000001"
OWNER2 = "aaaaaaaa-0000-4000-8000-000000000002"
ADMIN = "aaaaaaaa-0000-4000-8000-000000000003"
MEMBER = "aaaaaaaa-0000-4000-8000-000000000004"
OUTSIDER = "aaaaaaaa-0000-4000-8000-000000000005"


class _Query:
    def __init__(self, db: "_Db", table: str) -> None:
        self.db, self.table = db, table
        self.filters: list[tuple[str, Any]] = []
        self.op = "select"
        self.payload: Any = None

    def select(self, *_a, **_k):
        return self

    def eq(self, key, value):
        self.filters.append((key, str(value)))
        return self

    def limit(self, *_a):
        return self

    def update(self, payload):
        self.op, self.payload = "update", payload
        return self

    def delete(self):
        self.op = "delete"
        return self

    def insert(self, payload):
        self.op, self.payload = "insert", payload
        return self

    def _match(self, row):
        return all(str(row.get(k)) == v for k, v in self.filters)

    def execute(self):
        rows = self.db.tables.setdefault(self.table, [])
        if self.op == "select":
            return SimpleNamespace(data=[dict(r) for r in rows if self._match(r)])
        if self.op == "update":
            hit = [r for r in rows if self._match(r)]
            for r in hit:
                r.update(self.payload)
            return SimpleNamespace(data=[dict(r) for r in hit])
        if self.op == "delete":
            hit = [r for r in rows if self._match(r)]
            self.db.tables[self.table] = [r for r in rows if not self._match(r)]
            return SimpleNamespace(data=hit)
        rows.append(dict(self.payload))
        return SimpleNamespace(data=[self.payload])


class _Db:
    def __init__(self) -> None:
        self.tables: dict[str, list[dict]] = {
            "organization_members": [
                {"id": "bbbbbbbb-0000-4000-8000-000000000001", "org_id": ORG, "user_id": OWNER, "role": "owner"},
                {"id": "bbbbbbbb-0000-4000-8000-000000000003", "org_id": ORG, "user_id": ADMIN, "role": "admin"},
                {"id": "bbbbbbbb-0000-4000-8000-000000000004", "org_id": ORG, "user_id": MEMBER, "role": "member"},
                {"id": "bbbbbbbb-0000-4000-8000-000000000005", "org_id": OTHER_ORG, "user_id": OUTSIDER, "role": "member"},
            ],
            "organizations": [{"id": ORG, "name": "A"}],
        }

    def table(self, name):
        return _Query(self, name)

    def role(self, user_id, org=ORG):
        for r in self.tables["organization_members"]:
            if r["user_id"] == user_id and r["org_id"] == org:
                return r["role"]
        return None


@pytest.fixture
def env(monkeypatch):
    db = _Db()
    audits: list[dict] = []
    monkeypatch.setattr(org_router, "shared_service_client", lambda *_a, **_k: db)
    monkeypatch.setattr(org_router, "write_audit_event", lambda client, **kw: audits.append(kw))
    monkeypatch.setattr(org_router, "invalidate_org_and_users", lambda *a, **k: None)
    monkeypatch.setattr(org_router, "invalidate_org_state", lambda *a, **k: None)
    state = {"user": ADMIN}
    app = FastAPI()
    app.include_router(org_router.router)
    app.include_router(org_router.organizations_router)
    app.dependency_overrides[get_settings] = lambda: SimpleNamespace()
    app.dependency_overrides[get_current_user] = lambda: {"user_id": state["user"]}

    def _admin():
        role = db.role(state["user"])
        if role not in {"owner", "admin"}:
            from fastapi import HTTPException

            raise HTTPException(status_code=403, detail="Admin role required")
        return ({"user_id": state["user"]}, ORG)

    app.dependency_overrides[require_admin] = _admin
    return TestClient(app), db, state, audits


def _as(state, user):
    state["user"] = user


# ------------------------------------------------------------ role changes


def test_member_cannot_change_roles(env):
    client, db, state, _ = env
    _as(state, MEMBER)
    assert client.patch(f"/api/organizations/{ORG}/members/{MEMBER}", json={"role": "admin"}).status_code == 403
    assert db.role(MEMBER) == "member"


def test_admin_cannot_demote_an_owner(env):
    client, db, state, _ = env
    _as(state, ADMIN)
    assert client.patch(f"/api/organizations/{ORG}/members/{OWNER}", json={"role": "member"}).status_code == 403
    assert client.patch("/api/org/members/bbbbbbbb-0000-4000-8000-000000000001", json={"role": "member"}).status_code == 403
    assert db.role(OWNER) == "owner"


def test_admin_changes_a_member_role_and_it_is_audited(env):
    client, db, state, audits = env
    _as(state, ADMIN)
    resp = client.patch(f"/api/organizations/{ORG}/members/{MEMBER}", json={"role": "viewer"})
    assert resp.status_code == 200, resp.text
    assert db.role(MEMBER) == "viewer"
    assert audits[-1]["action"] == org_router.AUDIT_ORG_MEMBER_UPDATED
    assert audits[-1]["metadata"] == {"old_role": "member", "new_role": "viewer"}


def test_owner_cannot_demote_the_last_owner(env):
    client, db, state, _ = env
    _as(state, OWNER)
    resp = client.patch(f"/api/organizations/{ORG}/members/{OWNER}", json={"role": "admin"})
    assert resp.status_code == 400
    assert db.role(OWNER) == "owner"


def test_owner_can_demote_another_owner_when_one_remains(env):
    client, db, state, _ = env
    db.tables["organization_members"].append({"id": "bbbbbbbb-0000-4000-8000-000000000012", "org_id": ORG, "user_id": OWNER2, "role": "owner"})
    _as(state, OWNER)
    assert client.patch(f"/api/organizations/{ORG}/members/{OWNER2}", json={"role": "admin"}).status_code == 200
    assert db.role(OWNER2) == "admin"


def test_cross_org_target_is_not_found(env):
    client, db, state, _ = env
    _as(state, ADMIN)
    assert client.patch(f"/api/organizations/{ORG}/members/{OUTSIDER}", json={"role": "admin"}).status_code == 404
    assert client.delete(f"/api/organizations/{ORG}/members/{OUTSIDER}").status_code == 404
    assert client.delete("/api/org/members/bbbbbbbb-0000-4000-8000-000000000005").status_code == 404
    assert db.role(OUTSIDER, OTHER_ORG) == "member"


# ----------------------------------------------------------------- removals


def test_member_cannot_remove_anyone(env):
    client, db, state, _ = env
    _as(state, MEMBER)
    assert client.delete(f"/api/organizations/{ORG}/members/{ADMIN}").status_code == 403
    assert db.role(ADMIN) == "admin"


def test_admin_cannot_remove_an_owner(env):
    client, db, state, _ = env
    _as(state, ADMIN)
    assert client.delete(f"/api/organizations/{ORG}/members/{OWNER}").status_code == 403
    assert client.delete("/api/org/members/bbbbbbbb-0000-4000-8000-000000000001").status_code == 403
    assert db.role(OWNER) == "owner"


def test_admin_removes_a_member_and_it_is_audited(env):
    client, db, state, audits = env
    _as(state, ADMIN)
    assert client.delete(f"/api/organizations/{ORG}/members/{MEMBER}").status_code == 200
    assert db.role(MEMBER) is None
    assert audits[-1]["action"] == org_router.AUDIT_ORG_MEMBER_REMOVED


def test_last_owner_cannot_remove_themselves(env):
    client, db, state, _ = env
    _as(state, OWNER)
    assert client.delete("/api/org/members/bbbbbbbb-0000-4000-8000-000000000001").status_code == 400
    assert db.role(OWNER) == "owner"


# --------------------------------------------------------- transfer / delete


def test_admin_cannot_transfer_ownership(env):
    client, db, state, _ = env
    _as(state, ADMIN)
    assert client.post(f"/api/organizations/{ORG}/transfer", json={"new_owner_id": ADMIN}).status_code == 403
    assert db.role(ADMIN) == "admin" and db.role(OWNER) == "owner"


def test_owner_transfers_ownership(env):
    client, db, state, audits = env
    _as(state, OWNER)
    assert client.post(f"/api/organizations/{ORG}/transfer", json={"new_owner_id": ADMIN}).status_code == 200
    assert db.role(ADMIN) == "owner" and db.role(OWNER) == "admin"
    assert audits[-1]["metadata"]["ownership_transfer"] is True


def test_transfer_to_someone_outside_the_org_is_not_found(env):
    client, db, state, _ = env
    _as(state, OWNER)
    assert client.post(f"/api/organizations/{ORG}/transfer", json={"new_owner_id": OUTSIDER}).status_code == 404


def test_only_an_owner_deletes_the_organization(env):
    client, db, state, _ = env
    _as(state, ADMIN)
    assert client.delete(f"/api/organizations/{ORG}").status_code == 403
    assert db.tables["organizations"]
    _as(state, OWNER)
    assert client.delete(f"/api/organizations/{ORG}").status_code == 200
