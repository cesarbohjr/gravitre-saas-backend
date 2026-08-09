"""Twilio executor route + write-authority contract (external telephony)."""
from __future__ import annotations

from app.connectors.action_catalog.registry import get_vendor_catalog
from app.connectors.twilio_api import _ROUTES
from app.services.catalog_write_authority import catalog_action_requires_write_approval


def test_twilio_core_routes_use_account_sid_paths():
    assert _ROUTES["twilio.calls.create"][0] == "POST"
    assert "/Accounts/{account_sid}/Calls.json" in _ROUTES["twilio.calls.create"][1]
    assert _ROUTES["twilio.calls.get"][0] == "GET"
    assert "{call_sid}" in _ROUTES["twilio.calls.get"][1]
    assert _ROUTES["twilio.messages.create"][0] == "POST"


def test_twilio_outbound_actions_require_write_approval():
    vendor = get_vendor_catalog()["twilio"]
    by_id = {a.id: a for a in vendor.all_actions()}
    for action_id in ("twilio.calls.create", "twilio.messages.create"):
        spec = by_id[action_id]
        assert catalog_action_requires_write_approval(
            kind=spec.kind,
            destructive=spec.destructive,
            requires_approval=spec.requires_approval,
            scopes=spec.scopes,
        )


def test_twilio_shipped_and_distinct_from_internal_voice_copy():
    vendor = get_vendor_catalog()["twilio"]
    assert vendor.shipped is True
    create = next(a for a in vendor.all_actions() if a.id == "twilio.calls.create")
    assert "external" in create.description.lower() or "call-center" in create.description.lower()
    assert "approval" in create.description.lower()
