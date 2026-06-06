"""Org-scoped private connector bundles — upload, verify, activate (STA-98)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status

from app.connectors.private.signature import BundleSignatureError, verify_bundle_signature
from app.connectors.sdk.manifest import parse_manifest
from app.core.errors import error_detail
from app.services.partner_marketplace_service import validate_manifest_payload
from app.services.partner_security_review_service import run_certification_review

RESOURCE_TYPE_PRIVATE_BUNDLE = "private_connector_bundle"
AUDIT_PRIVATE_BUNDLE_UPLOADED = "marketplace.private_bundle.uploaded"
AUDIT_PRIVATE_BUNDLE_ACTIVATED = "marketplace.private_bundle.activated"
AUDIT_PRIVATE_BUNDLE_DISABLED = "marketplace.private_bundle.disabled"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_bundle(row: dict[str, Any]) -> dict[str, Any]:
    manifest = row.get("manifest") or {}
    auth = manifest.get("auth") or {}
    auth_type = auth.get("type") or "apiKey"
    return {
        "id": str(row["id"]),
        "orgId": str(row["org_id"]),
        "createdBy": str(row["created_by"]),
        "name": row.get("name"),
        "packageId": row.get("package_id"),
        "vendor": row.get("vendor"),
        "version": row.get("version"),
        "manifest": manifest,
        "packageSourceFiles": sorted((row.get("package_sources") or {}).keys()),
        "signingPublicKeyPem": row.get("signing_public_key_pem"),
        "signatureAlgorithm": row.get("signature_algorithm") or "ed25519",
        "securityScan": row.get("security_scan") or {},
        "scopeReview": row.get("scope_review") or {},
        "certificationStatus": row.get("certification_status") or "pending",
        "status": row.get("status"),
        "activatedAt": row.get("activated_at"),
        "activatedBy": str(row["activated_by"]) if row.get("activated_by") else None,
        "createdAt": row.get("created_at"),
        "updatedAt": row.get("updated_at"),
        "authType": "oauth" if auth_type == "oauth2" else "apiKey",
        "capabilities": manifest.get("capabilities") or [],
        "runtime": "sandbox",
    }


def get_active_bundle_for_vendor(client: Any, org_id: str, vendor: str) -> dict[str, Any] | None:
    """Return the active private bundle for an org/vendor, if any."""
    slug = (vendor or "").strip().lower()
    if not slug:
        return None
    result = (
        client.table("org_private_connector_bundles")
        .select("*")
        .eq("org_id", org_id)
        .eq("vendor", slug)
        .eq("status", "active")
        .limit(1)
        .execute()
    )
    if not result.data:
        return None
    return result.data[0]


def list_private_bundles(client: Any, *, org_id: str) -> list[dict[str, Any]]:
    result = (
        client.table("org_private_connector_bundles")
        .select("*")
        .eq("org_id", org_id)
        .order("created_at", desc=True)
        .execute()
    )
    return [_normalize_bundle(row) for row in (result.data or [])]


def get_private_bundle(client: Any, *, org_id: str, bundle_id: str) -> dict[str, Any]:
    result = (
        client.table("org_private_connector_bundles")
        .select("*")
        .eq("id", bundle_id)
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Private bundle not found")
    return _normalize_bundle(result.data[0])


def upload_private_bundle(
    client: Any,
    *,
    org_id: str,
    created_by: str,
    name: str,
    manifest: dict[str, Any],
    package_sources: dict[str, str],
    signing_public_key_pem: str,
    signature: str,
) -> dict[str, Any]:
    """Upload and verify a signed private connector bundle (draft)."""
    parsed = validate_manifest_payload(manifest)
    sources = {k: v for k, v in (package_sources or {}).items() if isinstance(v, str) and v.strip()}
    if "handlers.py" not in sources:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_detail("packageSources must include handlers.py", "MISSING_HANDLERS"),
        )

    try:
        verify_bundle_signature(
            manifest=parsed.model_dump(by_alias=True),
            package_sources=sources,
            signing_public_key_pem=signing_public_key_pem,
            signature_b64=signature,
        )
    except BundleSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_detail(str(exc), "INVALID_BUNDLE_SIGNATURE"),
        ) from exc

    certification = run_certification_review(parsed, package_sources=sources)
    if not certification.security_scan.passed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_detail(
                "Security scan failed — fix critical findings before uploading",
                "SECURITY_SCAN_FAILED",
            ),
        )

    cert_dict = certification.to_dict()
    display_name = (name or parsed.name).strip() or parsed.name
    row = {
        "org_id": org_id,
        "created_by": created_by,
        "name": display_name,
        "package_id": parsed.id,
        "vendor": parsed.vendor,
        "version": parsed.version,
        "manifest": parsed.model_dump(by_alias=True),
        "package_sources": sources,
        "signing_public_key_pem": signing_public_key_pem.strip(),
        "signature": signature.strip(),
        "signature_algorithm": "ed25519",
        "security_scan": cert_dict["securityScan"],
        "scope_review": cert_dict["scopeReview"],
        "certification_status": certification.certification_status,
        "status": "draft",
        "updated_at": _now_iso(),
    }

    existing = (
        client.table("org_private_connector_bundles")
        .select("id, status")
        .eq("org_id", org_id)
        .eq("vendor", parsed.vendor)
        .limit(1)
        .execute()
    )
    if existing.data:
        bundle_id = existing.data[0]["id"]
        updated = (
            client.table("org_private_connector_bundles")
            .update(row)
            .eq("id", bundle_id)
            .execute()
        )
        if not updated.data:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Bundle update failed")
        return _normalize_bundle(updated.data[0])

    created = client.table("org_private_connector_bundles").insert(row).execute()
    if not created.data:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Bundle create failed")
    return _normalize_bundle(created.data[0])


def activate_private_bundle(
    client: Any,
    *,
    org_id: str,
    bundle_id: str,
    actor_id: str,
) -> dict[str, Any]:
    """Activate a draft bundle for invoke_tool sandbox execution."""
    result = (
        client.table("org_private_connector_bundles")
        .select("*")
        .eq("id", bundle_id)
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Private bundle not found")
    row = result.data[0]
    if row.get("status") == "active":
        return _normalize_bundle(row)

    parsed = parse_manifest(row.get("manifest") or {})
    sources = row.get("package_sources") or {}
    try:
        verify_bundle_signature(
            manifest=row.get("manifest") or {},
            package_sources=sources,
            signing_public_key_pem=row.get("signing_public_key_pem") or "",
            signature_b64=row.get("signature") or "",
        )
    except BundleSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_detail(str(exc), "INVALID_BUNDLE_SIGNATURE"),
        ) from exc

    certification = run_certification_review(parsed, package_sources=sources)
    if not certification.security_scan.passed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_detail("Security scan must pass before activation", "SECURITY_SCAN_FAILED"),
        )

    activated_at = _now_iso()
    updated = (
        client.table("org_private_connector_bundles")
        .update(
            {
                "status": "active",
                "activated_at": activated_at,
                "activated_by": actor_id,
                "certification_status": certification.certification_status,
                "security_scan": certification.to_dict()["securityScan"],
                "scope_review": certification.to_dict()["scopeReview"],
                "updated_at": activated_at,
            }
        )
        .eq("id", bundle_id)
        .execute()
    )
    if not updated.data:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Activation failed")

    _register_private_scopes(parsed)
    return _normalize_bundle(updated.data[0])


def disable_private_bundle(client: Any, *, org_id: str, bundle_id: str) -> dict[str, Any]:
    result = (
        client.table("org_private_connector_bundles")
        .select("*")
        .eq("id", bundle_id)
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Private bundle not found")

    updated = (
        client.table("org_private_connector_bundles")
        .update({"status": "disabled", "updated_at": _now_iso()})
        .eq("id", bundle_id)
        .execute()
    )
    if not updated.data:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Disable failed")
    return _normalize_bundle(updated.data[0])


def ensure_private_scopes_registered(manifest: Any) -> None:
    """Register action scopes for agent permission checks (idempotent)."""
    from app.services.agent_tool_permissions import ACTION_REQUIRED_SCOPES

    for action_key in manifest.action_keys():
        ACTION_REQUIRED_SCOPES[action_key] = manifest.scopes_for_action(action_key)


def _register_private_scopes(manifest: Any) -> None:
    ensure_private_scopes_registered(manifest)
