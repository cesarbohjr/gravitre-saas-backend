"""Partner connector marketplace — submissions, review, registry (STA-71)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status

from app.connectors.sdk.manifest import ConnectorManifest, parse_manifest
from app.core.errors import error_detail
from app.services.partner_security_review_service import (
    build_registry_scan_summary,
    run_certification_review,
)

RESOURCE_TYPE_PARTNER_SUBMISSION = "partner_connector_submission"
RESOURCE_TYPE_PARTNER_REGISTRY = "partner_connector_registry"

AUDIT_SUBMISSION_CREATED = "marketplace.submission.created"
AUDIT_SUBMISSION_REVIEWED = "marketplace.submission.reviewed"
AUDIT_CONNECTOR_PUBLISHED = "marketplace.connector.published"
AUDIT_CERTIFICATION_SCANNED = "marketplace.certification.scanned"

CERTIFICATION_BADGE = "gravitre_certified"

SECURITY_CHECKLIST_KEYS = (
    "no_hardcoded_secrets",
    "oauth_redirects_documented",
    "scopes_minimized",
    "data_residency_documented",
    "audit_logging_compatible",
    "error_handling_documented",
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_security_checklist(checklist: dict[str, Any]) -> dict[str, bool]:
    """Require all security checklist items to be explicitly true."""
    normalized: dict[str, bool] = {}
    for key in SECURITY_CHECKLIST_KEYS:
        normalized[key] = bool(checklist.get(key))
    if not all(normalized.values()):
        missing = [key for key, ok in normalized.items() if not ok]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_detail(
                f"Complete the security checklist before submitting: {', '.join(missing)}",
                "SECURITY_CHECKLIST_INCOMPLETE",
            ),
        )
    return normalized


def validate_manifest_payload(manifest: dict[str, Any]) -> ConnectorManifest:
    """Parse and validate connector manifest.json content."""
    try:
        return parse_manifest(manifest)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_detail(f"Invalid manifest: {exc}", "INVALID_MANIFEST"),
        ) from exc


def _package_source_files(row: dict[str, Any]) -> list[str]:
    sources = row.get("package_sources") or {}
    if not isinstance(sources, dict):
        return []
    return sorted(str(name) for name in sources.keys())


def _normalize_submission(row: dict[str, Any], *, include_sources: bool = False) -> dict[str, Any]:
    payload = {
        "id": str(row["id"]),
        "orgId": str(row["org_id"]),
        "submittedBy": str(row["submitted_by"]),
        "packageId": row.get("package_id"),
        "vendor": row.get("vendor"),
        "name": row.get("name"),
        "version": row.get("version"),
        "manifest": row.get("manifest") or {},
        "securityChecklist": row.get("security_checklist") or {},
        "packageSourceFiles": _package_source_files(row),
        "securityScan": row.get("security_scan") or {},
        "scopeReview": row.get("scope_review") or {},
        "certificationStatus": row.get("certification_status") or "pending",
        "status": row.get("status"),
        "reviewerId": str(row["reviewer_id"]) if row.get("reviewer_id") else None,
        "reviewNotes": row.get("review_notes"),
        "reviewedAt": row.get("reviewed_at"),
        "createdAt": row.get("created_at"),
        "updatedAt": row.get("updated_at"),
    }
    if include_sources:
        payload["packageSources"] = row.get("package_sources") or {}
    return payload


def _normalize_registry(row: dict[str, Any]) -> dict[str, Any]:
    manifest = row.get("manifest") or {}
    auth = manifest.get("auth") or {}
    auth_type = auth.get("type") or "apiKey"
    return {
        "id": str(row["id"]),
        "submissionId": str(row["submission_id"]),
        "orgId": str(row["org_id"]),
        "packageId": row.get("package_id"),
        "vendor": row.get("vendor"),
        "name": row.get("name"),
        "version": row.get("version"),
        "manifest": manifest,
        "authType": "oauth" if auth_type == "oauth2" else "apiKey",
        "description": manifest.get("description") or "",
        "capabilities": manifest.get("capabilities") or [],
        "publishedBy": str(row["published_by"]),
        "publishedAt": row.get("published_at"),
        "status": row.get("status"),
        "certificationBadge": row.get("certification_badge"),
        "certifiedAt": row.get("certified_at"),
        "securityScanSummary": row.get("security_scan_summary") or {},
    }


def is_published_partner_vendor(client: Any, vendor: str) -> bool:
    """Return True when vendor is in the published partner registry."""
    slug = (vendor or "").strip().lower()
    if not slug:
        return False
    row = (
        client.table("partner_connector_registry")
        .select("id")
        .eq("vendor", slug)
        .eq("status", "published")
        .limit(1)
        .execute()
    )
    return bool(row.data)


def create_submission(
    client: Any,
    *,
    org_id: str,
    submitted_by: str,
    manifest: dict[str, Any],
    security_checklist: dict[str, Any],
    package_sources: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Create a pending partner connector submission."""
    parsed = validate_manifest_payload(manifest)
    checklist = validate_security_checklist(security_checklist)
    certification = run_certification_review(parsed, package_sources=package_sources)

    conflict = (
        client.table("partner_connector_submissions")
        .select("id")
        .eq("vendor", parsed.vendor)
        .in_("status", ["pending", "in_review"])
        .limit(1)
        .execute()
    )
    if conflict.data:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=error_detail(
                f"A submission for vendor {parsed.vendor!r} is already pending review",
                "SUBMISSION_PENDING",
            ),
        )

    published = (
        client.table("partner_connector_registry")
        .select("id")
        .eq("vendor", parsed.vendor)
        .eq("status", "published")
        .limit(1)
        .execute()
    )
    if published.data:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=error_detail(
                f"Vendor {parsed.vendor!r} is already published in the marketplace",
                "VENDOR_ALREADY_PUBLISHED",
            ),
        )

    cert_dict = certification.to_dict()
    row = {
        "org_id": org_id,
        "submitted_by": submitted_by,
        "package_id": parsed.id,
        "vendor": parsed.vendor,
        "name": parsed.name,
        "version": parsed.version,
        "manifest": parsed.model_dump(by_alias=True),
        "security_checklist": checklist,
        "package_sources": package_sources or {},
        "security_scan": cert_dict["securityScan"],
        "scope_review": cert_dict["scopeReview"],
        "certification_status": certification.certification_status,
        "status": "pending",
        "updated_at": _now_iso(),
    }
    created = client.table("partner_connector_submissions").insert(row).execute()
    if not created.data:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Submission create failed")
    return _normalize_submission(created.data[0])


def list_submissions(
    client: Any,
    *,
    org_id: str,
    admin: bool,
    status_filter: str | None = None,
) -> list[dict[str, Any]]:
    """List submissions. Admins see all orgs; members see their org only."""
    query = client.table("partner_connector_submissions").select("*").order("created_at", desc=True)
    if not admin:
        query = query.eq("org_id", org_id)
    if status_filter:
        query = query.eq("status", status_filter)
    result = query.execute()
    return [_normalize_submission(row) for row in (result.data or [])]


def get_submission(
    client: Any,
    submission_id: str,
    *,
    org_id: str,
    admin: bool,
    include_sources: bool = False,
) -> dict[str, Any]:
    """Fetch a single submission with org scoping."""
    query = (
        client.table("partner_connector_submissions")
        .select("*")
        .eq("id", submission_id)
        .limit(1)
    )
    if not admin:
        query = query.eq("org_id", org_id)
    result = query.execute()
    if not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found")
    return _normalize_submission(result.data[0], include_sources=include_sources or admin)


def review_submission(
    client: Any,
    *,
    submission_id: str,
    reviewer_id: str,
    org_id: str,
    decision: str,
    notes: str | None,
) -> dict[str, Any]:
    """Approve or reject a pending submission (platform admin)."""
    if decision not in {"approve", "reject"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="decision must be approve or reject")

    existing = (
        client.table("partner_connector_submissions")
        .select("*")
        .eq("id", submission_id)
        .limit(1)
        .execute()
    )
    if not existing.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found")
    row = existing.data[0]
    if row.get("status") not in {"pending", "in_review"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=error_detail("Submission is not open for review", "SUBMISSION_NOT_REVIEWABLE"),
        )

    reviewed_at = _now_iso()
    new_status = "approved" if decision == "approve" else "rejected"
    updated = (
        client.table("partner_connector_submissions")
        .update(
            {
                "status": new_status,
                "reviewer_id": reviewer_id,
                "review_notes": (notes or "").strip() or None,
                "reviewed_at": reviewed_at,
                "updated_at": reviewed_at,
            }
        )
        .eq("id", submission_id)
        .execute()
    )
    if not updated.data:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Review update failed")
    submission = _normalize_submission(updated.data[0])

    registry_entry: dict[str, Any] | None = None
    if decision == "approve":
        manifest = row.get("manifest") or {}
        parsed = validate_manifest_payload(manifest)
        certification = run_certification_review(
            parsed,
            package_sources=row.get("package_sources") or {},
        )
        badge: str | None = CERTIFICATION_BADGE if certification.badge_eligible else None
        registry_row = {
            "submission_id": submission_id,
            "org_id": row["org_id"],
            "package_id": parsed.id,
            "vendor": parsed.vendor,
            "name": parsed.name,
            "version": parsed.version,
            "manifest": parsed.model_dump(by_alias=True),
            "published_by": reviewer_id,
            "published_at": reviewed_at,
            "status": "published",
            "certification_badge": badge,
            "certified_at": reviewed_at if badge else None,
            "security_scan_summary": build_registry_scan_summary(certification),
            "updated_at": reviewed_at,
        }
        created = client.table("partner_connector_registry").insert(registry_row).execute()
        if not created.data:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Registry publish failed")
        registry_entry = _normalize_registry(created.data[0])
        from app.marketplace.convergence import upsert_connector_asset_from_registry

        try:
            upsert_connector_asset_from_registry(client, created.data[0])
        except Exception:
            pass  # registry publish succeeds even if unified asset sync fails

    return {"submission": submission, "registry": registry_entry}


def rescan_submission_certification(client: Any, submission_id: str) -> dict[str, Any]:
    """Re-run automated certification on a pending submission (admin)."""
    existing = (
        client.table("partner_connector_submissions")
        .select("*")
        .eq("id", submission_id)
        .limit(1)
        .execute()
    )
    if not existing.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found")
    row = existing.data[0]
    if row.get("status") not in {"pending", "in_review"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=error_detail("Only open submissions can be rescanned", "SUBMISSION_NOT_SCANNABLE"),
        )

    parsed = validate_manifest_payload(row.get("manifest") or {})
    certification = run_certification_review(
        parsed,
        package_sources=row.get("package_sources") or {},
    )
    cert_dict = certification.to_dict()
    updated = (
        client.table("partner_connector_submissions")
        .update(
            {
                "security_scan": cert_dict["securityScan"],
                "scope_review": cert_dict["scopeReview"],
                "certification_status": certification.certification_status,
                "updated_at": _now_iso(),
            }
        )
        .eq("id", submission_id)
        .execute()
    )
    if not updated.data:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Rescan update failed")
    return _normalize_submission(updated.data[0])


def list_registry(client: Any, *, status: str = "published") -> list[dict[str, Any]]:
    """List published partner connectors available in the marketplace."""
    result = (
        client.table("partner_connector_registry")
        .select("*")
        .eq("status", status)
        .order("published_at", desc=True)
        .execute()
    )
    return [_normalize_registry(row) for row in (result.data or [])]
