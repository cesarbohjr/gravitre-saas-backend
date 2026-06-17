"""Same-org marketplace asset clone (MKT-7.2)."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.marketplace.browse import MarketplaceBrowseError, resolve_browsable_asset
from app.workflows.audit import write_audit_event

logger = logging.getLogger(__name__)

AUDIT_ASSET_CLONED = "marketplace.asset.cloned"
RESOURCE_TYPE_MARKETPLACE_ASSET = "marketplace_asset"


class MarketplaceCloneError(Exception):
    code = "MARKETPLACE_CLONE_ERROR"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        if code:
            self.code = code


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slug_exists(client: Any, slug: str) -> bool:
    result = (
        client.table("marketplace_assets")
        .select("id")
        .eq("slug", slug)
        .limit(1)
        .execute()
    )
    return bool(result.data)


def _unique_clone_slug(client: Any, base_slug: str) -> str:
    candidates = [f"{base_slug}-copy", * [f"{base_slug}-copy-{index}" for index in range(2, 100)]]
    for candidate in candidates:
        if not _slug_exists(client, candidate):
            return candidate
    raise MarketplaceCloneError("Unable to allocate clone slug", code="VALIDATION_ERROR")


def _serialize_cloned_asset(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "slug": row["slug"],
        "title": row["title"],
        "description": row.get("description"),
        "assetType": row.get("asset_type"),
        "category": row.get("category"),
        "department": row.get("department"),
        "visibility": row.get("visibility"),
        "status": row.get("status"),
        "clonedFromAssetId": row.get("cloned_from_asset_id"),
        "orgId": row.get("org_id"),
    }


def clone_asset(
    client: Any,
    org_id: str,
    asset_ref: str,
    *,
    actor_id: str,
) -> dict[str, Any]:
    """Create a private draft copy of a browsable asset within the same org."""
    try:
        source = resolve_browsable_asset(client, org_id, asset_ref)
    except MarketplaceBrowseError as exc:
        raise MarketplaceCloneError(str(exc), code=exc.code) from exc

    slug = _unique_clone_slug(client, str(source["slug"]))
    now = _now()
    row = {
        "publisher_id": source["publisher_id"],
        "org_id": org_id,
        "slug": slug,
        "title": f"{source['title']} (Copy)",
        "description": source.get("description"),
        "asset_type": source["asset_type"],
        "category": source.get("category"),
        "department": source.get("department"),
        "tags": source.get("tags") or [],
        "visibility": "private",
        "status": "draft",
        "pricing_type": source.get("pricing_type") or "free",
        "price_cents": int(source.get("price_cents") or 0),
        "currency": source.get("currency") or "usd",
        "config": source.get("config") or {},
        "required_connectors": source.get("required_connectors") or [],
        "required_permissions": source.get("required_permissions") or [],
        "install_variables": source.get("install_variables") or [],
        "cloned_from_asset_id": source["id"],
        "created_by": actor_id,
        "current_version": 1,
        "install_count": 0,
        "clone_count": 0,
        "review_count": 0,
        "average_rating": None,
        "updated_at": now,
    }
    result = client.table("marketplace_assets").insert(row).execute()
    cloned = dict((result.data or [row])[0])

    current_clones = int(source.get("clone_count") or 0)
    client.table("marketplace_assets").update(
        {"clone_count": current_clones + 1, "updated_at": now}
    ).eq("id", source["id"]).execute()

    write_audit_event(
        client,
        org_id=org_id,
        actor_id=actor_id,
        action=AUDIT_ASSET_CLONED,
        resource_type=RESOURCE_TYPE_MARKETPLACE_ASSET,
        resource_id=str(cloned["id"]),
        metadata={
            "sourceAssetId": source["id"],
            "sourceSlug": source.get("slug"),
            "clonedSlug": slug,
            "assetType": source.get("asset_type"),
        },
    )
    logger.info(
        "marketplace_asset_cloned org_id=%s source_id=%s cloned_id=%s slug=%s",
        org_id,
        source["id"],
        cloned["id"],
        slug,
    )
    return {
        "cloned": True,
        "sourceAssetId": source["id"],
        "asset": _serialize_cloned_asset(cloned),
    }
