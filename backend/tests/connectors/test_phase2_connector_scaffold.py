"""Phase 2 connector catalog scaffold — ActionSpec rows only (shipped=False)."""
from __future__ import annotations

from app.connectors.action_catalog.registry import get_vendor_spec

PHASE2_VENDORS = (
    "linear",
    "gitlab",
    "shopify",
    "paypal",
    "brevo",
    "meta_marketing",
)


def test_phase2_vendors_present_in_catalog():
    for vendor_id in PHASE2_VENDORS:
        spec = get_vendor_spec(vendor_id)
        assert spec is not None, vendor_id
        assert spec.shipped is False, vendor_id
        actions = spec.all_actions()
        assert len(actions) >= 4, vendor_id
        assert any(a.kind == "write" for a in actions), vendor_id


def test_linear_issues_create_is_write():
    spec = get_vendor_spec("linear")
    assert spec is not None
    create = next(a for a in spec.all_actions() if a.id == "linear.issues.create")
    assert create.kind == "write"
