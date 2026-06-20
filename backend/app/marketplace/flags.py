"""Featured and verified asset flags (MKT-AUDIT-11.3)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.marketplace.crud import MarketplaceCrudError, _fetch_asset, _serialize_asset, validate_asset_pricing
from app.workflows.audit import write_audit_event

AUDIT_ASSET_FEATURED = "marketplace.asset.featured_updated"
AUDIT_ASSET_VERIFIED = "marketplace.asset.verified_updated"
AUDIT_ASSET_PRICING = "marketplace.asset.pricing_updated"
RESOURCE_TYPE_MARKETPLACE_ASSET = "marketplace_asset"


class MarketplaceFlagsError(Exception):
    code = "MARKETPLACE_FLAGS_ERROR"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        if code:
            self.code = code


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _crud_to_flags(exc: MarketplaceCrudError) -> MarketplaceFlagsError:
    return MarketplaceFlagsError(str(exc), code=exc.code)


def set_asset_featured(
    client: Any,
    asset_ref: str,
    *,
    featured: bool,
    actor_id: str,
    org_id: str = "",
) -> dict[str, Any]:
    try:
        asset = _fetch_asset(client, asset_ref)
    except MarketplaceCrudError as exc:
        raise _crud_to_flags(exc) from exc

    if asset.get("status") != "published" or asset.get("visibility") != "public":
        raise MarketplaceFlagsError(
            "Only published public assets can be featured",
            code="VALIDATION_ERROR",
        )

    client.table("marketplace_assets").update(
        {"featured": featured, "updated_at": _now()}
    ).eq("id", asset["id"]).execute()
    refreshed = _fetch_asset(client, str(asset["id"]))

    write_audit_event(
        client,
        org_id=org_id or str(asset.get("org_id") or ""),
        actor_id=actor_id,
        action=AUDIT_ASSET_FEATURED,
        resource_type=RESOURCE_TYPE_MARKETPLACE_ASSET,
        resource_id=str(asset["id"]),
        metadata={"slug": refreshed.get("slug"), "featured": featured},
    )
    return {"featured": featured, "asset": _serialize_asset(refreshed)}


def set_asset_verified(
    client: Any,
    asset_ref: str,
    *,
    verified: bool,
    actor_id: str,
    org_id: str = "",
) -> dict[str, Any]:
    try:
        asset = _fetch_asset(client, asset_ref)
    except MarketplaceCrudError as exc:
        raise _crud_to_flags(exc) from exc

    if asset.get("status") != "published":
        raise MarketplaceFlagsError(
            "Only published assets can be verified",
            code="VALIDATION_ERROR",
        )

    client.table("marketplace_assets").update(
        {"verified": verified, "updated_at": _now()}
    ).eq("id", asset["id"]).execute()
    refreshed = _fetch_asset(client, str(asset["id"]))

    write_audit_event(
        client,
        org_id=org_id or str(asset.get("org_id") or ""),
        actor_id=actor_id,
        action=AUDIT_ASSET_VERIFIED,
        resource_type=RESOURCE_TYPE_MARKETPLACE_ASSET,
        resource_id=str(asset["id"]),
        metadata={"slug": refreshed.get("slug"), "verified": verified},
    )
    return {"verified": verified, "asset": _serialize_asset(refreshed)}


def list_platform_public_catalog(
    client: Any,
    *,
    featured: bool | None = None,
    verified: bool | None = None,
    search: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """Platform admin list of published public assets for featured/verified curation."""
    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    query = (
        client.table("marketplace_assets")
        .select("*", count="exact")
        .eq("status", "published")
        .eq("visibility", "public")
    )
    if featured is True:
        query = query.eq("featured", True)
    if verified is True:
        query = query.eq("verified", True)
    if search:
        term = search.strip()
        if term:
            pattern = f'"%{term}%"'
            query = query.or_(f"title.ilike.{pattern},description.ilike.{pattern},slug.ilike.{pattern}")
    query = query.order("featured", desc=True).order("install_count", desc=True).order("published_at", desc=True)
    result = query.range(offset, offset + limit - 1).execute()
    assets = [_serialize_asset(dict(row)) for row in (result.data or [])]
    total = getattr(result, "count", None)
    if total is None:
        total = len(assets) + offset
    return {"assets": assets, "total": total, "limit": limit, "offset": offset}


def set_asset_pricing(
    client: Any,
    asset_ref: str,
    *,
    pricing_type: str,
    price_cents: int,
    currency: str = "usd",
    actor_id: str,
    org_id: str = "",
) -> dict[str, Any]:
    try:
        asset = _fetch_asset(client, asset_ref)
    except MarketplaceCrudError as exc:
        raise _crud_to_flags(exc) from exc

    status = str(asset.get("status") or "")
    visibility = str(asset.get("visibility") or "")
    allowed = status in {"draft", "pending_review"} or (
        status == "published" and visibility == "public"
    )
    if not allowed:
        raise MarketplaceFlagsError(
            "Pricing can only be updated on draft, pending review, or published public assets",
            code="VALIDATION_ERROR",
        )

    try:
        pricing = validate_asset_pricing(pricing_type, price_cents, currency=currency)
    except MarketplaceCrudError as exc:
        raise _crud_to_flags(exc) from exc

    client.table("marketplace_assets").update(
        {**pricing, "updated_at": _now()}
    ).eq("id", asset["id"]).execute()
    refreshed = _fetch_asset(client, str(asset["id"]))

    write_audit_event(
        client,
        org_id=org_id or str(asset.get("org_id") or ""),
        actor_id=actor_id,
        action=AUDIT_ASSET_PRICING,
        resource_type=RESOURCE_TYPE_MARKETPLACE_ASSET,
        resource_id=str(asset["id"]),
        metadata={
            "slug": refreshed.get("slug"),
            "pricingType": pricing["pricing_type"],
            "priceCents": pricing["price_cents"],
        },
    )
    return {"updated": True, "asset": _serialize_asset(refreshed)}


def set_org_asset_pricing(
    client: Any,
    org_id: str,
    asset_ref: str,
    *,
    pricing_type: str,
    price_cents: int,
    currency: str = "usd",
    actor_id: str,
) -> dict[str, Any]:
    from app.marketplace.crud import MarketplaceCrudError, _assert_org_owns_asset, _fetch_asset

    try:
        asset = _fetch_asset(client, asset_ref)
    except MarketplaceCrudError as exc:
        raise _crud_to_flags(exc) from exc
    _assert_org_owns_asset(asset, org_id)
    return set_asset_pricing(
        client,
        asset_ref,
        pricing_type=pricing_type,
        price_cents=price_cents,
        currency=currency,
        actor_id=actor_id,
        org_id=org_id,
    )
