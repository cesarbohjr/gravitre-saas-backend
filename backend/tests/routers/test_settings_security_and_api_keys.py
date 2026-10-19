"""Settings > Security controls and Settings > API keys persist without a migration."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.routers import settings_api_keys as keys
from app.routers import settings_security as sec

ADMIN = ({"user_id": "admin-1"}, "org-1")


class _Query:
    def __init__(self, db: "_Db", table: str):
        self.db, self.table, self.filters, self.op, self.payload = db, table, {}, "select", None

    def select(self, *_a, **_k):
        return self

    def eq(self, column, value):
        self.filters[column] = value
        return self

    def order(self, *_a, **_k):
        return self

    def limit(self, *_a):
        return self

    def insert(self, payload):
        self.op, self.payload = "insert", payload
        return self

    def update(self, payload):
        self.op, self.payload = "update", payload
        return self

    def execute(self):
        rows = self.db.tables.setdefault(self.table, [])
        if self.op == "insert":
            row = {"id": f"key-{len(rows) + 1}", "created_at": "2026-10-18T00:00:00+00:00", **self.payload}
            rows.append(row)
            return MagicMock(data=[dict(row)], error=None)
        matched = [r for r in rows if all(r.get(k) == v for k, v in self.filters.items())]
        if self.op == "update":
            for r in matched:
                r.update(self.payload)
        return MagicMock(data=[dict(r) for r in matched], error=None)


class _Db:
    def __init__(self, settings: dict | None = None):
        self.tables: dict[str, list[dict]] = {"organizations": [{"id": "org-1", "settings": settings or {}}]}

    def table(self, name):
        return _Query(self, name)

    @property
    def org_settings(self) -> dict:
        return self.tables["organizations"][0]["settings"]


@pytest.fixture
def db():
    store = _Db({"timezone": "Europe/London"})
    with (
        patch("app.routers.settings_security.shared_service_client", return_value=store),
        patch("app.routers.settings_security.invalidate_org_state"),
        patch("app.routers.settings_security.write_audit_event") as sec_audit,
        patch("app.routers.settings_api_keys.shared_service_client", return_value=store),
        patch("app.routers.settings_api_keys.invalidate_org_state"),
        patch("app.routers.settings_api_keys.write_audit_event") as key_audit,
    ):
        store.sec_audit, store.key_audit = sec_audit, key_audit
        yield store


# ---------------------------------------------------------------- security

def test_security_defaults_are_all_off_and_not_enforced(db):
    out = sec.get_security_controls_route({"user_id": "u"}, "org-1", MagicMock())["security"]
    assert out["requireTwoFactor"] is False
    assert out["ipAllowlist"] == {"enabled": False, "ranges": []}
    assert out["sessionTimeout"] == "never"
    assert out["enforced"] == {"requireTwoFactor": False, "ipAllowlist": False, "sessionTimeout": False}


def test_security_update_merges_and_canonicalizes_ranges(db):
    body = sec.SecurityControlsUpdateRequest(
        requireTwoFactor=True,
        ipAllowlist=sec.IpAllowlistUpdate(enabled=True, ranges=["10.0.0.7/24", "192.168.1.5", "10.0.0.0/24", "2001:db8::/32"]),
        sessionTimeout="24h",
    )
    out = sec.update_security_controls_route(body, ADMIN, MagicMock())["security"]
    assert out["ipAllowlist"]["ranges"] == ["10.0.0.0/24", "192.168.1.5/32", "2001:db8::/32"]
    assert db.org_settings["timezone"] == "Europe/London"
    assert db.org_settings["securityControls"]["sessionTimeout"] == "24h"
    assert db.sec_audit.call_args.kwargs["action"] == "settings.security_updated"

    # A later partial update keeps the other controls.
    sec.update_security_controls_route(sec.SecurityControlsUpdateRequest(requireTwoFactor=False), ADMIN, MagicMock())
    assert db.org_settings["securityControls"]["ipAllowlist"]["enabled"] is True


@pytest.mark.parametrize(
    "body",
    [
        sec.SecurityControlsUpdateRequest(ipAllowlist=sec.IpAllowlistUpdate(ranges=["10.0.0.300/24"])),
        sec.SecurityControlsUpdateRequest(ipAllowlist=sec.IpAllowlistUpdate(ranges=["office"])),
        sec.SecurityControlsUpdateRequest(sessionTimeout="30m"),
    ],
)
def test_security_rejects_bad_values(db, body):
    with pytest.raises(HTTPException) as exc:
        sec.update_security_controls_route(body, ADMIN, MagicMock())
    assert exc.value.status_code == 400
    assert "securityControls" not in db.org_settings


# ---------------------------------------------------------------- api keys

def test_create_returns_secret_once_and_stores_only_hash(db):
    out = keys.create_api_key_route(keys.ApiKeyCreateRequest(name=" Warehouse ", scope="read_write", expires_in="30d"), ADMIN, MagicMock())
    created = out["apiKey"]
    secret = created["key"]
    assert secret.startswith("gv_live_")
    row = db.tables["api_keys"][0]
    assert row["key_hash"] == keys.hash_api_key(secret) and secret not in row.values()
    assert row["name"] == "Warehouse" and row["created_by"] == "admin-1"
    assert created["scope"] == "read_write" and created["last4"] == secret[-4:]
    policy = db.org_settings["apiKeyPolicies"][created["id"]]
    assert policy["scope"] == "read_write"
    assert datetime.fromisoformat(policy["expiresAt"]) > datetime.now(timezone.utc) + timedelta(days=29)

    listed = keys.list_api_keys_route(ADMIN, MagicMock())["apiKeys"]
    assert [k["id"] for k in listed] == [created["id"]]
    assert "key" not in listed[0] and listed[0]["expired"] is False


@pytest.mark.parametrize("scope,expires", [("admin", "30d"), ("read", "2y")])
def test_create_rejects_unknown_scope_or_expiry(db, scope, expires):
    with pytest.raises(HTTPException) as exc:
        keys.create_api_key_route(keys.ApiKeyCreateRequest(name="k", scope=scope, expires_in=expires), ADMIN, MagicMock())
    assert exc.value.status_code == 400
    assert not db.tables.get("api_keys")


def test_never_expiring_key_and_expiry_check():
    now = datetime(2026, 10, 18, tzinfo=timezone.utc)
    assert keys.expires_at_for("never") is None
    active = {"status": "active"}
    assert keys.api_key_is_usable(active, {"expiresAt": None}, now)
    assert not keys.api_key_is_usable(active, {"expiresAt": (now - timedelta(seconds=1)).isoformat()}, now)
    assert not keys.api_key_is_usable({"status": "revoked"}, {}, now)


def test_revoke_and_rotate(db):
    created = keys.create_api_key_route(keys.ApiKeyCreateRequest(name="k"), ADMIN, MagicMock())["apiKey"]
    rotated = keys.rotate_api_key_route(created["id"], ADMIN, MagicMock())["apiKey"]
    assert rotated["key"] != created["key"]
    assert db.tables["api_keys"][0]["key_hash"] == keys.hash_api_key(rotated["key"])
    assert db.org_settings["apiKeyPolicies"][created["id"]]["scope"] == "read"

    revoked = keys.update_api_key_status_route(keys.ApiKeyStatusRequest(id=created["id"]), ADMIN, MagicMock())["apiKey"]
    assert revoked["status"] == "revoked"
    assert db.key_audit.call_args.kwargs["action"] == "api_key.revoked"
    with pytest.raises(HTTPException):
        keys.rotate_api_key_route(created["id"], ADMIN, MagicMock())
    with pytest.raises(HTTPException) as missing:
        keys.update_api_key_status_route(keys.ApiKeyStatusRequest(id="nope"), ADMIN, MagicMock())
    assert missing.value.status_code == 404


def test_legacy_key_without_policy_reports_unknown_scope(db):
    db.tables["api_keys"] = [{"id": "old", "org_id": "org-1", "name": "Old", "key_prefix": "gva_live_", "status": "active"}]
    listed = keys.list_api_keys_route(ADMIN, MagicMock())["apiKeys"]
    assert listed[0]["scope"] is None and listed[0]["expires_at"] is None and listed[0]["expired"] is False
