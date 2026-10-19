"""Settings redesign: profile metadata, sessions, org list counts, role counts, pending invites."""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock
from uuid import UUID

import pytest
from fastapi import HTTPException

from app.routers import auth as auth_router
from app.routers import org as org_router

USER = "11111111-1111-1111-1111-111111111111"
ORG = "22222222-2222-2222-2222-222222222222"
ORG_B = "33333333-3333-3333-3333-333333333333"
INVITEE = "44444444-4444-4444-4444-444444444444"


class _Resp:
    def __init__(self, data: list[dict[str, Any]], count: int | None = None):
        self.data = data
        self.error = None
        self.count = count


class _Query:
    def __init__(self, client: "_Client", name: str):
        self.client = client
        self.name = name
        self.filters: list[tuple[str, str, Any]] = []
        self.op = "select"
        self.payload: Any = None
        self.counted = False

    def schema(self, *_a):
        return self

    def select(self, *_a, count=None, **_k):
        self.counted = count == "exact"
        return self

    def eq(self, key, value):
        self.filters.append(("eq", key, value))
        return self

    def neq(self, key, value):
        self.filters.append(("neq", key, value))
        return self

    def in_(self, key, values):
        self.filters.append(("in", key, list(values)))
        return self

    def order(self, *_a, **_k):
        return self

    def limit(self, *_a):
        return self

    def update(self, payload):
        self.op, self.payload = "update", payload
        return self

    def delete(self):
        self.op = "delete"
        return self

    def _match(self, row):
        for kind, key, value in self.filters:
            if kind == "eq" and str(row.get(key)) != str(value):
                return False
            if kind == "neq" and str(row.get(key)) == str(value):
                return False
            if kind == "in" and str(row.get(key)) not in {str(v) for v in value}:
                return False
        return True

    def execute(self):
        self.client.calls.append((self.name, self.op, list(self.filters)))
        rows = [r for r in self.client.store.get(self.name, []) if self._match(r)]
        if self.op == "update":
            for r in rows:
                r.update(self.payload)
            return _Resp(rows)
        if self.op == "delete":
            for r in rows:
                self.client.store[self.name].remove(r)
            return _Resp(rows)
        if self.counted:
            return _Resp(rows[:1], count=len(rows))
        return _Resp([dict(r) for r in rows])


class _Client:
    def __init__(self, store: dict[str, list[dict[str, Any]]], auth_users: dict[str, Any] | None = None):
        self.store = store
        self.calls: list[tuple[str, str, list]] = []
        self.auth_users = auth_users or {}
        self.auth = SimpleNamespace(admin=MagicMock())
        self.auth.admin.get_user_by_id.side_effect = self._get_user
        self.auth.admin.update_user_by_id.side_effect = self._update_user

    def _get_user(self, user_id):
        if user_id not in self.auth_users:
            raise RuntimeError("User not found")
        return SimpleNamespace(user=self.auth_users[user_id])

    def _update_user(self, user_id, attrs):
        user = self.auth_users[user_id]
        meta = dict(user.user_metadata or {})
        meta.update(attrs["user_metadata"])
        user.user_metadata = meta
        return SimpleNamespace(user=user)

    def table(self, name):
        return _Query(self, name)

    def schema(self, _name):
        return self


def _auth_user(**kwargs):
    base = {
        "email": "cesar@example.com",
        "user_metadata": {},
        "email_confirmed_at": "2026-01-01T00:00:00Z",
        "invited_at": None,
        "last_sign_in_at": "2026-10-01T00:00:00Z",
        "confirmed_at": None,
    }
    base.update(kwargs)
    return SimpleNamespace(**base)


@pytest.fixture(autouse=True)
def _no_cache_invalidation(monkeypatch):
    monkeypatch.setattr(auth_router, "invalidate_user_state", lambda *_a, **_k: None)


def _use(monkeypatch, module, client):
    monkeypatch.setattr(module, "shared_service_client", lambda *_a, **_k: client)


# ---------- profile ----------


def test_profile_fields_saved_to_auth_metadata_without_touching_users(monkeypatch):
    client = _Client(
        {"users": [{"auth_user_id": USER, "full_name": "Old"}]},
        {USER: _auth_user(user_metadata={"full_name": "OAuth name", "gravitre_profile": {"bio": "Hi"}})},
    )
    _use(monkeypatch, auth_router, client)
    body = auth_router.UserProfileUpdateRequest(
        phone="+1 555 0100",
        timezone="America/Chicago",
        location="  ",
        preferences=auth_router.ProfilePreferences(theme="system", compact_tables=True),
    )
    result = auth_router.update_me(body, {"user_id": USER, "email": "cesar@example.com"}, MagicMock())

    meta = client.auth_users[USER].user_metadata
    assert meta["full_name"] == "OAuth name"  # provider metadata untouched
    assert meta["gravitre_profile"] == {
        "bio": "Hi",
        "phone": "+1 555 0100",
        "timezone": "America/Chicago",
        "preferences": {"theme": "system", "compact_tables": True},
    }
    assert result["phone"] == "+1 555 0100"
    assert result["location"] is None
    assert result["preferences"] == {"theme": "system", "compact_tables": True}
    assert not any(name == "users" for name, _op, _f in client.calls)


def test_preferences_merge_keeps_earlier_choices(monkeypatch):
    client = _Client(
        {},
        {USER: _auth_user(user_metadata={"gravitre_profile": {"preferences": {"theme": "dark", "compact_tables": True}}})},
    )
    _use(monkeypatch, auth_router, client)
    body = auth_router.UserProfileUpdateRequest(preferences=auth_router.ProfilePreferences(compact_tables=False))
    result = auth_router.update_me(body, {"user_id": USER}, MagicMock())
    assert result["preferences"] == {"theme": "dark", "compact_tables": False}


def test_profile_save_refuses_when_metadata_cannot_be_read(monkeypatch):
    client = _Client({}, {})
    _use(monkeypatch, auth_router, client)
    body = auth_router.UserProfileUpdateRequest(phone="1")
    with pytest.raises(HTTPException) as exc:
        auth_router.update_me(body, {"user_id": USER}, MagicMock())
    assert exc.value.status_code == 502
    client.auth.admin.update_user_by_id.assert_not_called()


def test_name_and_profile_fields_saved_together(monkeypatch):
    client = _Client({"users": [{"auth_user_id": USER, "full_name": "Old"}]}, {USER: _auth_user()})
    _use(monkeypatch, auth_router, client)
    body = auth_router.UserProfileUpdateRequest(full_name="New Name", bio="Builder")
    result = auth_router.update_me(body, {"user_id": USER}, MagicMock())
    assert client.store["users"][0]["full_name"] == "New Name"
    assert result["full_name"] == "New Name"
    assert result["bio"] == "Builder"


def test_load_auth_profile_reports_email_confirmation():
    client = _Client({}, {USER: _auth_user(email_confirmed_at=None, confirmed_at=None)})
    assert auth_router._load_auth_profile(client, USER)["email_confirmed"] is False
    client.auth_users[USER].email_confirmed_at = "2026-01-01T00:00:00Z"
    assert auth_router._load_auth_profile(client, USER)["email_confirmed"] is True
    assert auth_router._load_auth_profile(client, "missing") is None


def test_profile_fields_defaults():
    fields = auth_router._profile_fields({"phone": "", "preferences": {"theme": "neon"}})
    assert fields["phone"] is None
    assert fields["preferences"] == {"theme": None, "compact_tables": False}


# ---------- sessions ----------


def _request(token="tok", ua="Mozilla/5.0"):
    req = MagicMock()
    req.headers = {"authorization": f"Bearer {token}", "user-agent": ua}
    req.client = SimpleNamespace(host="10.0.0.1")
    return req


def test_sessions_mark_current_from_token_session_id(monkeypatch):
    client = _Client(
        {
            "sessions": [
                {"id": "s-new", "user_id": USER, "ip": "1.1.1.1", "user_agent": "UA1", "updated_at": "2026-10-02"},
                {"id": "s-mine", "user_id": USER, "ip": "2.2.2.2", "user_agent": "UA2", "updated_at": "2026-10-01"},
            ]
        }
    )
    _use(monkeypatch, auth_router, client)
    monkeypatch.setattr(auth_router, "decode_supabase_jwt", lambda *_a: {"session_id": "s-mine"})
    result = auth_router.list_sessions(_request(), {"user_id": USER}, MagicMock())
    current = {s["id"]: s["current"] for s in result["sessions"]}
    assert current == {"s-new": False, "s-mine": True}
    assert result["sessions"][1]["user_agent"] == "UA2"


def test_revoke_all_keeps_the_current_session(monkeypatch):
    client = _Client(
        {
            "sessions": [
                {"id": "s-other", "user_id": USER},
                {"id": "s-mine", "user_id": USER},
            ]
        }
    )
    _use(monkeypatch, auth_router, client)
    monkeypatch.setattr(auth_router, "decode_supabase_jwt", lambda *_a: {"session_id": "s-mine"})
    result = auth_router.revoke_all_sessions(_request(), {"user_id": USER}, MagicMock())
    assert result == {"ok": True, "kept_current": True}
    assert [s["id"] for s in client.store["sessions"]] == ["s-mine"]


# ---------- organizations ----------


def test_list_organizations_returns_counts_and_plan(monkeypatch):
    client = _Client(
        {
            "organization_members": [
                {"id": "m1", "org_id": ORG, "user_id": USER, "role": "owner"},
                {"id": "m2", "org_id": ORG, "user_id": "u2", "role": "member"},
                {"id": "m3", "org_id": ORG_B, "user_id": USER, "role": "viewer"},
            ],
            "organizations": [
                {"id": ORG, "name": "Acme", "slug": "acme", "settings": {}, "created_at": "2026-03-01T00:00:00Z"},
                {"id": ORG_B, "name": "Beta", "slug": "beta", "settings": {}, "created_at": "2026-04-01T00:00:00Z"},
            ],
            "agents": [{"id": "a1", "org_id": ORG}, {"id": "a2", "org_id": ORG}],
            "workflows": [{"id": "w1", "org_id": ORG_B}],
            "org_billing": [{"org_id": ORG, "plan_code": "command", "billing_status": "active"}],
        }
    )
    _use(monkeypatch, org_router, client)
    result = org_router.list_organizations({"user_id": USER}, MagicMock())
    by_id = {row["id"]: row for row in result["organizations"]}
    assert by_id[ORG]["member_count"] == 2
    assert by_id[ORG]["agent_count"] == 2
    assert by_id[ORG]["workflow_count"] == 0
    assert by_id[ORG]["plan_name"] == "Command"
    assert by_id[ORG]["plan_status"] == "active"
    assert by_id[ORG]["role"] == "owner"
    assert by_id[ORG_B]["member_count"] == 1
    assert by_id[ORG_B]["workflow_count"] == 1
    assert by_id[ORG_B]["plan_name"] is None
    assert by_id[ORG_B]["created_at"] == "2026-04-01T00:00:00Z"


def test_org_count_is_none_when_unreadable(monkeypatch):
    class _Broken(_Client):
        def table(self, name):
            if name == "agents":
                raise RuntimeError("relation does not exist")
            return super().table(name)

    client = _Broken({"organization_members": [{"id": "m1", "org_id": ORG, "user_id": USER}]})
    counts = org_router._org_counts(client, [ORG])
    assert counts[ORG]["agent_count"] is None
    assert counts[ORG]["member_count"] == 1


# ---------- role permissions ----------


def test_role_permissions_include_areas_descriptions_and_people(monkeypatch):
    client = _Client(
        {
            "organization_members": [
                {"org_id": ORG, "role": "owner"},
                {"org_id": ORG, "role": "admin"},
                {"org_id": ORG, "role": "member"},
                {"org_id": ORG, "role": "Viewer"},
                {"org_id": ORG_B, "role": "member"},
            ]
        }
    )
    _use(monkeypatch, org_router, client)
    result = org_router.get_role_permissions({"user_id": USER}, ORG, MagicMock())
    assert result["member_counts"] == {"owner": 1, "admin": 1, "member": 1, "viewer": 1}
    assert result["role_descriptions"]["viewer"]
    assert {cap["area"] for cap in result["capabilities"]} == {"Insights", "Build", "Govern"}
    assert len(result["capabilities"]) == 9
    assert org_router.get_role_permissions({"user_id": USER}, None, MagicMock())["member_counts"] is None


# ---------- invites ----------


def _invite_store():
    return {
        "organization_members": [
            {"id": "m1", "org_id": ORG, "user_id": USER, "role": "owner", "created_at": "2026-01-01"},
            {"id": "m2", "org_id": ORG, "user_id": INVITEE, "role": "viewer", "created_at": "2026-10-10"},
        ]
    }


def _invite_users():
    return {
        USER: _auth_user(),
        INVITEE: _auth_user(
            email="new@example.com",
            invited_at="2026-10-10T00:00:00Z",
            email_confirmed_at=None,
            last_sign_in_at=None,
        ),
    }


def test_pending_invites_come_from_unaccepted_auth_users(monkeypatch):
    client = _Client(_invite_store(), _invite_users())
    _use(monkeypatch, org_router, client)
    result = org_router.list_pending_invites({"user_id": USER}, ORG, MagicMock())
    assert result["invites"] == [
        {"user_id": INVITEE, "email": "new@example.com", "role": "viewer", "invited_at": "2026-10-10T00:00:00Z"}
    ]
    assert result["checked"] == 2
    assert result["unchecked"] == 0


def test_pending_invites_require_membership(monkeypatch):
    client = _Client(_invite_store(), _invite_users())
    _use(monkeypatch, org_router, client)
    with pytest.raises(HTTPException) as exc:
        org_router.list_pending_invites({"user_id": "stranger"}, ORG, MagicMock())
    assert exc.value.status_code == 403


def test_resend_invite_sends_again_and_audits(monkeypatch):
    client = _Client(_invite_store(), _invite_users())
    _use(monkeypatch, org_router, client)
    audit = MagicMock()
    monkeypatch.setattr(org_router, "write_audit_event", audit)
    settings = MagicMock()
    settings.public_app_url = "https://gravitre.app"
    result = org_router.resend_invite(UUID(INVITEE), ({"user_id": USER}, ORG), settings)
    assert result == {"ok": True, "email": "new@example.com"}
    email, options = client.auth.admin.invite_user_by_email.call_args.args
    assert email == "new@example.com"
    assert options["data"]["invited_role"] == "viewer"
    assert options["redirect_to"].startswith("https://gravitre.app/")
    assert audit.call_args.kwargs["action"] == org_router.AUDIT_ORG_MEMBER_INVITE_RESENT


def test_resend_invite_refuses_accepted_members(monkeypatch):
    client = _Client(_invite_store(), _invite_users())
    _use(monkeypatch, org_router, client)
    with pytest.raises(HTTPException) as exc:
        org_router.resend_invite(UUID(USER), ({"user_id": USER}, ORG), MagicMock())
    assert exc.value.status_code == 409
    client.auth.admin.invite_user_by_email.assert_not_called()
