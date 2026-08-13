"""Phase 2 connector executor route contracts."""
from __future__ import annotations

from app.connectors.oauth_provider_registry import GENERIC_OAUTH_VENDORS, OAUTH_PROVIDER_REGISTRY
from app.connectors.phase2_connector_routes import PHASE2_ROUTES, PHASE2_VENDORS


def test_phase2_route_count():
    assert len(PHASE2_ROUTES) == 30
    assert PHASE2_VENDORS == frozenset(
        {"linear", "gitlab", "shopify", "paypal", "brevo", "meta_marketing"}
    )


def test_phase2_oauth_vendors_in_registry():
    for vendor in ("linear", "gitlab", "shopify", "paypal", "meta_marketing"):
        assert vendor in GENERIC_OAUTH_VENDORS
        assert vendor in OAUTH_PROVIDER_REGISTRY


def test_brevo_is_api_key_not_generic_oauth():
    assert "brevo" not in GENERIC_OAUTH_VENDORS


def test_shopify_oauth_requires_subdomain():
    assert OAUTH_PROVIDER_REGISTRY["shopify"].requires_subdomain is True


def test_linear_routes_present():
    for action in (
        "linear.issues.list",
        "linear.issues.get",
        "linear.issues.create",
        "linear.issues.update",
    ):
        assert action in PHASE2_ROUTES
