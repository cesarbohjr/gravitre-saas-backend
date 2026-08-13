"""Phase 2 connector catalog — shipped vendors with real executors."""
from __future__ import annotations

from app.connectors.action_catalog.registry import get_vendor_spec
from app.connectors.phase2_connector_routes import PHASE2_ROUTES
from app.services.catalog_write_authority import catalog_action_requires_write_approval
from app.services.tool_service import list_registered_actions

PHASE2_VENDORS = (
    "linear",
    "gitlab",
    "shopify",
    "paypal",
    "brevo",
    "meta_marketing",
)


def test_phase2_vendors_shipped_with_executors():
    registered = set(list_registered_actions())
    for vendor_id in PHASE2_VENDORS:
        spec = get_vendor_spec(vendor_id)
        assert spec is not None, vendor_id
        assert spec.shipped is True, vendor_id
        actions = spec.all_actions()
        assert len(actions) >= 4, vendor_id
        assert any(a.kind == "write" for a in actions), vendor_id
        for action in actions:
            assert action.id in registered, action.id
            assert action.id in PHASE2_ROUTES, action.id


def test_linear_issues_create_is_write_with_approval_path():
    spec = get_vendor_spec("linear")
    assert spec is not None
    create = next(a for a in spec.all_actions() if a.id == "linear.issues.create")
    assert create.kind == "write"
    assert catalog_action_requires_write_approval(
        kind=create.kind,
        destructive=create.destructive,
        requires_approval=create.requires_approval,
        scopes=create.scopes,
    )


def test_paypal_destructive_writes_require_approval():
    spec = get_vendor_spec("paypal")
    assert spec is not None
    for action_id in ("paypal.refunds.create", "paypal.payouts.create"):
        action = next(a for a in spec.all_actions() if a.id == action_id)
        assert catalog_action_requires_write_approval(
            kind=action.kind,
            destructive=action.destructive,
            requires_approval=action.requires_approval,
            scopes=action.scopes,
        )
