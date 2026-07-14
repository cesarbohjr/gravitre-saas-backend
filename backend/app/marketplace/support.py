"""Marketplace supporting endpoints — installs, reviews, saves, categories, analytics (MKT-5.3)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.marketplace.adoption import count_adoption_events, top_assets_by_adoption
from app.marketplace.browse import (
    BROWSE_LIST_COLUMNS,
    MarketplaceBrowseError,
    resolve_browsable_asset,
)

_INSTALL_STATUSES = frozenset({"active", "failed", "uninstalled"})

INSTALL_LIST_COLUMNS = (
    "id, org_id, asset_id, asset_version, installed_entity_type, installed_entity_id, "
    "install_variables, status, installed_by, installed_at, updated_at, metadata"
)


class MarketplaceSupportError(Exception):
    code = "MARKETPLACE_SUPPORT_ERROR"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        if code:
            self.code = code


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _entity_deep_link(entity_type: str, entity_id: str, metadata: dict[str, Any]) -> str | None:
    if entity_type in {"operator", "agent"}:
        return f"/agents/{entity_id}"
    if entity_type == "workflow":
        return f"/workflows/{entity_id}"
    if entity_type == "rag_source":
        return f"/sources/{entity_id}"
    if entity_type == "connector":
        connector_type = metadata.get("connectorType") or metadata.get("connector_type")
        if connector_type:
            return f"/connectors?type={connector_type}"
        return "/connectors"
    return None


def _metadata_id_list(metadata: dict[str, Any], *, plural_key: str, singular_key: str) -> list[str]:
    """Prefer plural arrays; fall back to singular ids written by single-entity installs."""
    values = metadata.get(plural_key)
    out: list[str] = []
    if isinstance(values, list):
        out.extend(str(v) for v in values if v)
    singular = metadata.get(singular_key)
    if singular and str(singular) not in out:
        out.append(str(singular))
    return out


def build_install_deep_links(row: dict[str, Any]) -> list[dict[str, Any]]:
    metadata = row.get("metadata") or {}
    if not isinstance(metadata, dict):
        metadata = {}
    links: list[dict[str, Any]] = []
    seen_paths: set[str] = set()

    def add(label: str, entity_type: str, entity_id: str, path: str) -> None:
        if path in seen_paths:
            return
        seen_paths.add(path)
        links.append(
            {
                "label": label,
                "entityType": entity_type,
                "entityId": entity_id,
                "path": path,
            }
        )

    primary_path = _entity_deep_link(
        str(row.get("installed_entity_type") or ""),
        str(row.get("installed_entity_id") or ""),
        metadata,
    )
    if primary_path:
        add(
            "Primary",
            str(row.get("installed_entity_type") or ""),
            str(row.get("installed_entity_id") or ""),
            primary_path,
        )

    for agent_id in _metadata_id_list(metadata, plural_key="agentIds", singular_key="agentId"):
        add("Agent", "agent", agent_id, f"/agents/{agent_id}")
    operator_id = metadata.get("operatorId")
    if operator_id:
        add("Operator", "operator", str(operator_id), f"/agents/{operator_id}")
    for workflow_id in _metadata_id_list(metadata, plural_key="workflowIds", singular_key="workflowId"):
        add("Workflow", "workflow", workflow_id, f"/workflows/{workflow_id}")
    for source_id in _metadata_id_list(metadata, plural_key="ragSourceIds", singular_key="ragSourceId"):
        add("Knowledge source", "rag_source", source_id, f"/sources/{source_id}")

    return links


def _serialize_install_row(row: dict[str, Any], asset: dict[str, Any] | None = None) -> dict[str, Any]:
    asset_row = asset or row.get("marketplace_assets") or {}
    if isinstance(asset_row, list):
        asset_row = asset_row[0] if asset_row else {}
    return {
        "id": row["id"],
        "assetId": row["asset_id"],
        "assetVersion": row.get("asset_version"),
        "status": row.get("status"),
        "installedEntityType": row.get("installed_entity_type"),
        "installedEntityId": row.get("installed_entity_id"),
        "installVariables": row.get("install_variables") or {},
        "installedBy": row.get("installed_by"),
        "installedAt": row.get("installed_at"),
        "updatedAt": row.get("updated_at"),
        "metadata": row.get("metadata") or {},
        "deepLinks": build_install_deep_links(row),
        "asset": {
            "id": asset_row.get("id"),
            "slug": asset_row.get("slug"),
            "title": asset_row.get("title"),
            "assetType": asset_row.get("asset_type"),
            "category": asset_row.get("category"),
            "department": asset_row.get("department"),
        }
        if asset_row
        else None,
    }


def _serialize_review_row(row: dict[str, Any], *, mine: bool = False) -> dict[str, Any]:
    payload = {
        "id": row["id"],
        "assetId": row["asset_id"],
        "rating": row["rating"],
        "title": row.get("title"),
        "body": row.get("body"),
        "createdAt": row.get("created_at"),
        "updatedAt": row.get("updated_at"),
    }
    if mine:
        payload["orgId"] = row.get("org_id")
        payload["userId"] = row.get("user_id")
    return payload


def _serialize_save_row(row: dict[str, Any], asset: dict[str, Any] | None = None) -> dict[str, Any]:
    asset_row = asset or row.get("marketplace_assets") or {}
    if isinstance(asset_row, list):
        asset_row = asset_row[0] if asset_row else {}
    return {
        "id": row["id"],
        "assetId": row["asset_id"],
        "createdAt": row.get("created_at"),
        "asset": {
            "id": asset_row.get("id"),
            "slug": asset_row.get("slug"),
            "title": asset_row.get("title"),
            "assetType": asset_row.get("asset_type"),
            "category": asset_row.get("category"),
            "department": asset_row.get("department"),
            "pricingType": asset_row.get("pricing_type"),
        }
        if asset_row
        else None,
    }


def _refresh_asset_review_stats(client: Any, asset_id: str) -> None:
    reviews = (
        client.table("marketplace_reviews")
        .select("rating")
        .eq("asset_id", asset_id)
        .execute()
    )
    ratings = [int(row["rating"]) for row in (reviews.data or []) if row.get("rating") is not None]
    count = len(ratings)
    average = round(sum(ratings) / count, 2) if count else None
    client.table("marketplace_assets").update(
        {"review_count": count, "average_rating": average, "updated_at": _now()}
    ).eq("id", asset_id).execute()


def _published_catalog_query(client: Any, org_id: str):
    return (
        client.table("marketplace_assets")
        .select(BROWSE_LIST_COLUMNS)
        .eq("status", "published")
        .or_(f"visibility.eq.public,and(visibility.eq.internal,org_id.eq.{org_id})")
    )


def list_org_installs(
    client: Any,
    org_id: str,
    *,
    status: str | None = "active",
    asset_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    if status and status not in _INSTALL_STATUSES:
        raise MarketplaceSupportError(f"invalid status: {status}", code="VALIDATION_ERROR")

    limit = max(1, min(limit, 100))
    offset = max(0, offset)

    query = (
        client.table("marketplace_installs")
        .select(
            f"{INSTALL_LIST_COLUMNS}, marketplace_assets(id, slug, title, asset_type, category, department)",
            count="exact",
        )
        .eq("org_id", org_id)
    )
    if status:
        query = query.eq("status", status)
    if asset_id:
        query = query.eq("asset_id", asset_id)

    result = query.order("installed_at", desc=True).range(offset, offset + limit - 1).execute()
    installs = [_serialize_install_row(dict(row)) for row in (result.data or [])]
    total = getattr(result, "count", None)
    if total is None:
        total = len(installs) + offset
    return {"installs": installs, "total": total, "limit": limit, "offset": offset}


AUDIT_ASSET_UNINSTALLED = "marketplace.asset.uninstalled"


def _deactivate_install_entities(
    client: Any,
    org_id: str,
    *,
    entity_type: str | None,
    entity_id: str | None,
    metadata: dict[str, Any],
) -> dict[str, list[str]]:
    """Soft-deactivate agents/workflows/RAG spawned by a marketplace install."""
    now = _now()
    deactivated: dict[str, list[str]] = {"agents": [], "workflows": [], "ragSources": []}

    agent_ids: list[str] = []
    for raw in metadata.get("agentIds") or []:
        if raw:
            agent_ids.append(str(raw))
    if entity_type in {"operator", "agent", "ai_agent"} and entity_id:
        agent_ids.append(str(entity_id))
    for agent_id in dict.fromkeys(agent_ids):
        try:
            client.table("operators").update(
                {"deleted_at": now, "status": "inactive", "updated_at": now}
            ).eq("id", agent_id).eq("org_id", org_id).execute()
            deactivated["agents"].append(agent_id)
        except Exception:  # noqa: BLE001
            continue

    workflow_ids: list[str] = []
    for raw in metadata.get("workflowIds") or []:
        if raw:
            workflow_ids.append(str(raw))
    if entity_type == "workflow" and entity_id:
        workflow_ids.append(str(entity_id))
    for workflow_id in dict.fromkeys(workflow_ids):
        try:
            client.table("workflow_defs").update(
                {"status": "archived", "updated_at": now}
            ).eq("id", workflow_id).eq("org_id", org_id).execute()
            client.table("workflows").update(
                {"status": "archived", "updated_at": now}
            ).eq("id", workflow_id).eq("org_id", org_id).execute()
            deactivated["workflows"].append(workflow_id)
        except Exception:  # noqa: BLE001
            continue

    rag_ids: list[str] = []
    for raw in metadata.get("ragSourceIds") or []:
        if raw:
            rag_ids.append(str(raw))
    if entity_type == "rag_source" and entity_id:
        rag_ids.append(str(entity_id))
    for rag_id in dict.fromkeys(rag_ids):
        try:
            client.table("rag_sources").update(
                {"status": "inactive", "updated_at": now}
            ).eq("id", rag_id).eq("org_id", org_id).execute()
            deactivated["ragSources"].append(rag_id)
        except Exception:  # noqa: BLE001
            continue

    return deactivated


def _deactivate_legacy_department_pack(client: Any, org_id: str, slug: str | None) -> bool:
    if not slug:
        return False
    try:
        result = (
            client.table("org_department_pack_installs")
            .update({"status": "uninstalled", "updated_at": _now()})
            .eq("org_id", org_id)
            .eq("pack_id", slug)
            .eq("status", "active")
            .execute()
        )
        return bool(result.data)
    except Exception:  # noqa: BLE001
        return False


def uninstall_marketplace_asset(
    client: Any,
    org_id: str,
    asset_ref: str,
    *,
    actor_id: str,
) -> dict[str, Any]:
    """Uninstall ledger row and soft-deactivate spawned entities (Part D P4 / STA-309)."""
    asset = resolve_browsable_asset(client, org_id, asset_ref)
    existing = (
        client.table("marketplace_installs")
        .select(
            "id, status, installed_entity_type, installed_entity_id, metadata"
        )
        .eq("org_id", org_id)
        .eq("asset_id", asset["id"])
        .eq("status", "active")
        .limit(1)
        .execute()
    )
    if not existing.data:
        raise MarketplaceSupportError("No active install found for this asset", code="NOT_FOUND")

    install_row = existing.data[0]
    install_id = str(install_row["id"])
    metadata = dict(install_row.get("metadata") or {})
    deactivated = _deactivate_install_entities(
        client,
        org_id,
        entity_type=install_row.get("installed_entity_type"),
        entity_id=install_row.get("installed_entity_id"),
        metadata=metadata,
    )
    legacy_cleared = _deactivate_legacy_department_pack(client, org_id, asset.get("slug"))

    now = _now()
    client.table("marketplace_installs").update(
        {
            "status": "uninstalled",
            "updated_at": now,
            "metadata": {**metadata, "deactivatedOnUninstall": deactivated},
        }
    ).eq("id", install_id).execute()

    from app.workflows.audit import write_audit_event

    write_audit_event(
        client,
        org_id=org_id,
        actor_id=actor_id,
        action=AUDIT_ASSET_UNINSTALLED,
        resource_type="marketplace_install",
        resource_id=install_id,
        metadata={
            "assetId": asset["id"],
            "slug": asset.get("slug"),
            "deactivated": deactivated,
            "legacyDepartmentPackCleared": legacy_cleared,
        },
    )
    return {
        "uninstalled": True,
        "installId": install_id,
        "assetId": asset["id"],
        "slug": asset.get("slug"),
        "deactivated": deactivated,
        "legacyDepartmentPackCleared": legacy_cleared,
    }


def list_asset_reviews(
    client: Any,
    org_id: str,
    user_id: str,
    asset_ref: str,
    *,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    asset = resolve_browsable_asset(client, org_id, asset_ref)
    limit = max(1, min(limit, 100))
    offset = max(0, offset)

    result = (
        client.table("marketplace_reviews")
        .select("id, asset_id, rating, title, body, created_at, updated_at", count="exact")
        .eq("asset_id", asset["id"])
        .order("created_at", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )
    reviews = [_serialize_review_row(dict(row)) for row in (result.data or [])]
    mine = (
        client.table("marketplace_reviews")
        .select("*")
        .eq("asset_id", asset["id"])
        .eq("org_id", org_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    my_review = _serialize_review_row(dict(mine.data[0]), mine=True) if mine.data else None
    total = getattr(result, "count", None)
    if total is None:
        total = len(reviews) + offset
    return {
        "assetId": asset["id"],
        "reviews": reviews,
        "myReview": my_review,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def upsert_my_asset_review(
    client: Any,
    org_id: str,
    user_id: str,
    asset_ref: str,
    *,
    rating: int,
    title: str | None = None,
    body: str | None = None,
) -> dict[str, Any]:
    if rating < 1 or rating > 5:
        raise MarketplaceSupportError("rating must be between 1 and 5", code="VALIDATION_ERROR")
    asset = resolve_browsable_asset(client, org_id, asset_ref)
    row = {
        "asset_id": asset["id"],
        "org_id": org_id,
        "user_id": user_id,
        "rating": rating,
        "title": title,
        "body": body,
        "updated_at": _now(),
    }
    result = (
        client.table("marketplace_reviews")
        .upsert(row, on_conflict="asset_id,org_id,user_id")
        .execute()
    )
    saved = dict((result.data or [row])[0])
    _refresh_asset_review_stats(client, str(asset["id"]))
    return {"review": _serialize_review_row(saved, mine=True)}


def delete_my_asset_review(
    client: Any,
    org_id: str,
    user_id: str,
    asset_ref: str,
) -> dict[str, Any]:
    asset = resolve_browsable_asset(client, org_id, asset_ref)
    existing = (
        client.table("marketplace_reviews")
        .select("id")
        .eq("asset_id", asset["id"])
        .eq("org_id", org_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    if not existing.data:
        raise MarketplaceSupportError("Review not found", code="NOT_FOUND")
    client.table("marketplace_reviews").delete().eq("id", existing.data[0]["id"]).execute()
    _refresh_asset_review_stats(client, str(asset["id"]))
    return {"deleted": True, "assetId": asset["id"]}


def list_my_saves(
    client: Any,
    org_id: str,
    user_id: str,
    *,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    limit = max(1, min(limit, 100))
    offset = max(0, offset)

    result = (
        client.table("marketplace_saves")
        .select(
            f"id, asset_id, created_at, marketplace_assets({BROWSE_LIST_COLUMNS})",
            count="exact",
        )
        .eq("org_id", org_id)
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )
    saves = [_serialize_save_row(dict(row)) for row in (result.data or [])]
    total = getattr(result, "count", None)
    if total is None:
        total = len(saves) + offset
    return {"saves": saves, "total": total, "limit": limit, "offset": offset}


def save_asset(
    client: Any,
    org_id: str,
    user_id: str,
    asset_ref: str,
) -> dict[str, Any]:
    asset = resolve_browsable_asset(client, org_id, asset_ref)
    row = {
        "asset_id": asset["id"],
        "org_id": org_id,
        "user_id": user_id,
    }
    result = client.table("marketplace_saves").upsert(row, on_conflict="asset_id,org_id,user_id").execute()
    saved = dict((result.data or [row])[0])
    return {"saved": True, "save": _serialize_save_row(saved, asset=asset)}


def unsave_asset(
    client: Any,
    org_id: str,
    user_id: str,
    asset_ref: str,
) -> dict[str, Any]:
    asset = resolve_browsable_asset(client, org_id, asset_ref)
    existing = (
        client.table("marketplace_saves")
        .select("id")
        .eq("asset_id", asset["id"])
        .eq("org_id", org_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    if not existing.data:
        raise MarketplaceSupportError("Save not found", code="NOT_FOUND")
    client.table("marketplace_saves").delete().eq("id", existing.data[0]["id"]).execute()
    return {"saved": False, "assetId": asset["id"]}


def list_marketplace_categories(client: Any, org_id: str) -> dict[str, Any]:
    result = (
        _published_catalog_query(client, org_id)
        .select("category, department, asset_type")
        .execute()
    )
    by_category: dict[str, int] = {}
    by_department: dict[str, int] = {}
    by_asset_type: dict[str, int] = {}
    for row in result.data or []:
        category = str(row.get("category") or "uncategorized")
        department = str(row.get("department") or "general")
        asset_type = str(row.get("asset_type") or "unknown")
        by_category[category] = by_category.get(category, 0) + 1
        by_department[department] = by_department.get(department, 0) + 1
        by_asset_type[asset_type] = by_asset_type.get(asset_type, 0) + 1

    def _sorted_counts(values: dict[str, int]) -> list[dict[str, Any]]:
        return [
            {"key": key, "count": count}
            for key, count in sorted(values.items(), key=lambda item: (-item[1], item[0]))
        ]

    return {
        "categories": _sorted_counts(by_category),
        "departments": _sorted_counts(by_department),
        "assetTypes": _sorted_counts(by_asset_type),
        "totalAssets": len(result.data or []),
    }


def marketplace_analytics_summary(client: Any, org_id: str) -> dict[str, Any]:
    categories = list_marketplace_categories(client, org_id)

    installs = (
        client.table("marketplace_installs")
        .select("id", count="exact")
        .eq("org_id", org_id)
        .eq("status", "active")
        .execute()
    )
    saves = (
        client.table("marketplace_saves")
        .select("id", count="exact")
        .eq("org_id", org_id)
        .execute()
    )
    reviews = (
        client.table("marketplace_reviews")
        .select("id", count="exact")
        .eq("org_id", org_id)
        .execute()
    )

    catalog_assets = (
        _published_catalog_query(client, org_id)
        .select("install_count, clone_count")
        .execute()
    )
    total_install_count = sum(int(row.get("install_count") or 0) for row in (catalog_assets.data or []))
    total_clone_count = sum(int(row.get("clone_count") or 0) for row in (catalog_assets.data or []))

    return {
        "catalog": {
            "totalAssets": categories["totalAssets"],
            "byCategory": categories["categories"],
            "byDepartment": categories["departments"],
            "byAssetType": categories["assetTypes"],
            "totalInstallCount": total_install_count,
            "totalCloneCount": total_clone_count,
        },
        "org": {
            "activeInstalls": getattr(installs, "count", None) or len(installs.data or []),
            "savedAssets": getattr(saves, "count", None) or len(saves.data or []),
            "reviewsSubmitted": getattr(reviews, "count", None) or len(reviews.data or []),
            "usageEvents": count_adoption_events(client, org_id),
            "topAssetsByUsage": top_assets_by_adoption(client, org_id, limit=10),
        },
    }


def support_error_to_browse_error(exc: MarketplaceSupportError) -> MarketplaceBrowseError:
    return MarketplaceBrowseError(str(exc), code=exc.code)
