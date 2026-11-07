"""No-network HubSpot acceptance contract with actual CRM v3 request shapes."""
from __future__ import annotations

import importlib
from pathlib import Path

import pytest


@pytest.fixture
def hubspot(monkeypatch):
    scripts = Path(__file__).resolve().parents[2] / "scripts"
    monkeypatch.syspath_prepend(str(scripts))
    return importlib.import_module("p27_hubspot_sandbox_readback")


def _fake_hubspot_api(*, portal="910002", account_type="DEVELOPER_TEST",
                      mismatch=False, duplicate=False):
    seen = []
    def response(url, *, token, method, payload=None):
        seen.append((method, url, payload))
        if url.endswith("/account-info/v3/details") and method == "GET":
            return {"portalId": int(portal), "accountType": account_type}
        if url.endswith("/crm/v3/objects/contacts/batch/upsert") and method == "POST":
            assert len(payload["inputs"]) == 1
            item = payload["inputs"][0]
            assert item["idProperty"] == "email"
            assert item["id"] == item["properties"]["email"]
            count = len([method for method, _, _ in seen if method == "POST"])
            return {"status": "COMPLETE",
                    "results": [{"id": "90002" if duplicate and count > 1 else "90001"}]}
        if method == "GET" and "/crm/v3/objects/contacts/90001" in url:
            posted = next(payload for m, _, payload in seen if m == "POST")
            props = dict(posted["inputs"][0]["properties"])
            if mismatch:
                props["lastname"] = "not-the-original-value"
            return {"id": "90001", "properties": props}
        raise AssertionError("unexpected URL: " + method + " " + url)
    return response, seen


def test_hubspot_sandbox_upsert_authoritative_get_and_same_id_replay(hubspot, monkeypatch):
    reply, seen = _fake_hubspot_api()
    monkeypatch.setattr(hubspot, "_request", reply)
    evidence = hubspot.verify_hubspot(
        token="sandbox-fixture-token", portal_id="910002",
        email_domain="example.invalid", approved=True)
    assert evidence["result"] == "PASS" and evidence["duplicate_record"] is False
    assert [method for method, _, _ in seen] == ["GET", "POST", "GET", "POST", "GET"]
    assert seen[1][2] == seen[3][2]
    assert evidence["readback"] == "crm_v3_contacts_get_by_id"


@pytest.mark.parametrize("portal,account_type,approved", [
    ("910003", "DEVELOPER_TEST", True),
    ("910002", "STANDARD", True),
    ("910002", "DEVELOPER_TEST", False),
])
def test_hubspot_wrong_portal_production_account_or_no_approval_never_writes(
        hubspot, monkeypatch, portal, account_type, approved):
    reply, seen = _fake_hubspot_api(portal=portal, account_type=account_type)
    monkeypatch.setattr(hubspot, "_request", reply)
    with pytest.raises(RuntimeError):
        hubspot.verify_hubspot(
            token="sandbox-fixture-token", portal_id="910002",
            email_domain="example.invalid", approved=approved)
    assert all(method != "POST" for method, _, _ in seen)


@pytest.mark.parametrize("mismatch,duplicate", [(True, False), (False, True)])
def test_hubspot_readback_mismatch_or_duplicate_contact_fails(
        hubspot, monkeypatch, mismatch, duplicate):
    reply, seen = _fake_hubspot_api(mismatch=mismatch, duplicate=duplicate)
    monkeypatch.setattr(hubspot, "_request", reply)
    with pytest.raises(RuntimeError):
        hubspot.verify_hubspot(
            token="sandbox-fixture-token", portal_id="910002",
            email_domain="example.invalid", approved=True)
