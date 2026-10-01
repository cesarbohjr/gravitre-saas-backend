"""Converge portable capabilities with the existing Gravitre Marketplace.

The Marketplace owns discovery/review/pricing/entitlement. This bridge owns the
portable package snapshot. Installing a Marketplace capability always creates a
quarantined package in the destination org; it never activates MCP/tools/scripts.
"""
from __future__ import annotations

from typing import Any

from app.capabilities.packages import PackageInspection
from app.capabilities.repository import (
    get_package,
    install_package,
    list_package_resources,
    replace_package_resources,
    record_package_version,
)
from app.marketplace.crud import create_org_asset


def _inspection_from_package(package: dict[str, Any]) -> PackageInspection:
    raw = package.get("inspection") if isinstance(package.get("inspection"), dict) else {}
    components = raw.get("components") if isinstance(raw.get("components"), list) else []
    from app.capabilities.packages import PackageComponent

    parsed_components = tuple(
        PackageComponent(
            kind=str(row.get("kind") or "skill"),  # type: ignore[arg-type]
            name=str(row.get("name") or "component"),
            source=str(row.get("source") or "") or None,
            executable=bool(row.get("executable")),
        )
        for row in components
        if isinstance(row, dict)
    )
    return PackageInspection(
        format=str(package.get("package_format") or raw.get("format") or "unknown"),  # type: ignore[arg-type]
        name=str(package.get("name") or raw.get("name") or "capability"),
        version=str(package.get("version") or raw.get("version") or "") or None,
        description=str(package.get("description") or raw.get("description") or "") or None,
        license=str(package.get("license") or raw.get("license") or "") or None,
        license_policy=str(package.get("license_policy") or raw.get("license_policy") or "review"),  # type: ignore[arg-type]
        components=parsed_components,
        permissions=tuple(str(v) for v in (raw.get("permissions") or [])),
        network_hosts=tuple(str(v) for v in (raw.get("network_hosts") or [])),
        has_executable_code=bool(raw.get("has_executable_code")),
        has_write_tools=bool(raw.get("has_write_tools")),
        risk=str(package.get("risk_level") or raw.get("risk") or "moderate"),  # type: ignore[arg-type]
        findings=tuple(str(v) for v in (raw.get("findings") or [])),
    )


def create_marketplace_asset_for_package(
    client: Any,
    *,
    org_id: str,
    package_id: str,
    actor_id: str,
    slug: str,
    title: str | None = None,
    description: str | None = None,
    pricing_type: str = "free",
    price_cents: int = 0,
) -> dict[str, Any]:
    package = get_package(client, org_id, package_id)
    if not package:
        raise ValueError("Capability package not found")
    if str(package.get("status") or "") != "installed":
        raise ValueError("Capability must be approved before Marketplace publishing")
    if str(package.get("license_policy") or "") == "block":
        raise ValueError("Blocked-license capabilities cannot be published")
    if str(package.get("risk_level") or "") == "blocked":
        raise ValueError("Blocked capabilities cannot be published")
    security_scan = package.get("security_scan") if isinstance(package.get("security_scan"), dict) else {}
    if bool(security_scan.get("blocked")):
        raise ValueError("Capability security scan blocks publishing")

    resources = list_package_resources(client, org_id, package_id)
    display_title = (title or package.get("name") or "Portable capability").strip()
    display_description = (
        description
        or package.get("description")
        or "Portable Agent Skill / plugin capability for Gravitre."
    )
    # Use the existing structurally valid Marketplace knowledge-pack envelope
    # while category + immutable bridge snapshot identify the portable asset.
    created = create_org_asset(
        client,
        org_id,
        actor_id=actor_id,
        slug=slug,
        title=display_title,
        description=display_description,
        asset_type="knowledge_pack",
        category="capability_pack",
        tags=["portable-capability", str(package.get("package_format") or "plugin")],
        config={
            "documents": [
                {
                    "title": display_title,
                    "type": "portable_capability",
                    "metadata": {
                        "packageFormat": package.get("package_format"),
                        "packageVersion": package.get("version"),
                        "contentDigest": package.get("content_digest"),
                    },
                }
            ]
        },
        required_permissions=list(
            (package.get("inspection") or {}).get("permissions") or []
        )
        if isinstance(package.get("inspection"), dict)
        else [],
        pricing_type=pricing_type,
        price_cents=price_cents,
    )
    asset = created["asset"]
    client.table("marketplace_capability_assets").insert(
        {
            "asset_id": asset["id"],
            "source_org_id": org_id,
            "source_package_id": package_id,
            "package_name": package.get("name"),
            "package_format": package.get("package_format"),
            "package_version": package.get("version"),
            "content_digest": package.get("content_digest"),
            "manifest": package.get("manifest") or {},
            "inspection": package.get("inspection") or {},
            "security_scan": security_scan,
            "resources": [
                {
                    "path": row.get("path"),
                    "kind": row.get("kind"),
                    "content": row.get("content"),
                    "executable": bool(row.get("executable")),
                }
                for row in resources
            ],
            "created_by": actor_id or None,
        }
    ).execute()
    return {**created, "capabilityPackageId": package_id, "portableCapability": True}


def get_marketplace_capability_snapshot(client: Any, asset_id: str) -> dict[str, Any] | None:
    rows = (
        client.table("marketplace_capability_assets")
        .select("*")
        .eq("asset_id", asset_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    return dict(rows[0]) if rows else None


def install_marketplace_capability_snapshot(
    client: Any,
    *,
    org_id: str,
    actor_id: str,
    asset: dict[str, Any],
) -> dict[str, Any] | None:
    snapshot = get_marketplace_capability_snapshot(client, str(asset.get("id") or ""))
    if not snapshot:
        return None
    security_scan = snapshot.get("security_scan") if isinstance(snapshot.get("security_scan"), dict) else {}
    if bool(security_scan.get("blocked")):
        raise ValueError("Marketplace capability snapshot is blocked by security policy")

    pseudo_package = {
        "name": snapshot.get("package_name"),
        "package_format": snapshot.get("package_format"),
        "version": snapshot.get("package_version"),
        "description": asset.get("description"),
        "license": (snapshot.get("inspection") or {}).get("license")
        if isinstance(snapshot.get("inspection"), dict)
        else None,
        "license_policy": (snapshot.get("inspection") or {}).get("license_policy")
        if isinstance(snapshot.get("inspection"), dict)
        else "review",
        "risk_level": (snapshot.get("inspection") or {}).get("risk")
        if isinstance(snapshot.get("inspection"), dict)
        else "moderate",
        "inspection": snapshot.get("inspection") or {},
    }
    inspection = _inspection_from_package(pseudo_package)
    installed = install_package(
        client,
        org_id=org_id,
        user_id=actor_id,
        inspection=inspection,
        manifest=snapshot.get("manifest") or {},
        source_type="marketplace",
        source_uri=f"marketplace:{asset.get('id')}",
        publisher_name=None,
        publisher_trusted=False,
        publisher_trust_scope="none",
        publisher_verified=bool(asset.get("verified")),
        marketplace_publisher_id=str(asset.get("publisher_id") or "") or None,
        signature_status="unsigned",
        content_digest=str(snapshot.get("content_digest") or "") or None,
        # Marketplace install is distribution, not org approval.
        initial_status="quarantined",
        security_scan=security_scan,
    )
    package_id = str(installed.get("id") or "")
    resources = snapshot.get("resources") if isinstance(snapshot.get("resources"), list) else []
    if package_id:
        replace_package_resources(
            client,
            package_id=package_id,
            org_id=org_id,
            resources=[row for row in resources if isinstance(row, dict)],
        )
        record_package_version(
            client,
            org_id=org_id,
            package=installed,
            resources=[row for row in resources if isinstance(row, dict)],
            user_id=actor_id,
        )
    return {
        "entityType": "capability_package",
        "entityId": package_id,
        "packageId": package_id,
        "status": "quarantined",
        "requiresReview": True,
    }
