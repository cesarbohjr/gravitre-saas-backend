"""Federate partner connector registry into unified catalog browse (MKT-AUDIT-13.1)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.services.marketplace_billing_service import enrich_registry_with_pricing
from app.services.partner_marketplace_service import list_registry

SOURCE_PARTNER_REGISTRY = "partner_registry"


class MarketplaceConvergenceError(Exception):
    code = "CONVERGENCE_ERROR"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        if code:
            self.code = code


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _registry_slug(registry: dict[str, Any]) -> str:
    vendor = str(registry.get("vendor") or "")
    if vendor:
        return f"partner-{vendor}"
    return f"partner-{str(registry.get('id'))[:8]}"


def _connector_config_from_registry(registry: dict[str, Any]) -> dict[str, Any]:
    manifest = registry.get("manifest") or {}
    vendor = str(registry.get("vendor") or manifest.get("id") or "connector")
    return {
        "connector_type": vendor,
        "label": registry.get("name") or vendor,
        "required": True,
        "connect_path": "/connectors",
    }


def _serialize_federated_connector(
    registry: dict[str, Any],
    *,
    pricing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    vendor = str(registry.get("vendor") or "")
    slug = _registry_slug(registry)
    pricing_row = pricing or {}
    pricing_model = pricing_row.get("model") or pricing_row.get("pricingModel") or "free"
    price_cents = int(pricing_row.get("priceCents") or 0)
    if pricing_model == "flat_monthly":
        pricing_type = "subscription"
    elif pricing_model == "per_invocation" or price_cents > 0:
        pricing_type = "paid"
    else:
        pricing_type = "free"

    return {
        "id": str(registry["id"]),
        "slug": slug,
        "title": registry.get("name") or vendor or "Partner connector",
        "description": registry.get("description") or "",
        "assetType": "connector_config",
        "category": "connectors",
        "department": None,
        "tags": ["partner", vendor] if vendor else ["partner"],
        "pricingType": pricing_type,
        "priceCents": price_cents,
        "currency": (pricing_row.get("currency") or "usd").lower(),
        "source": SOURCE_PARTNER_REGISTRY,
        "registryId": str(registry["id"]),
        "vendor": vendor,
        "version": registry.get("version"),
        "authType": registry.get("authType"),
        "certificationBadge": registry.get("certificationBadge"),
        "verified": bool(registry.get("certificationBadge")),
        "featured": False,
        "installCount": 0,
        "canInstall": False,
        "installed": False,
        "connectorsReady": True,
        "requiredConnectorsConnected": 0,
        "requiredConnectorsTotal": 0,
        "connectorChecklist": [],
        "federated": True,
    }


def list_federated_connector_assets(
    client: Any,
    *,
    search: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """Return partner registry rows in unified asset list shape."""
    registry_rows = list_registry(client)
    enriched = enrich_registry_with_pricing(client, registry_rows)

    if search:
        needle = search.strip().lower()
        enriched = [
            row
            for row in enriched
            if needle in str(row.get("name") or "").lower()
            or needle in str(row.get("vendor") or "").lower()
            or needle in str((row.get("manifest") or {}).get("description") or "").lower()
        ]

    total = len(enriched)
    page = enriched[offset : offset + limit]
    assets = [_serialize_federated_connector(row, pricing=row.get("pricing")) for row in page]
    return {
        "assets": assets,
        "total": total,
        "limit": limit,
        "offset": offset,
        "source": SOURCE_PARTNER_REGISTRY,
    }


def upsert_connector_asset_from_registry(client: Any, registry_row: dict[str, Any]) -> dict[str, Any]:
    """Create or update a unified connector_config asset linked to a registry row."""
    registry_id = str(registry_row["id"])
    slug = _registry_slug(registry_row)
    manifest = registry_row.get("manifest") or {}
    vendor = str(registry_row.get("vendor") or "")

    linked = (
        client.table("marketplace_assets")
        .select("id, slug")
        .eq("partner_registry_id", registry_id)
        .limit(1)
        .execute()
    )
    by_slug = (
        client.table("marketplace_assets")
        .select("id, slug")
        .eq("slug", slug)
        .limit(1)
        .execute()
    )
    existing_id = None
    if linked.data:
        existing_id = str(linked.data[0]["id"])
    elif by_slug.data:
        existing_id = str(by_slug.data[0]["id"])

    publisher_id = None
    org_id = registry_row.get("org_id")
    if org_id:
        from app.marketplace.crud import resolve_org_publisher_id

        try:
            publisher_id = resolve_org_publisher_id(client, str(org_id))
        except Exception:
            publisher_id = None

    payload = {
        "slug": slug,
        "title": registry_row.get("name") or vendor or "Partner connector",
        "description": manifest.get("description") or registry_row.get("description") or "",
        "asset_type": "connector_config",
        "category": "connectors",
        "department": None,
        "tags": ["partner", vendor] if vendor else ["partner"],
        "visibility": "public",
        "status": "published",
        "pricing_type": "free",
        "price_cents": 0,
        "currency": "usd",
        "config": _connector_config_from_registry(registry_row),
        "required_connectors": [],
        "install_variables": [],
        "partner_registry_id": registry_id,
        "org_id": org_id,
        "publisher_id": publisher_id,
        "verified": bool(registry_row.get("certification_badge")),
        "published_at": registry_row.get("published_at") or _now_iso(),
        "updated_at": _now_iso(),
    }

    if existing_id:
        updated = client.table("marketplace_assets").update(payload).eq("id", existing_id).execute()
        row = dict((updated.data or [{"id": existing_id}])[0])
        return {"created": False, "assetId": str(row.get("id") or existing_id), "slug": slug}

    payload["created_at"] = _now_iso()
    inserted = client.table("marketplace_assets").insert(payload).execute()
    if not inserted.data:
        raise MarketplaceConvergenceError("Failed to create connector_config asset", code="INSERT_FAILED")
    row = dict(inserted.data[0])
    return {"created": True, "assetId": str(row["id"]), "slug": slug}


def link_asset_to_registry(
    client: Any,
    *,
    asset_id: str,
    registry_id: str,
) -> dict[str, Any]:
    """Attach a unified asset row to a partner registry entry."""
    registry = (
        client.table("partner_connector_registry")
        .select("id, vendor, name, status")
        .eq("id", registry_id)
        .limit(1)
        .execute()
    )
    if not registry.data or registry.data[0].get("status") != "published":
        raise MarketplaceConvergenceError("registry not found or not published", code="NOT_FOUND")

    updated = (
        client.table("marketplace_assets")
        .update({"partner_registry_id": registry_id, "updated_at": _now_iso()})
        .eq("id", asset_id)
        .execute()
    )
    if not updated.data:
        raise MarketplaceConvergenceError("asset not found", code="NOT_FOUND")
    return {
        "assetId": asset_id,
        "registryId": registry_id,
        "vendor": registry.data[0].get("vendor"),
    }
