"""Federate partner connector registry into unified catalog browse (MKT-AUDIT-13.1)."""
from __future__ import annotations

from typing import Any

from app.services.marketplace_billing_service import enrich_registry_with_pricing
from app.services.partner_marketplace_service import list_registry

SOURCE_PARTNER_REGISTRY = "partner_registry"


def _serialize_federated_connector(
    registry: dict[str, Any],
    *,
    pricing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    vendor = str(registry.get("vendor") or "")
    slug = f"partner-{vendor}" if vendor else f"partner-{registry.get('id')}"
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
        raise ValueError("registry not found or not published")

    updated = (
        client.table("marketplace_assets")
        .update({"partner_registry_id": registry_id})
        .eq("id", asset_id)
        .execute()
    )
    if not updated.data:
        raise ValueError("asset not found")
    return {
        "assetId": asset_id,
        "registryId": registry_id,
        "vendor": registry.data[0].get("vendor"),
    }
