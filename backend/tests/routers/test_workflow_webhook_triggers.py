"""Signed workflow webhook triggers: fail closed, replay safe, admin-only config."""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.dependencies import require_admin
from app.config import get_settings
from app.connectors.crypto import decrypt_secret, encrypt_secret
from app.routers.webhooks import workflow_triggers as wt
from app.services.execution_service import get_execution_service

KEY = "a" * 64
ORG = "11111111-1111-1111-1111-111111111111"
OTHER_ORG = "22222222-2222-2222-2222-222222222222"
WF = "33333333-3333-3333-3333-333333333333"
SECRET = "whsec_test_secret"


class _Query:
    def __init__(self, db: "_DB", table: str) -> None:
        self.db, self.table, self.op, self.payload = db, table, "select", None

    def select(self, *_a, **_k):
        return self

    def eq(self, *_a, **_k):
        return self

    def in_(self, *_a, **_k):
        return self

    def limit(self, *_a, **_k):
        return self

    def order(self, *_a, **_k):
        return self

    def update(self, payload):
        self.op, self.payload = "update", payload
        return self

    def insert(self, payload):
        self.op, self.payload = "insert", payload
        return self

    def execute(self):
        if self.op == "update":
            self.db.updates.append((self.table, self.payload))
            if self.table == "workflow_defs":
                self.db.workflow["webhook_config"] = self.payload["webhook_config"]
            return SimpleNamespace(data=[])
        if self.op == "insert":
            self.db.inserts.append((self.table, self.payload))
            return SimpleNamespace(data=[])
        if self.table == "workflow_defs":
            return SimpleNamespace(data=[dict(self.db.workflow)])
        if self.table == "organization_members":
            return SimpleNamespace(data=list(self.db.members))
        return SimpleNamespace(data=[])


class _DB:
    def __init__(self, config: dict[str, Any], org_id: str = ORG) -> None:
        self.workflow = {
            "id": WF,
            "name": "wf",
            "org_id": org_id,
            "status": "active",
            "definition": {"schema_version": "v1", "steps": []},
            "webhook_config": config,
        }
        self.updates: list = []
        self.inserts: list = []
        self.members: list = [
            {"user_id": "member-1", "role": "member", "created_at": "2026-01-01"},
            {"user_id": "owner-1", "role": "owner", "created_at": "2026-01-02"},
            {"user_id": "admin-1", "role": "admin", "created_at": "2026-01-03"},
        ]

    def table(self, name: str) -> _Query:
        return _Query(self, name)


def _settings(**over: Any) -> SimpleNamespace:
    base = {"connector_secrets_encryption_key": KEY, "webhook_trusted_proxy_hops": 0}
    base.update(over)
    return SimpleNamespace(**base)


@pytest.fixture
def harness(monkeypatch):
    state: dict[str, Any] = {"settings": _settings(), "runs": [], "seen": set()}

    def make(config: dict[str, Any], *, org_id: str = ORG, admin_org: str | None = ORG):
        db = _DB(config, org_id)
        state["db"] = db
        monkeypatch.setattr(wt, "get_supabase_client", lambda _s: db)
        monkeypatch.setattr(wt, "resolve_entitlements", lambda _s, _o: {"features": {"custom_webhooks": True}})

        async def fake_start(_settings, _client, **kw):
            state["runs"].append(kw)
            key = (kw.get("provider_event_id"), kw["workflow_id"])
            if kw.get("provider_event_id") and key in state["seen"]:
                return {"workflow_id": kw["workflow_id"], "status": "skipped", "reason": "duplicate_event"}
            state["seen"].add(key)
            return {"workflow_id": kw["workflow_id"], "status": "running", "run_id": "run-1"}

        import app.services.event_triggered_runs as etr

        monkeypatch.setattr(etr, "start_event_triggered_run", fake_start)
        import app.workflows.audit as audit

        monkeypatch.setattr(audit, "write_audit_event", lambda *a, **k: state.setdefault("audits", []).append(k))

        app = FastAPI()
        app.include_router(wt.router)
        app.dependency_overrides[get_settings] = lambda: state["settings"]
        app.dependency_overrides[get_execution_service] = lambda: None
        if admin_org is not None:
            app.dependency_overrides[require_admin] = lambda: ({"user_id": "admin-1"}, admin_org)
        else:
            from fastapi import HTTPException

            def deny():
                raise HTTPException(status_code=403, detail="Admin role required")

            app.dependency_overrides[require_admin] = deny
        return TestClient(app, client=("203.0.113.9", 5000))

    state["make"] = make
    return state


def _signed(body: bytes, secret: str = SECRET, ts: int | None = None, event_id: str | None = "evt-1"):
    ts = int(time.time()) if ts is None else ts
    sig = hmac.new(secret.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
    headers = {"X-Gravitre-Signature": f"sha256={sig}", "X-Gravitre-Timestamp": str(ts)}
    if event_id is not None:
        headers[wt.EVENT_ID_HEADER] = event_id
    return headers


def _enc_config(**extra: Any) -> dict[str, Any]:
    cfg = {"enabled": True, "secret_encrypted": encrypt_secret(SECRET, KEY)}
    cfg.update(extra)
    return cfg


BODY = json.dumps({"ticket": 42}).encode()


def test_no_secret_configured_fails_closed(harness):
    client = harness["make"]({"enabled": True})
    r = client.post(f"/api/webhooks/triggers/{WF}", content=BODY, headers=_signed(BODY))
    assert r.status_code == 401
    assert harness["runs"] == []


def test_missing_timestamp_is_refused(harness):
    client = harness["make"](_enc_config())
    sig = hmac.new(SECRET.encode(), BODY, hashlib.sha256).hexdigest()
    r = client.post(
        f"/api/webhooks/triggers/{WF}",
        content=BODY,
        headers={"X-Gravitre-Signature": sig, wt.EVENT_ID_HEADER: "evt-1"},
    )
    assert r.status_code == 401
    assert harness["runs"] == []


def test_stale_timestamp_is_refused(harness):
    client = harness["make"](_enc_config())
    r = client.post(f"/api/webhooks/triggers/{WF}", content=BODY, headers=_signed(BODY, ts=int(time.time()) - 3600))
    assert r.status_code == 401


def test_wrong_secret_is_refused(harness):
    client = harness["make"](_enc_config())
    r = client.post(f"/api/webhooks/triggers/{WF}", content=BODY, headers=_signed(BODY, secret="whsec_other"))
    assert r.status_code == 401


def test_missing_event_id_is_refused(harness):
    client = harness["make"](_enc_config())
    r = client.post(f"/api/webhooks/triggers/{WF}", content=BODY, headers=_signed(BODY, event_id=None))
    assert r.status_code == 400
    assert harness["runs"] == []


def test_signed_request_runs_and_passes_event_id(harness):
    client = harness["make"](_enc_config())
    r = client.post(f"/api/webhooks/triggers/{WF}", content=BODY, headers=_signed(BODY))
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "running"
    assert harness["runs"][0]["provider_event_id"] == "evt-1"
    assert harness["runs"][0]["parameters"] == {"ticket": 42}


def test_replayed_event_id_starts_no_second_run(harness):
    client = harness["make"](_enc_config())
    first = client.post(f"/api/webhooks/triggers/{WF}", content=BODY, headers=_signed(BODY))
    again = client.post(f"/api/webhooks/triggers/{WF}", content=BODY, headers=_signed(BODY))
    assert first.json()["status"] == "running"
    assert again.status_code == 200
    assert again.json()["status"] == "duplicate"
    assert again.json()["run_id"] == ""


def test_legacy_plaintext_secret_still_verifies(harness):
    client = harness["make"]({"enabled": True, "secret": SECRET})
    r = client.post(f"/api/webhooks/triggers/{WF}", content=BODY, headers=_signed(BODY))
    assert r.status_code == 200


def test_spoofed_forwarded_for_is_ignored_without_trusted_hops(harness):
    client = harness["make"](_enc_config(allowed_ips=["198.51.100.7"]))
    headers = _signed(BODY) | {"X-Forwarded-For": "198.51.100.7"}
    r = client.post(f"/api/webhooks/triggers/{WF}", content=BODY, headers=headers)
    assert r.status_code == 403
    assert harness["runs"] == []


def test_trusted_hop_uses_proxy_appended_address(harness):
    harness["settings"] = _settings(webhook_trusted_proxy_hops=1)
    client = harness["make"](_enc_config(allowed_ips=["198.51.100.7"]))
    # The caller forged the leftmost entry; our proxy appended the real address.
    spoofed = _signed(BODY, event_id="evt-a") | {"X-Forwarded-For": "198.51.100.7, 192.0.2.50"}
    assert client.post(f"/api/webhooks/triggers/{WF}", content=BODY, headers=spoofed).status_code == 403
    real = _signed(BODY, event_id="evt-b") | {"X-Forwarded-For": "10.0.0.1, 198.51.100.7"}
    assert client.post(f"/api/webhooks/triggers/{WF}", content=BODY, headers=real).status_code == 200


def test_get_config_requires_admin(harness):
    client = harness["make"](_enc_config(), admin_org=None)
    assert client.get(f"/api/webhooks/triggers/{WF}/config").status_code == 403


def test_get_config_hides_other_org_workflow_and_never_returns_secret(harness):
    client = harness["make"](_enc_config(), org_id=OTHER_ORG)
    assert client.get(f"/api/webhooks/triggers/{WF}/config").status_code == 404

    client = harness["make"](_enc_config())
    body = client.get(f"/api/webhooks/triggers/{WF}/config").json()
    assert body["has_secret"] is True
    assert "secret" not in body and "secret_encrypted" not in body
    assert body["signing"]["event_id_header"] == wt.EVENT_ID_HEADER


def test_put_config_requires_admin(harness):
    client = harness["make"]({"enabled": False}, admin_org=None)
    r = client.put(f"/api/webhooks/triggers/{WF}/config", json={"enabled": True})
    assert r.status_code == 403
    assert harness["db"].updates == []


def test_enabling_generates_secret_once_and_stores_it_encrypted(harness):
    client = harness["make"]({"enabled": False})
    r = client.put(f"/api/webhooks/triggers/{WF}/config", json={"enabled": True})
    assert r.status_code == 200, r.text
    secret = r.json()["secret"]
    assert secret.startswith("whsec_")
    stored = harness["db"].workflow["webhook_config"]
    assert stored["secret"] is None
    assert secret not in json.dumps(stored)
    assert decrypt_secret(stored["secret_encrypted"], KEY) == secret
    assert harness["audits"][0]["action"] == "workflow.webhook_config.updated"
    assert harness["audits"][0]["metadata"]["secret_rotated"] is True
    assert secret not in json.dumps(harness["audits"])

    # Not returned again on read.
    assert "secret" not in client.get(f"/api/webhooks/triggers/{WF}/config").json()

    # And the new secret signs triggers.
    ok = client.post(f"/api/webhooks/triggers/{WF}", content=BODY, headers=_signed(BODY, secret=secret))
    assert ok.status_code == 200, ok.text


def test_rotation_replaces_legacy_plaintext_and_old_secret_stops_working(harness):
    client = harness["make"]({"enabled": True, "secret": SECRET})
    r = client.put(f"/api/webhooks/triggers/{WF}/config", json={"rotate_secret": True})
    new = r.json()["secret"]
    assert new != SECRET
    assert harness["db"].workflow["webhook_config"]["secret"] is None
    old = client.post(f"/api/webhooks/triggers/{WF}", content=BODY, headers=_signed(BODY, event_id="e1"))
    assert old.status_code == 401
    fresh = client.post(f"/api/webhooks/triggers/{WF}", content=BODY, headers=_signed(BODY, secret=new, event_id="e2"))
    assert fresh.status_code == 200


def test_cannot_store_secret_without_encryption_key(harness):
    harness["settings"] = _settings(connector_secrets_encryption_key="")
    client = harness["make"]({"enabled": False})
    r = client.put(f"/api/webhooks/triggers/{WF}/config", json={"enabled": True})
    assert r.status_code == 400
    assert harness["db"].updates == []


def test_watcher_verify_signature_keeps_optional_timestamp():
    body = b"{}"
    sig = hmac.new(b"s", body, hashlib.sha256).hexdigest()
    assert wt.verify_signature(body, sig, "s") is True
    assert wt.verify_signature(body, sig, "s", require_timestamp=True) is False


def test_run_is_attributed_to_configuring_admin(harness):
    client = harness["make"](_enc_config(configured_by="admin-1"))
    client.post(f"/api/webhooks/triggers/{WF}", content=BODY, headers=_signed(BODY))
    assert harness["runs"][0]["actor_id"] == "admin-1"


def test_run_falls_back_to_earliest_owner_not_arbitrary_member(harness):
    client = harness["make"](_enc_config())
    client.post(f"/api/webhooks/triggers/{WF}", content=BODY, headers=_signed(BODY))
    assert harness["runs"][0]["actor_id"] == "owner-1"


def test_no_accountable_member_refuses_run(harness):
    client = harness["make"](_enc_config(configured_by="gone"))
    harness["db"].members = [{"user_id": "v1", "role": "viewer", "created_at": "2026-01-01"}]
    r = client.post(f"/api/webhooks/triggers/{WF}", content=BODY, headers=_signed(BODY))
    assert r.status_code == 409
    assert harness["runs"] == []


def test_put_config_records_configuring_admin(harness):
    client = harness["make"]({"enabled": False})
    client.put(f"/api/webhooks/triggers/{WF}/config", json={"enabled": True})
    assert harness["db"].workflow["webhook_config"]["configured_by"] == "admin-1"
