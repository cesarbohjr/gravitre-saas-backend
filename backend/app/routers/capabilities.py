"""Tenant capability registry and portable package ingestion."""
from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.auth.dependencies import get_environment_context, require_admin, require_org_member
from app.capabilities.activation import build_activation_plan
from app.capabilities.importers import import_file_bundle
from app.capabilities.packages import inspect_package, installation_allowed
from app.capabilities.provenance import bundle_digest, normalize_github_repository_url
from app.capabilities.registry import tenant_capability_snapshot
from app.capabilities.repository import (
    create_marketplace_source,
    install_package,
    list_marketplace_sources,
    list_package_resources,
    list_packages,
    replace_package_resources,
)
from app.config import Settings, get_settings
from app.workflows.repository import get_supabase_client

router = APIRouter(prefix="/api/capabilities", tags=["capabilities"])


class PackageInspectRequest(BaseModel):
    manifest: dict[str, Any] = Field(default_factory=dict)
    skill_md: str | None = None


class PackageBundleRequest(BaseModel):
    files: dict[str, str]
    source_type: Literal["manual", "github", "zip", "mcp", "marketplace"] = "manual"
    source_uri: str | None = None
    signing_public_key_pem: str | None = Field(default=None, alias="signingPublicKeyPem")
    signature: str | None = None

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
        "installationAllowed": installation_allowed(inspection),
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
    if not installation_allowed(inspection):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "Package blocked by capability policy", "inspection": inspection.as_dict()},
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
            signature_status = "verified"
            publisher_verified = True
        except BundleSignatureError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid capability package signature: {exc}",
            ) from exc

    client = get_supabase_client(settings)
    installed = install_package(
        client,
        org_id=org_id,
        user_id=str(user.get("user_id") or ""),
        inspection=inspection,
        manifest=bundle.manifest,
        source_type=body.source_type,
        source_uri=body.source_uri,
        publisher_name=str(bundle.manifest.get("publisher") or bundle.manifest.get("author") or "").strip() or None,
        signature_status=signature_status,
        publisher_verified=publisher_verified,
        content_digest=bundle_digest(body.files),
    )
    package_id = str(installed.get("id") or "")
    if package_id:
        replace_package_resources(
            client,
            package_id=package_id,
            org_id=org_id,
            resources=list(bundle.resources),
        )
    return {
        "package": installed,
        "inspection": inspection.as_dict(),
        "activationPlan": build_activation_plan(bundle.manifest, inspection.as_dict()),
        "resourceCount": len(bundle.resources),
        "directExecutionEnabled": False,
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
