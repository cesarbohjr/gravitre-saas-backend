"""Marketplace asset browse/list/detail (MKT-5.1)."""
from __future__ import annotations

import re
import uuid
from typing import Any

from app.marketplace.service import MarketplaceError, validate_connectors_for_asset

BROWSE_LIST_COLUMNS = (
    "id, slug, title, description, asset_type, category, department, tags, "
    "visibility, status, pricing_type, price_cents, currency, required_connectors, "
    "install_count, clone_count, average_rating, review_count, current_version, "
    "published_at, publisher_id, org_id, business_outcome, use_case, estimated_hours_saved, "
    "created_at, updated_at"
)

BROWSE_DETAIL_COLUMNS = f"{BROWSE_LIST_COLUMNS}, config, install_variables, required_permissions, cloned_from_asset_id"

PACK_ITEM_COLUMNS = (
    "id, sort_order, required, child_asset_id, "
    "marketplace_assets!marketplace_pack_items_child_asset_id_fkey("
    "id, slug, title, asset_type, category, department, pricing_type, price_cents"
    ")"
)

_ASSET_TYPES = frozenset({
    "ai_agent",
    "workflow",
    "knowledge_pack",
    "department_pack",
    "connector_config",
})
_PRICING_TYPES = frozenset({"free", "paid", "subscription"})


class MarketplaceBrowseError(Exception):
    code = "MARKETPLACE_BROWSE_ERROR"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        if code:
            self.code = code


def is_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
        return True
    except ValueError:
        return False


def _sanitize_search(value: str) -> str:
    cleaned = re.sub(r"[%_,()]", " ", value.strip())
    return cleaned[:120]


def _checklist_summary(required_connectors: list[Any] | None, validation: dict[str, Any]) -> dict[str, Any]:
    checklist = validation.get("checklist") or []
    required_total = sum(1 for item in checklist if item.get("required"))
    required_connected = sum(1 for item in checklist if item.get("required") and item.get("connected"))
    return {
        "requiredConnectorsTotal": required_total,
        "requiredConnectorsConnected": required_connected,
        "connectorsReady": required_connected >= required_total if required_total else True,
        "canInstall": validation.get("can_install", True),
        "connectorChecklist": checklist,
        "requiredConnectors": required_connectors or [],
    }


def _serialize_asset_summary(
    row: dict[str, Any],
    *,
    install: dict[str, Any] | None = None,
    connector_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    summary = connector_summary or {}
    return {
        "id": row["id"],
        "slug": row["slug"],
        "title": row["title"],
        "description": row.get("description"),
        "assetType": row.get("asset_type"),
        "category": row.get("category"),
        "department": row.get("department"),
        "tags": row.get("tags") or [],
        "visibility": row.get("visibility"),
        "status": row.get("status"),
        "pricingType": row.get("pricing_type"),
        "priceCents": row.get("price_cents"),
        "currency": row.get("currency"),
        "installCount": row.get("install_count"),
        "cloneCount": row.get("clone_count"),
        "averageRating": row.get("average_rating"),
        "reviewCount": row.get("review_count"),
        "currentVersion": row.get("current_version"),
        "publishedAt": row.get("published_at"),
        "publisherId": row.get("publisher_id"),
        "orgId": row.get("org_id"),
        "businessOutcome": row.get("business_outcome"),
        "useCase": row.get("use_case"),
        "estimatedHoursSaved": row.get("estimated_hours_saved"),
        "installed": install is not None,
        "installedAt": install.get("installed_at") if install else None,
        "installId": install.get("id") if install else None,
        **summary,
    }


def _serialize_pack_item(row: dict[str, Any]) -> dict[str, Any]:
    child = row.get("marketplace_assets") or {}
    if isinstance(child, list):
        child = child[0] if child else {}
    return {
        "sortOrder": row.get("sort_order"),
        "required": row.get("required", True),
        "child": {
            "id": child.get("id"),
            "slug": child.get("slug"),
            "title": child.get("title"),
            "assetType": child.get("asset_type"),
            "category": child.get("category"),
            "department": child.get("department"),
            "pricingType": child.get("pricing_type"),
            "priceCents": child.get("price_cents"),
        },
    }


def _serialize_asset_detail(
    row: dict[str, Any],
    *,
    install: dict[str, Any] | None,
    connector_summary: dict[str, Any],
    pack_items: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    payload = _serialize_asset_summary(
        row,
        install=install,
        connector_summary=connector_summary,
    )
    payload.update(
        {
            "config": row.get("config") or {},
            "installVariables": row.get("install_variables") or [],
            "requiredPermissions": row.get("required_permissions") or [],
            "clonedFromAssetId": row.get("cloned_from_asset_id"),
            "blockers": [
                {
                    "connector": item.get("connectorType"),
                    "reason": f"{item.get('label') or item.get('connectorType')} is not connected",
                    "action_url": item.get("action_url") or item.get("connectPath"),
                }
                for item in connector_summary.get("connectorChecklist") or []
                if item.get("required") and not item.get("connected")
            ],
            "packItems": pack_items or [],
        }
    )
    return payload


def _active_installs_by_asset(client: Any, org_id: str, asset_ids: list[str]) -> dict[str, dict[str, Any]]:
    if not asset_ids:
        return {}
    result = (
        client.table("marketplace_installs")
        .select("id, asset_id, status, installed_at, installed_entity_type, installed_entity_id")
        .eq("org_id", org_id)
        .eq("status", "active")
        .in_("asset_id", asset_ids)
        .execute()
    )
    return {str(row["asset_id"]): dict(row) for row in (result.data or [])}


def _fetch_pack_items(client: Any, pack_asset_id: str) -> list[dict[str, Any]]:
    try:
        result = (
            client.table("marketplace_pack_items")
            .select(PACK_ITEM_COLUMNS)
            .eq("pack_asset_id", pack_asset_id)
            .order("sort_order")
            .execute()
        )
    except Exception:
        result = (
            client.table("marketplace_pack_items")
            .select("id, sort_order, required, child_asset_id")
            .eq("pack_asset_id", pack_asset_id)
            .order("sort_order")
            .execute()
        )
        child_ids = [str(row["child_asset_id"]) for row in (result.data or []) if row.get("child_asset_id")]
        children: dict[str, dict[str, Any]] = {}
        if child_ids:
            child_rows = (
                client.table("marketplace_assets")
                .select("id, slug, title, asset_type, category, department, pricing_type, price_cents")
                .in_("id", child_ids)
                .execute()
            )
            children = {str(row["id"]): dict(row) for row in (child_rows.data or [])}
        return [
            _serialize_pack_item(
                {
                    **row,
                    "marketplace_assets": children.get(str(row.get("child_asset_id")), {}),
                }
            )
            for row in (result.data or [])
        ]
    return [_serialize_pack_item(dict(row)) for row in (result.data or [])]


def list_marketplace_assets(
    client: Any,
    org_id: str,
    *,
    environment_name: str = "production",
    category: str | None = None,
    department: str | None = None,
    asset_type: str | None = None,
    pricing_type: str | None = None,
    search: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """Return paginated browse rows with per-org install + connector readiness."""
    if asset_type and asset_type not in _ASSET_TYPES:
        raise MarketplaceBrowseError(f"invalid asset_type: {asset_type}", code="VALIDATION_ERROR")
    if pricing_type and pricing_type not in _PRICING_TYPES:
        raise MarketplaceBrowseError(f"invalid pricing_type: {pricing_type}", code="VALIDATION_ERROR")

    limit = max(1, min(limit, 100))
    offset = max(0, offset)

    query = (
        client.table("marketplace_assets")
        .select(BROWSE_LIST_COLUMNS, count="exact")
        .eq("status", "published")
        .or_(f"visibility.eq.public,and(visibility.eq.internal,org_id.eq.{org_id})")
    )
    if category:
        query = query.eq("category", category)
    if department:
        query = query.eq("department", department)
    if asset_type:
        query = query.eq("asset_type", asset_type)
    if pricing_type:
        query = query.eq("pricing_type", pricing_type)
    if search:
        term = _sanitize_search(search)
        if term:
            pattern = f'"%{term}%"'
            query = query.or_(f"title.ilike.{pattern},description.ilike.{pattern},slug.ilike.{pattern}")

    query = query.order("install_count", desc=True).order("published_at", desc=True)
    result = query.range(offset, offset + limit - 1).execute()
    rows = [dict(row) for row in (result.data or [])]
    asset_ids = [str(row["id"]) for row in rows]
    installs = _active_installs_by_asset(client, org_id, asset_ids)

    assets: list[dict[str, Any]] = []
    for row in rows:
        validation = validate_connectors_for_asset(
            client,
            org_id,
            row.get("required_connectors") or [],
            environment_name=environment_name,
        )
        connector_summary = _checklist_summary(row.get("required_connectors"), validation)
        assets.append(
            _serialize_asset_summary(
                row,
                install=installs.get(str(row["id"])),
                connector_summary=connector_summary,
            )
        )

    total = getattr(result, "count", None)
    if total is None:
        total = len(assets) + offset

    return {
        "assets": assets,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def _fetch_asset_row(client: Any, *, asset_id: str | None = None, slug: str | None = None) -> dict[str, Any]:
    query = client.table("marketplace_assets").select(BROWSE_DETAIL_COLUMNS)
    if asset_id:
        query = query.eq("id", asset_id)
    elif slug:
        query = query.eq("slug", slug)
    else:
        raise MarketplaceBrowseError("asset reference required", code="VALIDATION_ERROR")
    result = query.limit(1).execute()
    if not result.data:
        raise MarketplaceBrowseError("Marketplace asset not found", code="NOT_FOUND")
    return dict(result.data[0])


def _assert_asset_browsable(row: dict[str, Any], org_id: str) -> None:
    row_org = str(row.get("org_id") or "")
    status = str(row.get("status") or "")
    visibility = row.get("visibility")

    if status == "published":
        if visibility == "public":
            return
        if visibility == "internal" and row_org == org_id:
            return
        raise MarketplaceBrowseError("Marketplace asset not found", code="NOT_FOUND")

    if row_org == org_id and status in {"draft", "pending_review"}:
        return
    raise MarketplaceBrowseError("Marketplace asset not found", code="NOT_FOUND")


def get_marketplace_asset(
    client: Any,
    org_id: str,
    asset_ref: str,
    *,
    environment_name: str = "production",
) -> dict[str, Any]:
    """Fetch asset detail by UUID or slug, including connector pre-check for the org."""
    if is_uuid(asset_ref):
        row = _fetch_asset_row(client, asset_id=asset_ref)
    else:
        row = _fetch_asset_row(client, slug=asset_ref)
    _assert_asset_browsable(row, org_id)

    validation = validate_connectors_for_asset(
        client,
        org_id,
        row.get("required_connectors") or [],
        environment_name=environment_name,
    )
    connector_summary = _checklist_summary(row.get("required_connectors"), validation)
    installs = _active_installs_by_asset(client, org_id, [str(row["id"])])
    pack_items: list[dict[str, Any]] | None = None
    if row.get("asset_type") == "department_pack":
        pack_items = _fetch_pack_items(client, str(row["id"]))

    return {
        "asset": _serialize_asset_detail(
            row,
            install=installs.get(str(row["id"])),
            connector_summary=connector_summary,
            pack_items=pack_items,
        )
    }


def resolve_browsable_asset(client: Any, org_id: str, asset_ref: str) -> dict[str, Any]:
    """Resolve a browsable asset row by UUID or slug."""
    if is_uuid(asset_ref):
        row = _fetch_asset_row(client, asset_id=asset_ref)
    else:
        row = _fetch_asset_row(client, slug=asset_ref)
    _assert_asset_browsable(row, org_id)
    return row


def marketplace_browse_error_to_marketplace_error(exc: MarketplaceBrowseError) -> MarketplaceError:
    return MarketplaceError(str(exc), code=exc.code)
