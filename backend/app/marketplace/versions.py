"""Marketplace asset version history and rollback (MKT-9.4)."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.marketplace.browse import is_uuid
from app.marketplace.schemas import MarketplaceValidationError, validate_asset_payload
from app.workflows.audit import write_audit_event

logger = logging.getLogger(__name__)

AUDIT_ASSET_ROLLED_BACK = "marketplace.asset.rolled_back"
RESOURCE_TYPE_MARKETPLACE_ASSET = "marketplace_asset"

VERSION_LIST_COLUMNS = (
    "id, asset_id, version_number, change_summary, published_at, published_by"
)


class MarketplaceVersionError(Exception):
    code = "MARKETPLACE_VERSION_ERROR"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        if code:
            self.code = code


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fetch_asset_row(client: Any, asset_ref: str) -> dict[str, Any]:
    query = client.table("marketplace_assets").select("*")
    if is_uuid(asset_ref):
        query = query.eq("id", asset_ref)
    else:
        query = query.eq("slug", asset_ref)
    result = query.limit(1).execute()
    if not result.data:
        raise MarketplaceVersionError("Marketplace asset not found", code="NOT_FOUND")
    return dict(result.data[0])


def _assert_org_may_manage_asset(asset: dict[str, Any], org_id: str) -> None:
    asset_org = str(asset.get("org_id") or "")
    if not asset_org:
        raise MarketplaceVersionError(
            "Only org-owned marketplace assets can be version-managed",
            code="FORBIDDEN",
        )
    if asset_org != org_id:
        raise MarketplaceVersionError(
            "Marketplace asset belongs to another organization",
            code="FORBIDDEN",
        )


def _fetch_version_row(client: Any, asset_id: str, version_number: int) -> dict[str, Any]:
    result = (
        client.table("marketplace_asset_versions")
        .select("*")
        .eq("asset_id", asset_id)
        .eq("version_number", version_number)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise MarketplaceVersionError(
            f"Version {version_number} not found for asset",
            code="NOT_FOUND",
        )
    return dict(result.data[0])


def list_asset_versions(client: Any, org_id: str, asset_ref: str) -> dict[str, Any]:
    """Return version history for an org-owned asset."""
    asset = _fetch_asset_row(client, asset_ref)
    _assert_org_may_manage_asset(asset, org_id)
    result = (
        client.table("marketplace_asset_versions")
        .select(VERSION_LIST_COLUMNS)
        .eq("asset_id", asset["id"])
        .order("version_number", desc=True)
        .execute()
    )
    current_version = int(asset.get("current_version") or 1)
    versions = [
        {
            "versionNumber": row["version_number"],
            "changeSummary": row.get("change_summary"),
            "publishedAt": row.get("published_at"),
            "publishedBy": row.get("published_by"),
            "isCurrent": int(row["version_number"]) == current_version,
        }
        for row in (result.data or [])
    ]
    return {
        "assetId": asset["id"],
        "slug": asset.get("slug"),
        "currentVersion": current_version,
        "versions": versions,
    }


def rollback_asset_version(
    client: Any,
    org_id: str,
    asset_ref: str,
    *,
    version_number: int,
    actor_id: str,
) -> dict[str, Any]:
    """Restore an org-owned asset's live config from ``marketplace_asset_versions``."""
    if version_number < 1:
        raise MarketplaceVersionError("version must be >= 1", code="VALIDATION_ERROR")

    asset = _fetch_asset_row(client, asset_ref)
    _assert_org_may_manage_asset(asset, org_id)
    current_version = int(asset.get("current_version") or 1)
    if version_number == current_version:
        raise MarketplaceVersionError(
            f"Asset is already on version {current_version}",
            code="ALREADY_CURRENT",
        )

    version_row = _fetch_version_row(client, str(asset["id"]), version_number)
    config = version_row.get("config") or {}
    install_variables = version_row.get("install_variables") or []
    required_connectors = version_row.get("required_connectors") or []
    try:
        validated = validate_asset_payload(
            asset_type=str(asset["asset_type"]),
            config=config,
            install_variables=install_variables,
            required_connectors=required_connectors,
            publish=True,
        )
    except MarketplaceValidationError as exc:
        raise MarketplaceVersionError(exc.message, code="VALIDATION_ERROR") from exc

    previous_version = current_version
    update_row = {
        "config": validated["config"],
        "required_connectors": validated["required_connectors"],
        "install_variables": validated["install_variables"],
        "required_permissions": version_row.get("required_permissions") or [],
        "current_version": version_number,
        "updated_at": _now(),
    }
    client.table("marketplace_assets").update(update_row).eq("id", asset["id"]).execute()

    write_audit_event(
        client,
        org_id=org_id,
        actor_id=actor_id,
        action=AUDIT_ASSET_ROLLED_BACK,
        resource_type=RESOURCE_TYPE_MARKETPLACE_ASSET,
        resource_id=str(asset["id"]),
        metadata={
            "assetSlug": asset.get("slug"),
            "fromVersion": previous_version,
            "toVersion": version_number,
            "changeSummary": version_row.get("change_summary"),
        },
    )
    logger.info(
        "marketplace_asset_rolled_back org_id=%s asset_id=%s from=%s to=%s",
        org_id,
        asset["id"],
        previous_version,
        version_number,
    )
    return {
        "rolledBack": True,
        "assetId": asset["id"],
        "slug": asset.get("slug"),
        "previousVersion": previous_version,
        "currentVersion": version_number,
        "restoredFromVersion": version_number,
    }
