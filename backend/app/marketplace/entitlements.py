"""Paid install entitlements and Stripe checkout (MKT-AUDIT-12.1)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status

from app.config import Settings
from app.core.errors import error_detail
from app.marketplace.service import MarketplaceError, fetch_marketplace_asset

AUDIT_ENTITLEMENT_GRANTED = "marketplace.entitlement.granted"
AUDIT_CHECKOUT_CREATED = "marketplace.checkout.created"
RESOURCE_TYPE_MARKETPLACE_ENTITLEMENT = "marketplace_entitlement"

_PAID_PRICING_TYPES = frozenset({"paid", "subscription"})


class MarketplaceEntitlementError(Exception):
    code = "ENTITLEMENT_ERROR"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        if code:
            self.code = code


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def asset_requires_payment(asset: dict[str, Any], *, org_id: str) -> bool:
    """Return True when the org must purchase before install."""
    if str(asset.get("org_id") or "") == org_id:
        return False
    pricing_type = str(asset.get("pricing_type") or "free")
    price_cents = int(asset.get("price_cents") or 0)
    return pricing_type in _PAID_PRICING_TYPES and price_cents > 0


def get_active_entitlement(client: Any, org_id: str, asset_id: str) -> dict[str, Any] | None:
    result = (
        client.table("marketplace_asset_entitlements")
        .select("*")
        .eq("org_id", org_id)
        .eq("asset_id", asset_id)
        .eq("status", "active")
        .limit(1)
        .execute()
    )
    if not result.data:
        return None
    return dict(result.data[0])


def has_active_entitlement(client: Any, org_id: str, asset_id: str) -> bool:
    return get_active_entitlement(client, org_id, asset_id) is not None


def assert_install_entitlement(client: Any, org_id: str, asset: dict[str, Any]) -> None:
    """Raise MarketplaceError when a paid asset lacks entitlement."""
    if not asset_requires_payment(asset, org_id=org_id):
        return
    if has_active_entitlement(client, org_id, str(asset["id"])):
        return
    raise MarketplaceError(
        "Purchase required before installing this asset",
        code="PAYMENT_REQUIRED",
        details={
            "pricingType": asset.get("pricing_type"),
            "priceCents": int(asset.get("price_cents") or 0),
            "currency": asset.get("currency") or "usd",
        },
    )


def get_entitlement_status(client: Any, org_id: str, asset: dict[str, Any]) -> dict[str, Any]:
    requires_payment = asset_requires_payment(asset, org_id=org_id)
    entitlement = get_active_entitlement(client, org_id, str(asset["id"]))
    return {
        "requiresPayment": requires_payment,
        "hasEntitlement": entitlement is not None,
        "pricingType": asset.get("pricing_type") or "free",
        "priceCents": int(asset.get("price_cents") or 0),
        "currency": (asset.get("currency") or "usd").lower(),
        "entitlement": _normalize_entitlement(entitlement) if entitlement else None,
    }


def _normalize_entitlement(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if not row:
        return None
    return {
        "id": str(row["id"]),
        "orgId": str(row["org_id"]),
        "assetId": str(row["asset_id"]),
        "status": row.get("status"),
        "pricingType": row.get("pricing_type"),
        "priceCents": int(row.get("price_cents") or 0),
        "currency": row.get("currency") or "usd",
        "grantedAt": row.get("granted_at"),
        "expiresAt": row.get("expires_at"),
    }


def _require_stripe(settings: Settings) -> None:
    if not (settings.stripe_secret_key or "").strip():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=error_detail("Stripe is not configured", "STRIPE_NOT_CONFIGURED"),
        )


def _load_publisher_org_id(client: Any, asset: dict[str, Any]) -> str | None:
    publisher_id = asset.get("publisher_id")
    if not publisher_id:
        return None
    row = (
        client.table("marketplace_publishers")
        .select("org_id")
        .eq("id", str(publisher_id))
        .limit(1)
        .execute()
    )
    if not row.data:
        return None
    org_id = row.data[0].get("org_id")
    return str(org_id) if org_id else None


def create_asset_checkout_session(
    client: Any,
    settings: Settings,
    *,
    org_id: str,
    asset_ref: str,
    actor_id: str,
    success_url: str,
    cancel_url: str,
) -> dict[str, Any]:
    """Create Stripe Checkout for a paid marketplace asset."""
    _require_stripe(settings)
    asset = fetch_marketplace_asset(client, asset_ref)
    if asset.get("status") != "published":
        raise MarketplaceEntitlementError("Asset is not published", code="NOT_PUBLISHED")
    if not asset_requires_payment(asset, org_id=org_id):
        raise MarketplaceEntitlementError("Asset does not require payment", code="FREE_ASSET")
    if has_active_entitlement(client, org_id, str(asset["id"])):
        raise MarketplaceEntitlementError("Entitlement already active", code="ALREADY_ENTITLED")

    pricing_type = str(asset.get("pricing_type") or "paid")
    price_cents = int(asset.get("price_cents") or 0)
    currency = (asset.get("currency") or "usd").lower()
    mode = "subscription" if pricing_type == "subscription" else "payment"

    pending = {
        "org_id": org_id,
        "asset_id": asset["id"],
        "status": "pending",
        "pricing_type": pricing_type,
        "price_cents": price_cents,
        "currency": currency,
        "granted_by": actor_id,
        "updated_at": _now_iso(),
    }
    inserted = client.table("marketplace_asset_entitlements").insert(pending).execute()
    entitlement_row = dict((inserted.data or [pending])[0])

    from app.billing.stripe import init_stripe

    init_stripe(settings)
    import stripe

    metadata = {
        "org_id": org_id,
        "marketplace_asset_id": str(asset["id"]),
        "entitlement_id": str(entitlement_row["id"]),
        "checkout_kind": "marketplace_asset",
        "pricing_type": pricing_type,
    }
    publisher_org_id = _load_publisher_org_id(client, asset)
    if publisher_org_id:
        metadata["publisher_org_id"] = publisher_org_id

    line_item: dict[str, Any] = {
        "quantity": 1,
        "price_data": {
            "currency": currency,
            "unit_amount": price_cents,
            "product_data": {
                "name": str(asset.get("title") or asset.get("slug") or "Marketplace asset"),
                "metadata": {"asset_id": str(asset["id"]), "slug": str(asset.get("slug") or "")},
            },
        },
    }
    if mode == "subscription":
        line_item["price_data"]["recurring"] = {"interval": "month"}

    session = stripe.checkout.Session.create(
        mode=mode,
        line_items=[line_item],
        success_url=success_url,
        cancel_url=cancel_url,
        metadata=metadata,
        client_reference_id=str(entitlement_row["id"]),
    )

    client.table("marketplace_asset_entitlements").update(
        {
            "stripe_checkout_session_id": session.id,
            "updated_at": _now_iso(),
        }
    ).eq("id", entitlement_row["id"]).execute()

    return {
        "checkoutUrl": session.url,
        "sessionId": session.id,
        "entitlementId": str(entitlement_row["id"]),
        "mode": mode,
    }


def fulfill_entitlement_from_checkout(
    client: Any,
    settings: Settings,
    *,
    session: dict[str, Any],
) -> dict[str, Any] | None:
    """Activate entitlement after Stripe checkout.session.completed."""
    metadata = session.get("metadata") or {}
    if metadata.get("checkout_kind") != "marketplace_asset":
        return None

    entitlement_id = metadata.get("entitlement_id") or session.get("client_reference_id")
    asset_id = metadata.get("marketplace_asset_id")
    org_id = metadata.get("org_id")
    if not entitlement_id or not asset_id or not org_id:
        return None

    patch = {
        "status": "active",
        "granted_at": _now_iso(),
        "stripe_checkout_session_id": session.get("id"),
        "stripe_payment_intent_id": session.get("payment_intent"),
        "stripe_subscription_id": session.get("subscription"),
        "updated_at": _now_iso(),
    }
    updated = (
        client.table("marketplace_asset_entitlements")
        .update(patch)
        .eq("id", str(entitlement_id))
        .execute()
    )
    if not updated.data:
        return None

    entitlement = dict(updated.data[0])
    from app.marketplace.payouts import record_asset_purchase_payout

    record_asset_purchase_payout(
        client,
        settings,
        org_id=str(org_id),
        asset_id=str(asset_id),
        entitlement_id=str(entitlement_id),
        gross_cents=int(entitlement.get("price_cents") or 0),
        currency=str(entitlement.get("currency") or "usd"),
        publisher_org_id=metadata.get("publisher_org_id"),
    )
    return _normalize_entitlement(entitlement)
