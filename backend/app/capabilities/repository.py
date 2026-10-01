"""Persistence for portable capability packages."""
from __future__ import annotations

from typing import Any

from app.capabilities.packages import PackageInspection


_RISK_RANK = {"low": 0, "moderate": 1, "high": 2, "blocked": 3}


def _effective_risk(inspection_risk: str, security_scan: dict[str, Any] | None) -> str:
    scan_risk = str((security_scan or {}).get("risk") or "low")
    return max(
        (inspection_risk or "low", scan_risk),
        key=lambda value: _RISK_RANK.get(value, 1),
    )


def list_packages(client: Any, org_id: str) -> list[dict[str, Any]]:
    try:
        response = (
            client.table("capability_packages")
            .select(
                "id,org_id,name,package_format,version,description,license,license_policy,"
                "risk_level,source_type,source_uri,source_commit_sha,source_package_path,marketplace_source_id,publisher_name,"
                "publisher_verified,signature_status,content_digest,inspection,security_scan,status,"
                "installed_by,installed_at,updated_at,reviewed_by,reviewed_at,review_notes"
            )
            .eq("org_id", org_id)
            .neq("status", "removed")
            .order("installed_at", desc=True)
            .execute()
        )
        return list(response.data or [])
    except Exception:
        # Read path remains backward-compatible during rolling deploys before
        # the new migration reaches every environment.
        return []


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
    security_scan: dict[str, Any] | None = None,
    source_commit_sha: str | None = None,
    source_package_path: str | None = None,
) -> dict[str, Any]:
    effective_risk = _effective_risk(inspection.risk, security_scan)
    row = {
        "org_id": org_id,
        "name": inspection.name,
        "package_format": inspection.format,
        "version": inspection.version or "0.0.0",
        "description": inspection.description,
        "license": inspection.license,
        "license_policy": inspection.license_policy,
        "risk_level": effective_risk,
        "source_type": source_type,
        "source_uri": source_uri,
        "source_commit_sha": source_commit_sha,
        "source_package_path": source_package_path,
        "marketplace_source_id": marketplace_source_id,
        "publisher_name": publisher_name,
        "publisher_verified": publisher_verified,
        "signature_status": signature_status,
        "content_digest": content_digest,
        "manifest": manifest,
        "inspection": inspection.as_dict(),
        "security_scan": security_scan or {},
        "status": initial_status or ("quarantined" if effective_risk == "high" else "installed"),
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
    try:
        response = (
            client.table("capability_marketplace_sources")
            .select("id,name,source_type,repository_url,branch,root_path,auto_sync,approval_required,status,last_synced_at,last_sync_status,last_sync_error,created_by,created_at,updated_at")
            .eq("org_id", org_id)
            .neq("status", "removed")
            .order("created_at", desc=True)
            .execute()
        )
        return list(response.data or [])
    except Exception:
        return []


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


def upsert_marketplace_candidate(
    client: Any,
    *,
    org_id: str,
    source_id: str,
    package_path: str,
    manifest: dict[str, Any],
    inspection: dict[str, Any],
    content_digest: str,
    files: dict[str, str],
    security_scan: dict[str, Any] | None = None,
    source_commit_sha: str | None = None,
    source_package_path: str | None = None,
) -> dict[str, Any]:
    effective_risk = _effective_risk(str(inspection.get("risk") or "moderate"), security_scan)
    row = {
        "org_id": org_id,
        "marketplace_source_id": source_id,
        "package_path": package_path,
        "name": str(inspection.get("name") or "unnamed-capability"),
        "package_format": str(inspection.get("format") or "unknown"),
        "version": inspection.get("version"),
        "description": inspection.get("description"),
        "license": inspection.get("license"),
        "license_policy": str(inspection.get("license_policy") or "review"),
        "risk_level": effective_risk,
        "content_digest": content_digest,
        "manifest": manifest,
        "inspection": inspection,
        "security_scan": security_scan or {},
        "files": files,
        "source_commit_sha": source_commit_sha,
        "source_package_path": source_package_path or package_path,
        "status": "pending_review",
    }
    response = client.table("capability_marketplace_candidates").upsert(
        row,
        on_conflict="marketplace_source_id,package_path,content_digest",
    ).execute()
    rows = list(response.data or [])
    return rows[0] if rows else row


def list_marketplace_candidates(
    client: Any,
    org_id: str,
    *,
    source_id: str | None = None,
    status: str | None = None,
) -> list[dict[str, Any]]:
    query = client.table("capability_marketplace_candidates").select("*").eq("org_id", org_id)
    if source_id:
        query = query.eq("marketplace_source_id", source_id)
    if status:
        query = query.eq("status", status)
    response = query.order("discovered_at", desc=True).execute()
    return list(response.data or [])


def get_marketplace_candidate(client: Any, org_id: str, candidate_id: str) -> dict[str, Any] | None:
    response = (
        client.table("capability_marketplace_candidates")
        .select("*")
        .eq("org_id", org_id)
        .eq("id", candidate_id)
        .limit(1)
        .execute()
    )
    rows = list(response.data or [])
    return rows[0] if rows else None


def review_marketplace_candidate(
    client: Any,
    *,
    org_id: str,
    candidate_id: str,
    user_id: str,
    decision: str,
    notes: str | None = None,
) -> dict[str, Any] | None:
    from datetime import datetime, timezone

    status = "approved" if decision == "approve" else "rejected"
    response = (
        client.table("capability_marketplace_candidates")
        .update(
            {
                "status": status,
                "reviewed_at": datetime.now(timezone.utc).isoformat(),
                "reviewed_by": user_id or None,
                "review_notes": notes,
            }
        )
        .eq("org_id", org_id)
        .eq("id", candidate_id)
        .execute()
    )
    rows = list(response.data or [])
    return rows[0] if rows else None


_PACKAGE_SNAPSHOT_FIELDS = (
    "name",
    "package_format",
    "version",
    "description",
    "license",
    "license_policy",
    "risk_level",
    "source_type",
    "source_uri",
    "marketplace_source_id",
    "publisher_name",
    "publisher_verified",
    "signature_status",
    "content_digest",
    "manifest",
    "inspection",
    "security_scan",
    "status",
)


def record_package_version(
    client: Any,
    *,
    org_id: str,
    package: dict[str, Any],
    resources: list[dict[str, Any]],
    user_id: str,
) -> dict[str, Any] | None:
    package_id = str(package.get("id") or "")
    if not package_id:
        return None
    snapshot = {
        key: package.get(key)
        for key in _PACKAGE_SNAPSHOT_FIELDS
    }
    digest = str(package.get("content_digest") or "").strip() or None
    row = {
        "package_id": package_id,
        "org_id": org_id,
        "content_digest": digest,
        "package_version": package.get("version"),
        "snapshot": snapshot,
        "resources": [
            {
                "path": resource.get("path"),
                "kind": resource.get("kind"),
                "content": resource.get("content"),
                "executable": bool(resource.get("executable")),
            }
            for resource in resources
        ],
        "recorded_by": user_id or None,
    }
    if digest:
        response = client.table("capability_package_versions").upsert(
            row,
            on_conflict="package_id,content_digest",
        ).execute()
    else:
        response = client.table("capability_package_versions").insert(row).execute()
    rows = list(response.data or [])
    return rows[0] if rows else row


def list_package_versions(
    client: Any,
    *,
    org_id: str,
    package_id: str,
) -> list[dict[str, Any]]:
    response = (
        client.table("capability_package_versions")
        .select("id,package_id,content_digest,package_version,snapshot,recorded_by,recorded_at")
        .eq("org_id", org_id)
        .eq("package_id", package_id)
        .order("recorded_at", desc=True)
        .execute()
    )
    return list(response.data or [])


def get_package_version(
    client: Any,
    *,
    org_id: str,
    package_id: str,
    version_id: str,
) -> dict[str, Any] | None:
    response = (
        client.table("capability_package_versions")
        .select("*")
        .eq("org_id", org_id)
        .eq("package_id", package_id)
        .eq("id", version_id)
        .limit(1)
        .execute()
    )
    rows = list(response.data or [])
    return rows[0] if rows else None


def rollback_status_for_snapshot(snapshot: dict[str, Any]) -> str:
    if str(snapshot.get("license_policy") or "") == "block":
        return "quarantined"
    if str(snapshot.get("risk_level") or "") in {"high", "blocked"}:
        return "quarantined"
    return "installed"


def restore_package_version(
    client: Any,
    *,
    org_id: str,
    package_id: str,
    version_row: dict[str, Any],
    user_id: str,
) -> dict[str, Any] | None:
    snapshot = version_row.get("snapshot") if isinstance(version_row.get("snapshot"), dict) else {}
    patch = {
        key: snapshot.get(key)
        for key in _PACKAGE_SNAPSHOT_FIELDS
        if key in snapshot and key != "status"
    }
    patch["status"] = rollback_status_for_snapshot(snapshot)
    patch["installed_by"] = user_id or None
    response = (
        client.table("capability_packages")
        .update(patch)
        .eq("org_id", org_id)
        .eq("id", package_id)
        .execute()
    )
    rows = list(response.data or [])
    if not rows:
        return None
    resources = version_row.get("resources") if isinstance(version_row.get("resources"), list) else []
    replace_package_resources(
        client,
        package_id=package_id,
        org_id=org_id,
        resources=[row for row in resources if isinstance(row, dict)],
    )
    return rows[0]
