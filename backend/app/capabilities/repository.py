"""Persistence for portable capability packages."""
from __future__ import annotations

from typing import Any

from app.capabilities.packages import PackageInspection


def list_packages(client: Any, org_id: str) -> list[dict[str, Any]]:
    response = (
        client.table("capability_packages")
        .select("id,org_id,name,package_format,version,description,license,license_policy,risk_level,source_type,source_uri,inspection,status,installed_by,installed_at,updated_at")
        .eq("org_id", org_id)
        .neq("status", "removed")
        .order("installed_at", desc=True)
        .execute()
    )
    return list(response.data or [])


def install_package(
    client: Any,
    *,
    org_id: str,
    user_id: str,
    inspection: PackageInspection,
    manifest: dict[str, Any],
    source_type: str = "manual",
    source_uri: str | None = None,
    marketplace_source_id: str | None = None,
    publisher_name: str | None = None,
    publisher_verified: bool = False,
    signature_status: str = "unsigned",
    content_digest: str | None = None,
    initial_status: str | None = None,
) -> dict[str, Any]:
    row = {
        "org_id": org_id,
        "name": inspection.name,
        "package_format": inspection.format,
        "version": inspection.version,
        "description": inspection.description,
        "license": inspection.license,
        "license_policy": inspection.license_policy,
        "risk_level": inspection.risk,
        "source_type": source_type,
        "source_uri": source_uri,
        "marketplace_source_id": marketplace_source_id,
        "publisher_name": publisher_name,
        "publisher_verified": publisher_verified,
        "signature_status": signature_status,
        "content_digest": content_digest,
        "manifest": manifest,
        "inspection": inspection.as_dict(),
        "status": initial_status or ("quarantined" if inspection.risk == "high" else "installed"),
        "installed_by": user_id,
    }
    response = client.table("capability_packages").upsert(
        row,
        on_conflict="org_id,name,version",
    ).execute()
    data = list(response.data or [])
    return data[0] if data else row


def replace_package_resources(
    client: Any,
    *,
    package_id: str,
    org_id: str,
    resources: list[dict[str, Any]],
) -> None:
    client.table("capability_package_resources").delete().eq("package_id", package_id).eq("org_id", org_id).execute()
    rows = [
        {
            "package_id": package_id,
            "org_id": org_id,
            "path": str(row.get("path") or ""),
            "kind": str(row.get("kind") or "reference"),
            "content": row.get("content"),
            "executable": bool(row.get("executable")),
        }
        for row in resources
        if str(row.get("path") or "").strip()
    ]
    if rows:
        client.table("capability_package_resources").insert(rows).execute()


def list_package_resources(client: Any, org_id: str, package_id: str) -> list[dict[str, Any]]:
    response = (
        client.table("capability_package_resources")
        .select("id,package_id,path,kind,content,executable,created_at")
        .eq("org_id", org_id)
        .eq("package_id", package_id)
        .order("path")
        .execute()
    )
    return list(response.data or [])


def list_marketplace_sources(client: Any, org_id: str) -> list[dict[str, Any]]:
    response = (
        client.table("capability_marketplace_sources")
        .select("id,name,source_type,repository_url,branch,root_path,auto_sync,approval_required,status,last_synced_at,last_sync_status,last_sync_error,created_by,created_at,updated_at")
        .eq("org_id", org_id)
        .neq("status", "removed")
        .order("created_at", desc=True)
        .execute()
    )
    return list(response.data or [])


def create_marketplace_source(
    client: Any,
    *,
    org_id: str,
    user_id: str,
    name: str,
    repository_url: str,
    branch: str = "main",
    root_path: str = "",
    auto_sync: bool = False,
    approval_required: bool = True,
) -> dict[str, Any]:
    row = {
        "org_id": org_id,
        "name": name.strip(),
        "source_type": "github",
        "repository_url": repository_url,
        "branch": branch.strip() or "main",
        "root_path": root_path.strip().strip("/"),
        "auto_sync": bool(auto_sync),
        "approval_required": bool(approval_required),
        "status": "active",
        "created_by": user_id or None,
    }
    response = client.table("capability_marketplace_sources").insert(row).execute()
    data = list(response.data or [])
    return data[0] if data else row


def get_package(client: Any, org_id: str, package_id: str) -> dict[str, Any] | None:
    response = (
        client.table("capability_packages")
        .select("*")
        .eq("id", package_id)
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    )
    rows = list(response.data or [])
    return rows[0] if rows else None


def review_package(
    client: Any,
    *,
    org_id: str,
    package_id: str,
    reviewer_id: str,
    target_status: str,
    notes: str | None = None,
) -> dict[str, Any] | None:
    from datetime import datetime, timezone

    response = (
        client.table("capability_packages")
        .update(
            {
                "status": target_status,
                "reviewed_by": reviewer_id or None,
                "reviewed_at": datetime.now(timezone.utc).isoformat(),
                "review_notes": (notes or "").strip() or None,
            }
        )
        .eq("id", package_id)
        .eq("org_id", org_id)
        .execute()
    )
    rows = list(response.data or [])
    return rows[0] if rows else None


def get_marketplace_source(client: Any, org_id: str, source_id: str) -> dict[str, Any] | None:
    response = (
        client.table("capability_marketplace_sources")
        .select("*")
        .eq("id", source_id)
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    )
    rows = list(response.data or [])
    return rows[0] if rows else None


def update_marketplace_sync_status(
    client: Any,
    *,
    org_id: str,
    source_id: str,
    sync_status: str,
    error: str | None = None,
    synced: bool = False,
) -> None:
    from datetime import datetime, timezone

    patch = {
        "last_sync_status": sync_status,
        "last_sync_error": (error or "")[:2000] or None,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if synced:
        patch["last_synced_at"] = datetime.now(timezone.utc).isoformat()
    (
        client.table("capability_marketplace_sources")
        .update(patch)
        .eq("id", source_id)
        .eq("org_id", org_id)
        .execute()
    )
