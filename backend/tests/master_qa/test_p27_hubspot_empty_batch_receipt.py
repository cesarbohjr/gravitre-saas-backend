"""Regression: HubSpot may omit batch result IDs; identity must come from GET."""
import importlib.util
import pathlib
import sys
import types
import urllib.error

import pytest

SCRIPTS = pathlib.Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import p27_hubspot_sandbox_readback as mod


def test_empty_batch_receipt_verified_by_email_and_cleaned(monkeypatch):
    calls = []
    state = {"exists": False, "id": "123456", "writes": 0}
    def request(url, *, token, method, payload=None):
        calls.append((method, url))
        if "account-info/v3/details" in url:
            return {"portalId": mod.GRAVITRE_HUBSPOT_PORTAL_ID, "accountType": "STANDARD"}
        if method == "POST":
            state["writes"] += 1
            state["exists"] = True
            state["properties"] = payload["inputs"][0]["properties"]
            return {"status": "COMPLETE", "results": []}
        if method == "DELETE":
            assert state["exists"]
            state["exists"] = False
            return {}
        if "/crm/v3/objects/contacts/" in url:
            if not state["exists"]:
                raise urllib.error.HTTPError(url, 404, "not found", {}, None)
            return {"id": state["id"], "properties": dict(state["properties"])}
        raise AssertionError(url)
    monkeypatch.setattr(mod, "_request", request)
    monkeypatch.setattr(mod, "uuid4", lambda: types.SimpleNamespace(hex="a" * 32))
    result = mod.verify_hubspot(
        token="dedicated-test-token", portal_id=mod.GRAVITRE_HUBSPOT_PORTAL_ID,
        email_domain="qa.example.invalid", approved=True, approve_existing_live_portal=True)
    assert result["result"] == "PASS"
    assert result["contact_id"] == "123456"
    assert state["writes"] == 2
    assert not state["exists"]
    assert len([c for c in calls if c[0] == "DELETE"]) == 1


def test_empty_receipt_without_authoritative_contact_fails_closed(monkeypatch):
    calls = []
    def request(url, *, token, method, payload=None):
        calls.append(method)
        if "account-info/v3/details" in url:
            return {"portalId": mod.GRAVITRE_HUBSPOT_PORTAL_ID, "accountType": "STANDARD"}
        if method == "POST":
            return {"status": "COMPLETE", "results": []}
        raise urllib.error.HTTPError(url, 404, "not found", {}, None)
    monkeypatch.setattr(mod, "_request", request)
    with pytest.raises(RuntimeError, match="HubSpot QA test failed"):
        mod.verify_hubspot(token="dedicated-test-token",
                           portal_id=mod.GRAVITRE_HUBSPOT_PORTAL_ID,
                           email_domain="qa.example.invalid", approved=True,
                           approve_existing_live_portal=True)
    assert "DELETE" not in calls
