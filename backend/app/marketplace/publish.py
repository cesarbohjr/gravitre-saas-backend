"""Internal org publish workflow (MKT-AUDIT-9.2)."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.marketplace.crud import MarketplaceCrudError, _fetch_asset, _serialize_asset, _assert_org_owns_asset
from app.marketplace.publishers import assert_org_can_publish_publicly
from app.marketplace.schemas import MarketplaceValidationError, validate_asset_payload
from app.workflows.audit import write_audit_event

logger = logging.getLogger(__name__)

AUDIT_ASSET_SUBMITTED = "marketplace.asset.submitted_for_review"
AUDIT_ASSET_APPROVED = "marketplace.asset.approved"
AUDIT_ASSET_REJECTED = "marketplace.asset.rejected"
RESOURCE_TYPE_MARKETPLACE_ASSET = "marketplace_asset"


class MarketplacePublishError(Exception):
    code = "MARKETPLACE_PUBLISH_ERROR"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        if code:
            self.code = code


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _crud_to_publish(exc: MarketplaceCrudError) -> MarketplacePublishError:
    return MarketplacePublishError(str(exc), code=exc.code)


def _snapshot_version(
    client: Any,
    asset: dict[str, Any],
    *,
    actor_id: str,
    change_summary: str,
    validated: dict[str, Any],
) -> int:
    next_version = int(asset.get("current_version") or 1) + 1
    client.table("marketplace_asset_versions").insert(
        {
            "asset_id": asset["id"],
            "version_number": next_version,
            "config": validated["config"],
            "required_connectors": validated["required_connectors"],
            "required_permissions": asset.get("required_permissions") or [],
            "install_variables": validated["install_variables"],
            "change_summary": change_summary,
            "published_at": _now(),
            "published_by": actor_id,
        }
    ).execute()
    return next_version


def submit_asset_for_review(
    client: Any,
    org_id: str,
    asset_ref: str,
    *,
    actor_id: str,
) -> dict[str, Any]:
    try:
        asset = _fetch_asset(client, asset_ref)
        _assert_org_owns_asset(asset, org_id)
    except MarketplaceCrudError as exc:
        raise _crud_to_publish(exc) from exc

    if asset.get("status") != "draft":
        raise MarketplacePublishError(
            "Only draft assets can be submitted for review",
            code="VALIDATION_ERROR",
        )

    try:
        validated = validate_asset_payload(
            asset_type=str(asset["asset_type"]),
            config=asset.get("config") or {},
            install_variables=asset.get("install_variables"),
            required_connectors=asset.get("required_connectors"),
            publish=True,
        )
    except MarketplaceValidationError as exc:
        raise MarketplacePublishError(exc.message, code="VALIDATION_ERROR") from exc

    client.table("marketplace_assets").update(
        {
            "status": "pending_review",
            "review_scope": "internal",
            "config": validated["config"],
            "required_connectors": validated["required_connectors"],
            "install_variables": validated["install_variables"],
            "review_feedback": None,
            "updated_at": _now(),
        }
    ).eq("id", asset["id"]).execute()
    refreshed = _fetch_asset(client, str(asset["id"]))

    write_audit_event(
        client,
        org_id=org_id,
        actor_id=actor_id,
        action=AUDIT_ASSET_SUBMITTED,
        resource_type=RESOURCE_TYPE_MARKETPLACE_ASSET,
        resource_id=str(asset["id"]),
        metadata={"slug": refreshed.get("slug")},
    )
    return {"submitted": True, "asset": _serialize_asset(refreshed)}


def approve_asset_for_internal_publish(
    client: Any,
    org_id: str,
    asset_ref: str,
    *,
    actor_id: str,
) -> dict[str, Any]:
    try:
        asset = _fetch_asset(client, asset_ref)
        _assert_org_owns_asset(asset, org_id)
    except MarketplaceCrudError as exc:
        raise _crud_to_publish(exc) from exc

    if asset.get("status") != "pending_review":
        raise MarketplacePublishError(
            "Only pending_review assets can be approved",
            code="VALIDATION_ERROR",
        )
    if asset.get("review_scope") == "public":
        raise MarketplacePublishError(
            "Public submissions are reviewed by Gravitre platform admins",
            code="VALIDATION_ERROR",
        )

    try:
        validated = validate_asset_payload(
            asset_type=str(asset["asset_type"]),
            config=asset.get("config") or {},
            install_variables=asset.get("install_variables"),
            required_connectors=asset.get("required_connectors"),
            publish=True,
        )
    except MarketplaceValidationError as exc:
        raise MarketplacePublishError(exc.message, code="VALIDATION_ERROR") from exc

    version_number = _snapshot_version(
        client,
        asset,
        actor_id=actor_id,
        change_summary="Internal publish approval",
        validated=validated,
    )
    now = _now()
    client.table("marketplace_assets").update(
        {
            "status": "published",
            "visibility": "internal",
            "config": validated["config"],
            "required_connectors": validated["required_connectors"],
            "install_variables": validated["install_variables"],
            "current_version": version_number,
            "published_at": now,
            "published_by": actor_id,
            "review_feedback": None,
            "updated_at": now,
        }
    ).eq("id", asset["id"]).execute()
    refreshed = _fetch_asset(client, str(asset["id"]))

    write_audit_event(
        client,
        org_id=org_id,
        actor_id=actor_id,
        action=AUDIT_ASSET_APPROVED,
        resource_type=RESOURCE_TYPE_MARKETPLACE_ASSET,
        resource_id=str(asset["id"]),
        metadata={
            "slug": refreshed.get("slug"),
            "visibility": "internal",
            "version": version_number,
        },
    )
    return {"approved": True, "asset": _serialize_asset(refreshed)}


def reject_asset_review(
    client: Any,
    org_id: str,
    asset_ref: str,
    *,
    actor_id: str,
    reason: str,
) -> dict[str, Any]:
    try:
        asset = _fetch_asset(client, asset_ref)
        _assert_org_owns_asset(asset, org_id)
    except MarketplaceCrudError as exc:
        raise _crud_to_publish(exc) from exc

    if asset.get("status") != "pending_review":
        raise MarketplacePublishError(
            "Only pending_review assets can be rejected",
            code="VALIDATION_ERROR",
        )
    if asset.get("review_scope") == "public":
        raise MarketplacePublishError(
            "Public submissions are reviewed by Gravitre platform admins",
            code="VALIDATION_ERROR",
        )

    feedback = reason.strip()
    if not feedback:
        raise MarketplacePublishError("rejection reason is required", code="VALIDATION_ERROR")

    client.table("marketplace_assets").update(
        {
            "status": "draft",
            "review_feedback": feedback,
            "updated_at": _now(),
        }
    ).eq("id", asset["id"]).execute()
    refreshed = _fetch_asset(client, str(asset["id"]))

    write_audit_event(
        client,
        org_id=org_id,
        actor_id=actor_id,
        action=AUDIT_ASSET_REJECTED,
        resource_type=RESOURCE_TYPE_MARKETPLACE_ASSET,
        resource_id=str(asset["id"]),
        metadata={"slug": refreshed.get("slug"), "reason": feedback},
    )
    return {"rejected": True, "reason": feedback, "asset": _serialize_asset(refreshed)}


def submit_asset_for_public_review(
    client: Any,
    org_id: str,
    asset_ref: str,
    *,
    actor_id: str,
) -> dict[str, Any]:
    assert_org_can_publish_publicly(client, org_id)
    try:
        asset = _fetch_asset(client, asset_ref)
        _assert_org_owns_asset(asset, org_id)
    except MarketplaceCrudError as exc:
        raise _crud_to_publish(exc) from exc

    if asset.get("status") != "draft":
        raise MarketplacePublishError(
            "Only draft assets can be submitted for public review",
            code="VALIDATION_ERROR",
        )

    try:
        validated = validate_asset_payload(
            asset_type=str(asset["asset_type"]),
            config=asset.get("config") or {},
            install_variables=asset.get("install_variables"),
            required_connectors=asset.get("required_connectors"),
            publish=True,
        )
    except MarketplaceValidationError as exc:
        raise MarketplacePublishError(exc.message, code="VALIDATION_ERROR") from exc

    client.table("marketplace_assets").update(
        {
            "status": "pending_review",
            "review_scope": "public",
            "config": validated["config"],
            "required_connectors": validated["required_connectors"],
            "install_variables": validated["install_variables"],
            "review_feedback": None,
            "updated_at": _now(),
        }
    ).eq("id", asset["id"]).execute()
    refreshed = _fetch_asset(client, str(asset["id"]))

    write_audit_event(
        client,
        org_id=org_id,
        actor_id=actor_id,
        action=AUDIT_ASSET_SUBMITTED,
        resource_type=RESOURCE_TYPE_MARKETPLACE_ASSET,
        resource_id=str(asset["id"]),
        metadata={"slug": refreshed.get("slug"), "reviewScope": "public"},
    )
    return {"submitted": True, "asset": _serialize_asset(refreshed)}


def list_public_review_queue(
    client: Any,
    *,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    result = (
        client.table("marketplace_assets")
        .select("*", count="exact")
        .eq("status", "pending_review")
        .eq("review_scope", "public")
        .order("updated_at", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )
    assets: list[dict[str, Any]] = []
    for row in result.data or []:
        serialized = _serialize_asset(dict(row))
        publisher_id = row.get("publisher_id")
        if publisher_id:
            pub = (
                client.table("marketplace_publishers")
                .select("display_name, slug")
                .eq("id", publisher_id)
                .limit(1)
                .execute()
            )
            if pub.data:
                serialized["publisherDisplayName"] = pub.data[0].get("display_name")
                serialized["publisherSlug"] = pub.data[0].get("slug")
        assets.append(serialized)
    total = getattr(result, "count", None)
    if total is None:
        total = len(assets) + offset
    return {"assets": assets, "total": total, "limit": limit, "offset": offset}


def get_public_review_asset_detail(client: Any, asset_ref: str) -> dict[str, Any]:
    """Platform admin detail for a public pending_review asset (cross-org preview)."""
    asset = _fetch_asset(client, asset_ref)
    if asset.get("status") != "pending_review" or asset.get("review_scope") != "public":
        raise MarketplacePublishError(
            "Only public pending_review assets can be reviewed",
            code="NOT_FOUND",
        )
    serialized = _serialize_asset(asset)
    publisher_id = asset.get("publisher_id")
    if publisher_id:
        pub = (
            client.table("marketplace_publishers")
            .select("display_name, slug, website_url, verified")
            .eq("id", publisher_id)
            .limit(1)
            .execute()
        )
        if pub.data:
            row = pub.data[0]
            serialized["publisherDisplayName"] = row.get("display_name")
            serialized["publisherSlug"] = row.get("slug")
            serialized["publisherWebsiteUrl"] = row.get("website_url")
            serialized["publisherVerified"] = bool(row.get("verified"))
    return {"asset": serialized}


def approve_asset_for_public_publish(
    client: Any,
    asset_ref: str,
    *,
    actor_id: str,
    org_id: str | None = None,
) -> dict[str, Any]:
    asset = _fetch_asset(client, asset_ref)
    if asset.get("status") != "pending_review" or asset.get("review_scope") != "public":
        raise MarketplacePublishError(
            "Only public pending_review assets can be approved",
            code="VALIDATION_ERROR",
        )

    try:
        validated = validate_asset_payload(
            asset_type=str(asset["asset_type"]),
            config=asset.get("config") or {},
            install_variables=asset.get("install_variables"),
            required_connectors=asset.get("required_connectors"),
            publish=True,
        )
    except MarketplaceValidationError as exc:
        raise MarketplacePublishError(exc.message, code="VALIDATION_ERROR") from exc

    version_number = _snapshot_version(
        client,
        asset,
        actor_id=actor_id,
        change_summary="Public catalog publish approval",
        validated=validated,
    )
    now = _now()
    asset_org = str(asset.get("org_id") or "")
    client.table("marketplace_assets").update(
        {
            "status": "published",
            "visibility": "public",
            "review_scope": "public",
            "config": validated["config"],
            "required_connectors": validated["required_connectors"],
            "install_variables": validated["install_variables"],
            "current_version": version_number,
            "published_at": now,
            "published_by": actor_id,
            "review_feedback": None,
            "updated_at": now,
        }
    ).eq("id", asset["id"]).execute()
    refreshed = _fetch_asset(client, str(asset["id"]))

    write_audit_event(
        client,
        org_id=org_id or asset_org or "",
        actor_id=actor_id,
        action=AUDIT_ASSET_APPROVED,
        resource_type=RESOURCE_TYPE_MARKETPLACE_ASSET,
        resource_id=str(asset["id"]),
        metadata={
            "slug": refreshed.get("slug"),
            "visibility": "public",
            "version": version_number,
            "reviewScope": "public",
        },
    )
    return {"approved": True, "asset": _serialize_asset(refreshed)}


def reject_asset_public_review(
    client: Any,
    asset_ref: str,
    *,
    actor_id: str,
    reason: str,
    org_id: str | None = None,
) -> dict[str, Any]:
    asset = _fetch_asset(client, asset_ref)
    if asset.get("status") != "pending_review" or asset.get("review_scope") != "public":
        raise MarketplacePublishError(
            "Only public pending_review assets can be rejected",
            code="VALIDATION_ERROR",
        )

    feedback = reason.strip()
    if not feedback:
        raise MarketplacePublishError("rejection reason is required", code="VALIDATION_ERROR")

    client.table("marketplace_assets").update(
        {
            "status": "draft",
            "review_feedback": feedback,
            "updated_at": _now(),
        }
    ).eq("id", asset["id"]).execute()
    refreshed = _fetch_asset(client, str(asset["id"]))

    write_audit_event(
        client,
        org_id=org_id or str(asset.get("org_id") or ""),
        actor_id=actor_id,
        action=AUDIT_ASSET_REJECTED,
        resource_type=RESOURCE_TYPE_MARKETPLACE_ASSET,
        resource_id=str(asset["id"]),
        metadata={"slug": refreshed.get("slug"), "reason": feedback, "reviewScope": "public"},
    )
    return {"rejected": True, "reason": feedback, "asset": _serialize_asset(refreshed)}
