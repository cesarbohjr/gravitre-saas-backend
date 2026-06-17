"""Persist Gravitre marketplace starter catalog to Supabase (MKT-4.1 – MKT-4.5)."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.marketplace.schemas import validate_asset_payload
from app.marketplace.seed_catalog import LEGACY_PACK_SLUG_MAP, CatalogAsset, list_catalog_assets
from app.services.department_pack_catalog import pack_seed_id

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_missing_table_error(error: Exception) -> bool:
    message = str(error).lower()
    return "does not exist" in message or ("relation" in message and "does not exist" in message)


def fetch_publisher_id(client: Any, *, slug: str = "gravitre") -> str:
    result = (
        client.table("marketplace_publishers")
        .select("id")
        .eq("slug", slug)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise RuntimeError(f"Marketplace publisher not found: {slug!r}")
    return str(result.data[0]["id"])


def _asset_row(publisher_id: str, asset: CatalogAsset, *, validated: dict[str, Any]) -> dict[str, Any]:
    now = _now()
    return {
        "publisher_id": publisher_id,
        "org_id": None,
        "slug": asset.slug,
        "title": asset.title,
        "description": asset.description,
        "asset_type": asset.asset_type,
        "category": asset.category,
        "department": asset.department,
        "tags": asset.tags,
        "visibility": "public",
        "status": "published",
        "pricing_type": "free",
        "price_cents": 0,
        "currency": "usd",
        "config": validated["config"],
        "required_connectors": validated["required_connectors"],
        "required_permissions": [],
        "install_variables": validated["install_variables"],
        "current_version": 1,
        "published_at": now,
        "updated_at": now,
    }


def upsert_catalog_asset(
    client: Any,
    publisher_id: str,
    asset: CatalogAsset,
) -> dict[str, Any]:
    validated = validate_asset_payload(
        asset_type=asset.asset_type,
        config=asset.config,
        install_variables=asset.install_variables,
        required_connectors=asset.required_connectors,
        publish=True,
    )
    row = _asset_row(publisher_id, asset, validated=validated)
    existing = (
        client.table("marketplace_assets")
        .select("id, current_version")
        .eq("slug", asset.slug)
        .limit(1)
        .execute()
    )
    if existing.data:
        asset_id = str(existing.data[0]["id"])
        client.table("marketplace_assets").update(row).eq("id", asset_id).execute()
    else:
        inserted = client.table("marketplace_assets").insert(row).execute()
        asset_id = str((inserted.data or [row])[0]["id"])

    version_row = {
        "asset_id": asset_id,
        "version_number": 1,
        "config": validated["config"],
        "required_connectors": validated["required_connectors"],
        "required_permissions": [],
        "install_variables": validated["install_variables"],
        "change_summary": "Starter catalog seed",
        "published_at": row["published_at"],
    }
    client.table("marketplace_asset_versions").upsert(
        version_row,
        on_conflict="asset_id,version_number",
    ).execute()
    return {"id": asset_id, "slug": asset.slug}


def sync_pack_items(client: Any, pack: CatalogAsset, slug_to_id: dict[str, str]) -> int:
    if not pack.pack_children:
        return 0
    pack_id = slug_to_id.get(pack.slug)
    if not pack_id:
        raise RuntimeError(f"pack asset missing after upsert: {pack.slug}")
    client.table("marketplace_pack_items").delete().eq("pack_asset_id", pack_id).execute()
    rows: list[dict[str, Any]] = []
    for index, child_slug in enumerate(pack.pack_children):
        child_id = slug_to_id.get(child_slug)
        if not child_id:
            raise RuntimeError(f"pack {pack.slug} references unknown child slug: {child_slug}")
        rows.append(
            {
                "pack_asset_id": pack_id,
                "child_asset_id": child_id,
                "sort_order": index,
                "required": True,
            }
        )
    if rows:
        client.table("marketplace_pack_items").insert(rows).execute()
    return len(rows)


def validate_catalog_assets(assets: list[CatalogAsset] | None = None) -> dict[str, Any]:
    catalog = assets or list_catalog_assets()
    for asset in catalog:
        validate_asset_payload(
            asset_type=asset.asset_type,
            config=asset.config,
            install_variables=asset.install_variables,
            required_connectors=asset.required_connectors,
            publish=True,
        )
    pack_item_count = sum(len(asset.pack_children) for asset in catalog if asset.asset_type == "department_pack")
    return {
        "asset_count": len(catalog),
        "pack_item_count": pack_item_count,
    }


def seed_marketplace_catalog(
    client: Any,
    *,
    publisher_slug: str = "gravitre",
    dry_run: bool = False,
) -> dict[str, Any]:
    assets = list_catalog_assets()
    if dry_run:
        summary = validate_catalog_assets(assets)
        return {"dry_run": True, **summary}

    publisher_id = fetch_publisher_id(client, slug=publisher_slug)
    slug_to_id: dict[str, str] = {}
    for asset in assets:
        saved = upsert_catalog_asset(client, publisher_id, asset)
        slug_to_id[saved["slug"]] = saved["id"]

    pack_items = 0
    for asset in assets:
        if asset.asset_type == "department_pack":
            pack_items += sync_pack_items(client, asset, slug_to_id)

    return {
        "publisher_id": publisher_id,
        "asset_count": len(slug_to_id),
        "pack_item_count": pack_items,
        "slugs": sorted(slug_to_id),
    }


def _legacy_installed_entity_id(org_id: str, pack_id: str, row: dict[str, Any]) -> str:
    workflow_ids = row.get("workflow_ids") or []
    if isinstance(workflow_ids, list) and workflow_ids:
        return str(workflow_ids[0])
    return pack_seed_id(org_id, f"{pack_id}:workflow")


def backfill_legacy_department_pack_installs(client: Any, slug_to_id: dict[str, str]) -> dict[str, Any]:
    """MKT-4.5: copy org_department_pack_installs rows into marketplace_installs."""
    try:
        legacy = client.table("org_department_pack_installs").select("*").execute()
    except Exception as exc:
        if _is_missing_table_error(exc):
            return {"backfilled": 0, "skipped": 0, "reason": "legacy_table_missing"}
        raise

    backfilled = 0
    skipped = 0
    for row in legacy.data or []:
        pack_id = str(row.get("pack_id") or "")
        org_id = str(row.get("org_id") or "")
        if not pack_id or not org_id:
            skipped += 1
            continue
        asset_slug = LEGACY_PACK_SLUG_MAP.get(pack_id, pack_id)
        asset_id = slug_to_id.get(asset_slug)
        if not asset_id:
            logger.warning("backfill_skip_unknown_pack pack_id=%s mapped_slug=%s", pack_id, asset_slug)
            skipped += 1
            continue

        entity_id = _legacy_installed_entity_id(org_id, pack_id, row)
        install_row = {
            "org_id": org_id,
            "asset_id": asset_id,
            "asset_version": 1,
            "installed_entity_type": "department_pack",
            "installed_entity_id": entity_id,
            "install_variables": {},
            "status": "active",
            "installed_by": row.get("installed_by"),
            "installed_at": row.get("installed_at") or _now(),
            "updated_at": row.get("updated_at") or _now(),
            "metadata": {
                "backfilledFrom": "org_department_pack_installs",
                "legacyPackId": pack_id,
                "agentIds": row.get("agent_ids") or [],
                "workflowIds": row.get("workflow_ids") or [],
                "ragSourceIds": row.get("rag_source_ids") or [],
                "checklist": row.get("connector_checklist") or [],
            },
        }
        existing = (
            client.table("marketplace_installs")
            .select("id")
            .eq("org_id", org_id)
            .eq("asset_id", asset_id)
            .eq("status", "active")
            .limit(1)
            .execute()
        )
        if existing.data:
            client.table("marketplace_installs").update(install_row).eq("id", existing.data[0]["id"]).execute()
        else:
            client.table("marketplace_installs").insert(install_row).execute()
        backfilled += 1

    return {"backfilled": backfilled, "skipped": skipped}
