"""Org-owned marketplace asset CRUD (MKT-AUDIT-9.1)."""
from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from app.marketplace.browse import BROWSE_DETAIL_COLUMNS, is_uuid
from app.marketplace.schemas import MarketplaceValidationError, validate_asset_payload
from app.workflows.audit import write_audit_event

logger = logging.getLogger(__name__)

AUDIT_ASSET_CREATED = "marketplace.asset.created"
AUDIT_ASSET_UPDATED = "marketplace.asset.updated"
AUDIT_ASSET_ARCHIVED = "marketplace.asset.archived"
RESOURCE_TYPE_MARKETPLACE_ASSET = "marketplace_asset"

_EDITABLE_STATUSES = frozenset({"draft", "pending_review"})
_ASSET_TYPES = frozenset({
    "ai_agent",
    "workflow",
    "knowledge_pack",
    "department_pack",
    "connector_config",
})
_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class MarketplaceCrudError(Exception):
    code = "MARKETPLACE_CRUD_ERROR"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        if code:
            self.code = code


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_slug(value: str) -> str:
    slug = value.strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    if not slug or not _SLUG_RE.fullmatch(slug):
        raise MarketplaceCrudError("slug must be lowercase alphanumeric with hyphens", code="VALIDATION_ERROR")
    return slug


def _fetch_asset(client: Any, asset_ref: str) -> dict[str, Any]:
    query = client.table("marketplace_assets").select("*")
    if is_uuid(asset_ref):
        query = query.eq("id", asset_ref)
    else:
        query = query.eq("slug", asset_ref)
    result = query.limit(1).execute()
    if not result.data:
        raise MarketplaceCrudError("Marketplace asset not found", code="NOT_FOUND")
    return dict(result.data[0])


def _assert_org_owns_asset(asset: dict[str, Any], org_id: str) -> None:
    asset_org = str(asset.get("org_id") or "")
    if not asset_org:
        raise MarketplaceCrudError(
            "Only org-owned marketplace assets can be modified",
            code="FORBIDDEN",
        )
    if asset_org != org_id:
        raise MarketplaceCrudError(
            "Marketplace asset belongs to another organization",
            code="FORBIDDEN",
        )


def _serialize_asset(row: dict[str, Any]) -> dict[str, Any]:
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
        "config": row.get("config") or {},
        "requiredConnectors": row.get("required_connectors") or [],
        "requiredPermissions": row.get("required_permissions") or [],
        "installVariables": row.get("install_variables") or [],
        "businessOutcome": row.get("business_outcome"),
        "useCase": row.get("use_case"),
        "estimatedHoursSaved": row.get("estimated_hours_saved"),
        "reviewFeedback": row.get("review_feedback"),
        "currentVersion": row.get("current_version"),
        "orgId": row.get("org_id"),
        "publisherId": row.get("publisher_id"),
        "createdAt": row.get("created_at"),
        "updatedAt": row.get("updated_at"),
    }


def resolve_org_publisher_id(client: Any, org_id: str, *, org_name: str | None = None) -> str:
    """Return marketplace_publishers row for org, creating one if needed."""
    result = (
        client.table("marketplace_publishers")
        .select("id, slug")
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    )
    if result.data:
        return str(result.data[0]["id"])

    slug_base = f"org-{org_id.split('-')[0]}"
    slug = slug_base
    for index in range(100):
        candidate = slug if index == 0 else f"{slug_base}-{index}"
        exists = (
            client.table("marketplace_publishers")
            .select("id")
            .eq("slug", candidate)
            .limit(1)
            .execute()
        )
        if not exists.data:
            slug = candidate
            break

    display = org_name or f"Organization {org_id[:8]}"
    inserted = (
        client.table("marketplace_publishers")
        .insert(
            {
                "slug": slug,
                "display_name": display,
                "org_id": org_id,
                "description": "Organization marketplace publisher",
                "verified": False,
                "status": "active",
            }
        )
        .execute()
    )
    return str((inserted.data or [{"id": ""}])[0]["id"])


def create_org_asset(
    client: Any,
    org_id: str,
    *,
    actor_id: str,
    org_name: str | None = None,
    slug: str,
    title: str,
    asset_type: str,
    config: dict[str, Any],
    description: str | None = None,
    category: str | None = None,
    department: str | None = None,
    tags: list[str] | None = None,
    required_connectors: list[Any] | None = None,
    required_permissions: list[Any] | None = None,
    install_variables: list[Any] | None = None,
    business_outcome: str | None = None,
    use_case: str | None = None,
    estimated_hours_saved: float | None = None,
) -> dict[str, Any]:
    if asset_type not in _ASSET_TYPES:
        raise MarketplaceCrudError(f"invalid asset_type: {asset_type}", code="VALIDATION_ERROR")

    normalized_slug = _normalize_slug(slug)
    existing = (
        client.table("marketplace_assets")
        .select("id")
        .eq("slug", normalized_slug)
        .limit(1)
        .execute()
    )
    if existing.data:
        raise MarketplaceCrudError(f"slug already exists: {normalized_slug}", code="CONFLICT")

    try:
        validated = validate_asset_payload(
            asset_type=asset_type,
            config=config,
            install_variables=install_variables,
            required_connectors=required_connectors,
            publish=False,
        )
    except MarketplaceValidationError as exc:
        raise MarketplaceCrudError(exc.message, code="VALIDATION_ERROR") from exc

    publisher_id = resolve_org_publisher_id(client, org_id, org_name=org_name)
    now = _now()
    row = {
        "publisher_id": publisher_id,
        "org_id": org_id,
        "slug": normalized_slug,
        "title": title.strip(),
        "description": description,
        "asset_type": asset_type,
        "category": category or asset_type,
        "department": department,
        "tags": tags or [],
        "visibility": "private",
        "status": "draft",
        "pricing_type": "free",
        "price_cents": 0,
        "currency": "usd",
        "config": validated["config"],
        "required_connectors": validated["required_connectors"],
        "required_permissions": required_permissions or [],
        "install_variables": validated["install_variables"],
        "business_outcome": business_outcome,
        "use_case": use_case,
        "estimated_hours_saved": estimated_hours_saved,
        "current_version": 1,
        "created_by": actor_id,
        "updated_at": now,
    }
    result = client.table("marketplace_assets").insert(row).execute()
    created = dict((result.data or [row])[0])

    client.table("marketplace_asset_versions").insert(
        {
            "asset_id": created["id"],
            "version_number": 1,
            "config": validated["config"],
            "required_connectors": validated["required_connectors"],
            "required_permissions": required_permissions or [],
            "install_variables": validated["install_variables"],
            "change_summary": "Initial draft",
            "published_by": actor_id,
        }
    ).execute()

    write_audit_event(
        client,
        org_id=org_id,
        actor_id=actor_id,
        action=AUDIT_ASSET_CREATED,
        resource_type=RESOURCE_TYPE_MARKETPLACE_ASSET,
        resource_id=str(created["id"]),
        metadata={"slug": normalized_slug, "assetType": asset_type, "status": "draft"},
    )
    return {"created": True, "asset": _serialize_asset(created)}


def update_org_asset(
    client: Any,
    org_id: str,
    asset_ref: str,
    *,
    actor_id: str,
    patch: dict[str, Any],
) -> dict[str, Any]:
    asset = _fetch_asset(client, asset_ref)
    _assert_org_owns_asset(asset, org_id)

    status = str(asset.get("status") or "")
    if status not in _EDITABLE_STATUSES:
        raise MarketplaceCrudError(
            "Published assets cannot be patched directly; use version rollback or publish workflow",
            code="FORBIDDEN",
        )

    asset_type = str(patch.get("asset_type") or asset.get("asset_type"))
    config = patch.get("config", asset.get("config") or {})
    install_variables = patch.get("install_variables", asset.get("install_variables"))
    required_connectors = patch.get("required_connectors", asset.get("required_connectors"))

    try:
        validated = validate_asset_payload(
            asset_type=asset_type,
            config=config,
            install_variables=install_variables,
            required_connectors=required_connectors,
            publish=False,
        )
    except MarketplaceValidationError as exc:
        raise MarketplaceCrudError(exc.message, code="VALIDATION_ERROR") from exc

    update_row: dict[str, Any] = {
        "config": validated["config"],
        "required_connectors": validated["required_connectors"],
        "install_variables": validated["install_variables"],
        "updated_at": _now(),
    }

    for field, column in (
        ("title", "title"),
        ("description", "description"),
        ("category", "category"),
        ("department", "department"),
        ("tags", "tags"),
        ("required_permissions", "required_permissions"),
        ("business_outcome", "business_outcome"),
        ("use_case", "use_case"),
        ("estimated_hours_saved", "estimated_hours_saved"),
    ):
        if field in patch:
            update_row[column] = patch[field]

    if "slug" in patch and patch["slug"]:
        new_slug = _normalize_slug(str(patch["slug"]))
        if new_slug != asset.get("slug"):
            conflict = (
                client.table("marketplace_assets")
                .select("id")
                .eq("slug", new_slug)
                .limit(1)
                .execute()
            )
            if conflict.data and str(conflict.data[0]["id"]) != str(asset["id"]):
                raise MarketplaceCrudError(f"slug already exists: {new_slug}", code="CONFLICT")
            update_row["slug"] = new_slug

    client.table("marketplace_assets").update(update_row).eq("id", asset["id"]).execute()
    refreshed = _fetch_asset(client, str(asset["id"]))

    write_audit_event(
        client,
        org_id=org_id,
        actor_id=actor_id,
        action=AUDIT_ASSET_UPDATED,
        resource_type=RESOURCE_TYPE_MARKETPLACE_ASSET,
        resource_id=str(asset["id"]),
        metadata={"slug": refreshed.get("slug"), "status": refreshed.get("status")},
    )
    return {"updated": True, "asset": _serialize_asset(refreshed)}


def archive_org_asset(
    client: Any,
    org_id: str,
    asset_ref: str,
    *,
    actor_id: str,
) -> dict[str, Any]:
    asset = _fetch_asset(client, asset_ref)
    _assert_org_owns_asset(asset, org_id)

    if asset.get("status") == "archived":
        return {"archived": True, "asset": _serialize_asset(asset)}

    client.table("marketplace_assets").update(
        {"status": "archived", "updated_at": _now()}
    ).eq("id", asset["id"]).execute()
    refreshed = _fetch_asset(client, str(asset["id"]))

    write_audit_event(
        client,
        org_id=org_id,
        actor_id=actor_id,
        action=AUDIT_ASSET_ARCHIVED,
        resource_type=RESOURCE_TYPE_MARKETPLACE_ASSET,
        resource_id=str(asset["id"]),
        metadata={"slug": refreshed.get("slug")},
    )
    return {"archived": True, "asset": _serialize_asset(refreshed)}


def fetch_archived_asset_for_install_lookup(client: Any, asset_id: str) -> dict[str, Any] | None:
    """Allow install records to resolve archived assets via version snapshots."""
    try:
        asset_uuid = uuid.UUID(asset_id)
    except ValueError:
        return None
    result = (
        client.table("marketplace_assets")
        .select(BROWSE_DETAIL_COLUMNS)
        .eq("id", str(asset_uuid))
        .limit(1)
        .execute()
    )
    if not result.data:
        return None
    return dict(result.data[0])
