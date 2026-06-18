"""Featured and verified asset flags (MKT-AUDIT-11.3)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.marketplace.crud import MarketplaceCrudError, _fetch_asset, _serialize_asset
from app.workflows.audit import write_audit_event

AUDIT_ASSET_FEATURED = "marketplace.asset.featured_updated"
AUDIT_ASSET_VERIFIED = "marketplace.asset.verified_updated"
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
