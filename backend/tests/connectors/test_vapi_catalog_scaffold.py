"""Vapi catalog scaffold — Phase 5 sequenced after Twilio."""
from __future__ import annotations

from app.connectors.action_catalog.registry import get_vendor_catalog
from app.services.catalog_write_authority import catalog_action_requires_write_approval


def test_vapi_outbound_call_requires_approval():
    vendor = get_vendor_catalog()["vapi"]
    assert vendor.shipped is False  # Twilio first; Vapi follows
    create = next(a for a in vendor.all_actions() if a.id == "vapi.calls.create")
    assert catalog_action_requires_write_approval(
        kind=create.kind,
        destructive=create.destructive,
        requires_approval=create.requires_approval,
        scopes=create.scopes,
    )
    assert "external" in create.description.lower() or "phone" in create.description.lower()
