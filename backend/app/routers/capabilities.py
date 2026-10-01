"""Tenant capability registry and portable package ingestion."""
from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from app.auth.dependencies import get_environment_context, require_admin, require_org_member
from app.capabilities.activation import build_activation_plan
from app.capabilities.importers import import_file_bundle, read_zip_bundle
from app.capabilities.packages import inspect_package, installation_allowed
from app.capabilities.provenance import bundle_digest, normalize_github_repository_url
from app.capabilities.publisher_trust import (
    is_trusted_publisher_key,
    list_trusted_publishers,
    trust_publisher_key,
)
from app.capabilities.registry import tenant_capability_snapshot
from app.capabilities.repository import (
    create_marketplace_source,
    get_marketplace_candidate,
    get_marketplace_source,
    get_package,
    get_package_version,
    install_package,
    list_marketplace_candidates,
    list_marketplace_sources,
    list_package_resources,
    list_package_versions,
    list_packages,
    record_package_version,
    replace_package_resources,
    restore_package_version,
    review_marketplace_candidate,
    review_package,
    update_marketplace_sync_status,
    upsert_marketplace_candidate,
)
from app.capabilities.review import review_transition_allowed
from app.capabilities.github_sync import sync_public_github_marketplace
from app.capabilities.mcp_activation import prepare_mcp_dependencies
from app.config import Settings, get_settings
from app.workflows.repository import get_supabase_client

router = APIRouter(prefix="/api/capabilities", tags=["capabilities"])


def _persist_resources_and_version(
    client: Any,
    *,
    org_id: str,
    package: dict[str, Any],
    resources: list[dict[str, Any]],
    user_id: str,
) -> None:
    package_id = str(package.get("id") or "")
    if not package_id:
        return
    replace_package_resources(
        client,
        package_id=package_id,
        org_id=org_id,
        resources=resources,
    )
    record_package_version(
        client,
        org_id=org_id,
        package=package,
        resources=resources,
        user_id=user_id,
    )



class PackageInspectRequest(BaseModel):
    manifest: dict[str, Any] = Field(default_factory=dict)
    skill_md: str | None = None


class PackageBundleRequest(BaseModel):
    files: dict[str, str]
    source_type: Literal["manual", "github", "zip", "mcp", "marketplace"] = Field(default="manual", alias="sourceType")
    source_uri: str | None = Field(default=None, alias="sourceUri")
    signing_public_key_pem: str | None = Field(default=None, alias="signingPublicKeyPem")
    signature: str | None = None

    model_config = {"populate_by_name": True}


class PackageReviewRequest(BaseModel):
    status: Literal["installed", "quarantined", "disabled"]
    notes: str | None = Field(default=None, max_length=2000)


class TrustedPublisherCreateRequest(BaseModel):
    publisher_name: str = Field(min_length=1, max_length=160, alias="publisherName")
    public_key_pem: str = Field(min_length=1, alias="publicKeyPem")

    model_config = {"populate_by_name": True}


class GitMarketplaceSourceCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    repository_url: str = Field(alias="repositoryUrl")
    branch: str = "main"
    root_path: str = Field(default="", alias="rootPath")
    auto_sync: bool = Field(default=False, alias="autoSync")
    approval_required: bool = Field(default=True, alias="approvalRequired")

    model_config = {"populate_by_name": True}


class PackageInstallRequest(PackageInspectRequest):
    source_type: Literal["manual", "github", "zip", "mcp", "marketplace"] = "manual"
    source_uri: str | None = None


@router.get("")
async def get_capabilities(
    member: Annotated[tuple[dict, str, str], Depends(require_org_member)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    _user, org_id, _role = member
    if not org_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = get_supabase_client(settings)
    snapshot = tenant_capability_snapshot(client, org_id, environment_name=environment_name)
    snapshot["portablePackages"] = list_packages(client, org_id)
    snapshot["portablePackagePolicy"] = {
        "executionOwner": "gravitre",
        "directImportedCodeExecution": False,
        "writeActions": "canonical approval + verified-write lifecycle",
        "supportedFormats": ["agent_skill", "openai_plugin", "claude_plugin", "gravitre", "mcp"],
    }
    return snapshot


@router.post("/packages/inspect")
async def inspect_portable_package(
    body: PackageInspectRequest,
    _member: Annotated[tuple[dict, str, str], Depends(require_org_member)],
) -> dict:
    """Inspect a package without installing or executing it."""
    inspection = inspect_package(body.manifest, skill_md=body.skill_md)
    return {"inspection": inspection.as_dict(), "installationAllowed": installation_allowed(inspection), "activationPlan": build_activation_plan(body.manifest, inspection.as_dict())}


@router.get("/packages")
async def get_portable_packages(
    member: Annotated[tuple[dict, str, str], Depends(require_org_member)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    _user, org_id, _role = member
    client = get_supabase_client(settings)
    return {"items": list_packages(client, org_id)}


@router.post("/packages/install")
async def install_portable_package(
    body: PackageInstallRequest,
    admin: Annotated[tuple[dict, str], Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """Install inert package metadata. High-risk packages are quarantined."""
    user, org_id = admin
    inspection = inspect_package(body.manifest, skill_md=body.skill_md)
    if not installation_allowed(inspection):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "Package blocked by capability policy", "inspection": inspection.as_dict()},
        )
    client = get_supabase_client(settings)
    installed = install_package(
        client,
        org_id=org_id,
        user_id=str(user.get("user_id") or ""),
        inspection=inspection,
        manifest=body.manifest,
        source_type=body.source_type,
        source_uri=body.source_uri,
    )
    record_package_version(
        client,
        org_id=org_id,
        package=installed,
        resources=[],
        user_id=str(user.get("user_id") or ""),
    )
    return {
        "package": installed,
        "inspection": inspection.as_dict(),
        "executionOwner": "gravitre",
        "directExecutionEnabled": False,
        "activationPlan": build_activation_plan(body.manifest, inspection.as_dict()),
    }


@router.post("/packages/inspect-bundle")
async def inspect_portable_bundle(
    body: PackageBundleRequest,
    _member: Annotated[tuple[dict, str, str], Depends(require_org_member)],
) -> dict:
    try:
        bundle = import_file_bundle(body.files)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    inspection = bundle.inspection
    return {
        "inspection": inspection.as_dict(),
        "installationAllowed": installation_allowed(inspection) and not bool(bundle.security_scan.get("blocked")),
        "securityScan": bundle.security_scan,
        "activationPlan": build_activation_plan(bundle.manifest, inspection.as_dict()),
        "resources": [
            {"path": row["path"], "kind": row["kind"], "executable": row["executable"]}
            for row in bundle.resources
        ],
        "ignoredFiles": list(bundle.ignored_files),
    }


@router.post("/packages/install-bundle")
async def install_portable_bundle(
    body: PackageBundleRequest,
    admin: Annotated[tuple[dict, str], Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    user, org_id = admin
    try:
        bundle = import_file_bundle(body.files)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    inspection = bundle.inspection
    if not installation_allowed(inspection) or bool(bundle.security_scan.get("blocked")):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "Package blocked by capability security policy",
                "inspection": inspection.as_dict(),
                "securityScan": bundle.security_scan,
            },
        )
    signature_status = "unsigned"
    publisher_verified = False
    if bool(body.signing_public_key_pem) != bool(body.signature):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="signingPublicKeyPem and signature must be provided together",
        )
    if body.signing_public_key_pem and body.signature:
        try:
            from app.connectors.private.signature import BundleSignatureError, verify_bundle_signature

            verify_bundle_signature(
                manifest=bundle.manifest,
                package_sources=body.files,
                signing_public_key_pem=body.signing_public_key_pem,
                signature_b64=body.signature,
            )
            # Signature validity proves integrity. Publisher identity is trusted
            # only when this org has explicitly pinned the same signing key.
            signature_status = "verified"
        except BundleSignatureError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid capability package signature: {exc}",
            ) from exc

    client = get_supabase_client(settings)
    publisher_name = str(
        bundle.manifest.get("publisher") or bundle.manifest.get("author") or ""
    ).strip() or None
    if signature_status == "verified" and body.signing_public_key_pem:
        publisher_verified = is_trusted_publisher_key(
            client,
            org_id=org_id,
            publisher_name=publisher_name,
            public_key_pem=body.signing_public_key_pem,
        )
    installed = install_package(
        client,
        org_id=org_id,
        user_id=str(user.get("user_id") or ""),
        inspection=inspection,
        manifest=bundle.manifest,
        source_type=body.source_type,
        source_uri=body.source_uri,
        publisher_name=publisher_name,
        signature_status=signature_status,
        publisher_verified=publisher_verified,
        content_digest=bundle_digest(body.files),
        security_scan=bundle.security_scan,
    )
    _persist_resources_and_version(
        client,
        org_id=org_id,
        package=installed,
        resources=list(bundle.resources),
        user_id=str(user.get("user_id") or ""),
    )
    return {
        "package": installed,
        "inspection": inspection.as_dict(),
        "activationPlan": build_activation_plan(bundle.manifest, inspection.as_dict()),
        "resourceCount": len(bundle.resources),
        "securityScan": bundle.security_scan,
        "directExecutionEnabled": False,
    }


@router.post("/packages/inspect-zip")
async def inspect_portable_zip(
    archive: Annotated[UploadFile, File(...)],
    _member: Annotated[tuple[dict, str, str], Depends(require_org_member)],
) -> dict:
    """Inspect a ZIP package without persisting or executing its contents."""
    payload = await archive.read()
    try:
        files = read_zip_bundle(payload)
        bundle = import_file_bundle(files)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    inspection = bundle.inspection
    return {
        "inspection": inspection.as_dict(),
        "installationAllowed": installation_allowed(inspection) and not bool(bundle.security_scan.get("blocked")),
        "securityScan": bundle.security_scan,
        "activationPlan": build_activation_plan(bundle.manifest, inspection.as_dict()),
        "resources": [
            {"path": row["path"], "kind": row["kind"], "executable": row["executable"]}
            for row in bundle.resources
        ],
        "ignoredFiles": list(bundle.ignored_files),
        "fileName": archive.filename,
    }


@router.post("/packages/install-zip")
async def install_portable_zip(
    archive: Annotated[UploadFile, File(...)],
    admin: Annotated[tuple[dict, str], Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
    source_uri: Annotated[str | None, Form(alias="sourceUri")] = None,
    signing_public_key_pem: Annotated[str | None, Form(alias="signingPublicKeyPem")] = None,
    signature: Annotated[str | None, Form()] = None,
) -> dict:
    """Install a ZIP through the same inert package policy as JSON bundles."""
    user, org_id = admin
    payload = await archive.read()
    try:
        files = read_zip_bundle(payload)
        bundle = import_file_bundle(files)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    inspection = bundle.inspection
    if not installation_allowed(inspection) or bool(bundle.security_scan.get("blocked")):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "Package blocked by capability security policy",
                "inspection": inspection.as_dict(),
                "securityScan": bundle.security_scan,
            },
        )

    signature_status = "unsigned"
    if bool(signing_public_key_pem) != bool(signature):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="signingPublicKeyPem and signature must be provided together",
        )
    if signing_public_key_pem and signature:
        try:
            from app.connectors.private.signature import (
                BundleSignatureError,
                verify_bundle_signature,
            )

            verify_bundle_signature(
                manifest=bundle.manifest,
                package_sources=files,
                signing_public_key_pem=signing_public_key_pem,
                signature_b64=signature,
            )
            signature_status = "verified"
        except BundleSignatureError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid capability package signature: {exc}",
            ) from exc

    client = get_supabase_client(settings)
    publisher_name = str(
        bundle.manifest.get("publisher") or bundle.manifest.get("author") or ""
    ).strip() or None
    publisher_verified = False
    if signature_status == "verified" and signing_public_key_pem:
        publisher_verified = is_trusted_publisher_key(
            client,
            org_id=org_id,
            publisher_name=publisher_name,
            public_key_pem=signing_public_key_pem,
        )
    installed = install_package(
        client,
        org_id=org_id,
        user_id=str(user.get("user_id") or ""),
        inspection=inspection,
        manifest=bundle.manifest,
        source_type="zip",
        source_uri=source_uri or archive.filename,
        publisher_name=publisher_name,
        signature_status=signature_status,
        publisher_verified=publisher_verified,
        content_digest=bundle_digest(files),
        security_scan=bundle.security_scan,
    )
    _persist_resources_and_version(
        client,
        org_id=org_id,
        package=installed,
        resources=list(bundle.resources),
        user_id=str(user.get("user_id") or ""),
    )
    return {
        "package": installed,
        "inspection": inspection.as_dict(),
        "activationPlan": build_activation_plan(bundle.manifest, inspection.as_dict()),
        "resourceCount": len(bundle.resources),
        "securityScan": bundle.security_scan,
        "directExecutionEnabled": False,
        "fileName": archive.filename,
    }


@router.get("/packages/{package_id}/versions")
async def get_portable_package_versions(
    package_id: str,
    member: Annotated[tuple[dict, str, str], Depends(require_org_member)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    _user, org_id, _role = member
    client = get_supabase_client(settings)
    if not get_package(client, org_id, package_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Capability package not found")
    return {"items": list_package_versions(client, org_id=org_id, package_id=package_id)}


@router.post("/packages/{package_id}/versions/{version_id}/rollback")
async def rollback_portable_package_version(
    package_id: str,
    version_id: str,
    admin: Annotated[tuple[dict, str], Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    user, org_id = admin
    client = get_supabase_client(settings)
    current = get_package(client, org_id, package_id)
    if not current:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Capability package not found")
    version_row = get_package_version(
        client,
        org_id=org_id,
        package_id=package_id,
        version_id=version_id,
    )
    if not version_row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Capability package version not found")
    restored = restore_package_version(
        client,
        org_id=org_id,
        package_id=package_id,
        version_row=version_row,
        user_id=str(user.get("user_id") or ""),
    )
    if not restored:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Capability rollback did not persist")
    record_package_version(
        client,
        org_id=org_id,
        package=restored,
        resources=list_package_resources(client, org_id, package_id),
        user_id=str(user.get("user_id") or ""),
    )
    return {
        "package": restored,
        "restoredFromVersionId": version_id,
        "status": restored.get("status"),
        "requiresReview": restored.get("status") == "quarantined",
    }


@router.get("/packages/{package_id}/resources")
async def get_portable_package_resources(
    package_id: str,
    member: Annotated[tuple[dict, str, str], Depends(require_org_member)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    _user, org_id, _role = member
    client = get_supabase_client(settings)
    return {"items": list_package_resources(client, org_id, package_id)}


@router.get("/trusted-publishers")
async def get_trusted_capability_publishers(
    member: Annotated[tuple[dict, str, str], Depends(require_org_member)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    _user, org_id, _role = member
    client = get_supabase_client(settings)
    return {"items": list_trusted_publishers(client, org_id)}


@router.post("/trusted-publishers")
async def add_trusted_capability_publisher(
    body: TrustedPublisherCreateRequest,
    admin: Annotated[tuple[dict, str], Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    user, org_id = admin
    client = get_supabase_client(settings)
    try:
        row = trust_publisher_key(
            client,
            org_id=org_id,
            publisher_name=body.publisher_name,
            public_key_pem=body.public_key_pem,
            user_id=str(user.get("user_id") or ""),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    return {"publisher": row}


@router.get("/marketplaces")
async def get_capability_marketplaces(
    member: Annotated[tuple[dict, str, str], Depends(require_org_member)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    _user, org_id, _role = member
    client = get_supabase_client(settings)
    return {"items": list_marketplace_sources(client, org_id)}


@router.post("/marketplaces")
async def add_capability_marketplace(
    body: GitMarketplaceSourceCreateRequest,
    admin: Annotated[tuple[dict, str], Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    user, org_id = admin
    try:
        repository_url = normalize_github_repository_url(body.repository_url)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    client = get_supabase_client(settings)
    source = create_marketplace_source(
        client,
        org_id=org_id,
        user_id=str(user.get("user_id") or ""),
        name=body.name,
        repository_url=repository_url,
        branch=body.branch,
        root_path=body.root_path,
        auto_sync=body.auto_sync,
        approval_required=body.approval_required,
    )
    return {
        "marketplace": source,
        "sync": {
            "automatic": bool(body.auto_sync),
            "approvalRequired": bool(body.approval_required),
            "executionOwner": "gravitre",
        },
    }


@router.post("/packages/{package_id}/review")
async def review_portable_package(
    package_id: str,
    body: PackageReviewRequest,
    admin: Annotated[tuple[dict, str], Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    user, org_id = admin
    client = get_supabase_client(settings)
    package = get_package(client, org_id, package_id)
    if not package:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Capability package not found")
    if not review_transition_allowed(
        current_status=str(package.get("status") or ""),
        target_status=body.status,
        risk_level=str(package.get("risk_level") or ""),
        license_policy=str(package.get("license_policy") or ""),
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Requested package review transition is not allowed",
        )
    reviewer_id = str(user.get("user_id") or "")
    updated = review_package(
        client,
        org_id=org_id,
        package_id=package_id,
        reviewer_id=reviewer_id,
        target_status=body.status,
        notes=body.notes,
    )
    try:
        from app.workflows.audit import write_audit_event

        write_audit_event(
            client,
            org_id,
            reviewer_id,
            "capability.package.reviewed",
            "capability_package",
            package_id,
            {
                "previousStatus": package.get("status"),
                "status": body.status,
                "riskLevel": package.get("risk_level"),
                "licensePolicy": package.get("license_policy"),
                "signatureStatus": package.get("signature_status"),
                "notes": body.notes,
            },
        )
    except Exception:
        pass
    return {"package": updated, "reviewed": True}


@router.post("/packages/{package_id}/prepare-mcp")
async def prepare_portable_package_mcp(
    package_id: str,
    admin: Annotated[tuple[dict, str], Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    user, org_id = admin
    client = get_supabase_client(settings)
    package = get_package(client, org_id, package_id)
    if not package:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Capability package not found")
    if str(package.get("status") or "") != "installed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Capability package must be approved and installed before MCP dependencies are prepared",
        )
    manifest = package.get("manifest") if isinstance(package.get("manifest"), dict) else {}
    return prepare_mcp_dependencies(
        client,
        org_id=org_id,
        package_id=package_id,
        manifest=manifest,
        user_id=str(user.get("user_id") or ""),
    )


@router.post("/marketplaces/{source_id}/sync")
async def sync_capability_marketplace(
    source_id: str,
    admin: Annotated[tuple[dict, str], Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    user, org_id = admin
    client = get_supabase_client(settings)
    source = get_marketplace_source(client, org_id, source_id)
    if not source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Capability marketplace not found")
    if str(source.get("source_type") or "") != "github":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Unsupported marketplace source type")
    update_marketplace_sync_status(
        client,
        org_id=org_id,
        source_id=source_id,
        sync_status="syncing",
    )
    try:
        result = await sync_public_github_marketplace(
            client,
            org_id=org_id,
            user_id=str(user.get("user_id") or ""),
            source=source,
            settings=settings,
        )
    except Exception as exc:  # noqa: BLE001
        update_marketplace_sync_status(
            client,
            org_id=org_id,
            source_id=source_id,
            sync_status="failed",
            error=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Capability marketplace sync failed: {exc}",
        ) from exc
    update_marketplace_sync_status(
        client,
        org_id=org_id,
        source_id=source_id,
        sync_status="completed",
        synced=True,
    )
    return {"sync": result, "sourceId": source_id, "status": "completed"}


@router.get("/marketplace-candidates")
async def get_capability_marketplace_candidates(
    member: Annotated[tuple[dict, str, str], Depends(require_org_member)],
    settings: Annotated[Settings, Depends(get_settings)],
    source_id: str | None = None,
    candidate_status: str | None = None,
) -> dict:
    _user, org_id, _role = member
    client = get_supabase_client(settings)
    return {
        "items": list_marketplace_candidates(
            client,
            org_id,
            source_id=source_id,
            status=candidate_status,
        )
    }


@router.post("/marketplace-candidates/{candidate_id}/review")
async def review_capability_marketplace_candidate(
    candidate_id: str,
    body: CandidateReviewRequest,
    admin: Annotated[tuple[dict, str], Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    user, org_id = admin
    client = get_supabase_client(settings)
    candidate = get_marketplace_candidate(client, org_id, candidate_id)
    if not candidate:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Capability candidate not found")
    if body.decision == "approve":
        security_scan = candidate.get("security_scan") if isinstance(candidate.get("security_scan"), dict) else {}
        if (
            str(candidate.get("license_policy") or "") == "block"
            or str(candidate.get("risk_level") or "") == "blocked"
            or bool(security_scan.get("blocked"))
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Blocked capability candidate cannot be approved",
            )
    row = review_marketplace_candidate(
        client,
        org_id=org_id,
        candidate_id=candidate_id,
        user_id=str(user.get("user_id") or ""),
        decision=body.decision,
        notes=body.notes,
    )
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Capability candidate not found")
    return {"candidate": row}


@router.post("/marketplace-candidates/{candidate_id}/install")
async def install_capability_marketplace_candidate(
    candidate_id: str,
    admin: Annotated[tuple[dict, str], Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    user, org_id = admin
    client = get_supabase_client(settings)
    candidate = get_marketplace_candidate(client, org_id, candidate_id)
    if not candidate:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Capability candidate not found")
    if str(candidate.get("status") or "") != "approved":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Capability candidate must be approved before installation",
        )
    files = dict(candidate.get("files") or {})
    bundle = import_file_bundle(files)
    inspection = bundle.inspection
    if not installation_allowed(inspection) or bool(bundle.security_scan.get("blocked")):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Candidate is blocked by capability security policy",
        )
    source = get_marketplace_source(
        client,
        org_id,
        str(candidate.get("marketplace_source_id") or ""),
    ) or {}
    installed = install_package(
        client,
        org_id=org_id,
        user_id=str(user.get("user_id") or ""),
        inspection=inspection,
        manifest=bundle.manifest,
        source_type="marketplace",
        source_uri=(
            f"{source.get('repository_url')}@{candidate.get('source_commit_sha')}#/{candidate.get('source_package_path') or candidate.get('package_path') or ''}"
            if source.get("repository_url") and candidate.get("source_commit_sha")
            else str(source.get("repository_url") or "") or None
        ),
        source_commit_sha=str(candidate.get("source_commit_sha") or "") or None,
        source_package_path=str(candidate.get("source_package_path") or candidate.get("package_path") or "") or None,
        marketplace_source_id=str(candidate.get("marketplace_source_id") or "") or None,
        publisher_name=str(bundle.manifest.get("publisher") or bundle.manifest.get("author") or "").strip() or None,
        publisher_verified=False,
        signature_status="unsigned",
        content_digest=str(candidate.get("content_digest") or bundle_digest(files)),
        security_scan=bundle.security_scan,
    )
    _persist_resources_and_version(
        client,
        org_id=org_id,
        package=installed,
        resources=list(bundle.resources),
        user_id=str(user.get("user_id") or ""),
    )
    (
        client.table("capability_marketplace_candidates")
        .update({"status": "installed"})
        .eq("org_id", org_id)
        .eq("id", candidate_id)
        .execute()
    )
    return {
        "package": installed,
        "candidateId": candidate_id,
        "activationPlan": build_activation_plan(bundle.manifest, inspection.as_dict()),
        "securityScan": bundle.security_scan,
        "directExecutionEnabled": False,
    }
