"""No-network HubSpot existing live portal test: approval, idempotency, cleanup."""
from __future__ import annotations

import importlib
import urllib.error
from pathlib import Path

import pytest

PORTAL = "343328749"


@pytest.fixture
def hubspot(monkeypatch):
    scripts = Path(__file__).resolve().parents[2] / "scripts"
    monkeypatch.syspath_prepend(str(scripts))
    return importlib.import_module("p27_hubspot_sandbox_readback")


def _fake_hubspot_api(*, portal=PORTAL, account_type="STANDARD",
                      mismatch=False, duplicate=False, cleanup_fails=False,
                      delete_fails=False, first_upsert_fails=False,
                      applied_but_response_lost=False, foreign_receipt_id=False):
    seen = []
    state = {"deleted": False, "properties": None, "created": False}

    def response(url, *, token, method, payload=None):
        seen.append((method, url, payload))
        if url.endswith("/account-info/v3/details") and method == "GET":
            return {"portalId": int(portal), "accountType": account_type}
        if url.endswith("/crm/v3/objects/contacts/batch/upsert") and method == "POST":
            assert len(payload["inputs"]) == 1
            item = payload["inputs"][0]
            assert item["idProperty"] == "email"
            assert item["id"] == item["properties"]["email"]
            assert item["properties"]["email"].startswith("p27qa")
            assert "objectWriteTraceId" not in item
            assert item["properties"]["lastname"] == item["properties"]["email"].split("@", 1)[0]
            state["properties"] = dict(item["properties"])
            count = len([m for m, _, _ in seen if m == "POST"])
            if first_upsert_fails and count == 1:
                if applied_but_response_lost:
                    state["created"] = True
                raise RuntimeError("upsert network timeout")
            state["created"] = True
            return {"status": "COMPLETE",
                    "results": [{"id": "90002" if foreign_receipt_id or (duplicate and count > 1) else "90001"}]}
        if "idProperty=email" in url and method == "GET":
            if not state["created"] or state["deleted"]:
                raise urllib.error.HTTPError(url, 404, "Not Found", None, None)
            return {"id": "90001", "properties": dict(state["properties"])}
        if "/crm/v3/objects/contacts/90002" in url and method == "GET":
            return {"id": "90002", "properties": {
                "email": "real-customer@example.com",
                "firstname": "Real",
                "lastname": "Customer",
            }}
        if "/crm/v3/objects/contacts/90001" in url and method == "GET":
            if state["deleted"] and not cleanup_fails:
                raise urllib.error.HTTPError(url, 404, "Not Found", None, None)
            props = dict(state["properties"])
            if mismatch:
                props["lastname"] = "wrong"
            return {"id": "90001", "properties": props}
        if url.endswith("/crm/v3/objects/contacts/90001") and method == "DELETE":
            if delete_fails:
                raise RuntimeError("cleanup denied")
            state["deleted"] = True
            return {}
        raise AssertionError("unexpected URL: " + method + " " + url)

    return response, seen


def _invoke(hubspot, **kwargs):
    return hubspot.verify_hubspot(
        token="test-only-credential", portal_id=kwargs.pop("portal_id", PORTAL),
        email_domain=kwargs.pop("email_domain", "qa.example.invalid"),
        approved=kwargs.pop("approved", True),
        approve_existing_live_portal=kwargs.pop("live_approved", True),
    )


def test_existing_portal_same_key_and_cleanup_404(hubspot, monkeypatch):
    reply, seen = _fake_hubspot_api()
    monkeypatch.setattr(hubspot, "_request", reply)
    evidence = _invoke(hubspot)
    assert evidence["result"] == "PASS"
    assert evidence["cleanup"] == "archived_and_get_404_verified"
    assert evidence["duplicate_record"] is False
    assert [m for m, _, _ in seen] == [
        "GET", "POST", "GET", "GET", "POST", "GET", "GET", "GET", "DELETE", "GET"]
    assert seen[1][2] == seen[4][2]
    assert seen[7][0] == "GET"  # independently prove synthetic owner before DELETE
    assert seen[8][1].endswith("/contacts/90001")


@pytest.mark.parametrize("kwargs,returned_portal,returned_type", [
    ({"portal_id": "999999"}, PORTAL, "STANDARD"),
    ({}, "999999", "STANDARD"),
    ({}, PORTAL, "DEVELOPER_TEST"),
    ({"approved": False}, PORTAL, "STANDARD"),
    ({"live_approved": False}, PORTAL, "STANDARD"),
    ({"email_domain": "gmail.com"}, PORTAL, "STANDARD"),
    ({"email_domain": "injected..invalid"}, PORTAL, "STANDARD"),
    ({"email_domain": "example.invalid."}, PORTAL, "STANDARD"),
])
def test_no_write_on_invalid_live_portal_approval_or_namespace(
        hubspot, monkeypatch, kwargs, returned_portal, returned_type):
    reply, seen = _fake_hubspot_api(
        portal=returned_portal, account_type=returned_type)
    monkeypatch.setattr(hubspot, "_request", reply)
    with pytest.raises(RuntimeError):
        _invoke(hubspot, **kwargs)
    assert all(method != "POST" for method, _, _ in seen)


@pytest.mark.parametrize("behavior", [
    {"mismatch": True},
    {"duplicate": True},
    {"cleanup_fails": True},
    {"delete_fails": True},
])
def test_readback_idempotency_or_cleanup_failure_never_reports_pass(
        hubspot, monkeypatch, behavior):
    reply, seen = _fake_hubspot_api(**behavior)
    monkeypatch.setattr(hubspot, "_request", reply)
    with pytest.raises(RuntimeError):
        _invoke(hubspot)
    if behavior.get("mismatch", False):
        # Never delete an unverified object just because upsert named it.
        assert not any(m == "DELETE" for m, _, _ in seen)
    else:
        assert any(m == "DELETE" for m, _, _ in seen)


def test_upsert_unconfirmed_never_claims_cleanup(hubspot, monkeypatch):
    reply, seen = _fake_hubspot_api(first_upsert_fails=True)
    monkeypatch.setattr(hubspot, "_request", reply)
    with pytest.raises(RuntimeError):
        _invoke(hubspot)
    assert not any(m == "DELETE" for m, _, _ in seen)

def test_provider_applied_then_response_lost_recovers_qa_id_and_cleans_up(
        hubspot, monkeypatch):
    reply, seen = _fake_hubspot_api(
        first_upsert_fails=True, applied_but_response_lost=True)
    monkeypatch.setattr(hubspot, "_request", reply)
    with pytest.raises(RuntimeError):
        _invoke(hubspot)
    assert [m for m, _, _ in seen] == ["GET", "POST", "GET", "GET", "DELETE", "GET"]
    assert seen[2][1].find("idProperty=email") != -1
    assert seen[3][0] == "GET"  # verify id and marker independently
    assert seen[4][1].endswith("/contacts/90001")


def test_unexpected_provider_id_never_deletes_real_contact(
        hubspot, monkeypatch):
    reply, seen = _fake_hubspot_api(foreign_receipt_id=True)
    monkeypatch.setattr(hubspot, "_request", reply)
    with pytest.raises(RuntimeError):
        _invoke(hubspot)
    # Conflicting receipt is never trusted. Independently verify and clean up
    # only the uniquely owned QA record, never the foreign receipt ID.
    assert any("idProperty=email" in url and method == "GET"
               for method, url, _ in seen)
    assert any(method == "DELETE" and url.endswith("/contacts/90001")
               for method, url, _ in seen)
    assert not any("/contacts/90002" in url and method in ("GET", "DELETE")
                   for method, url, _ in seen)
