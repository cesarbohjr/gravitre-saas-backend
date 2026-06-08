"""Partner connector marketplace — submissions and registry (STA-71)."""
from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from supabase import create_client

from app.auth.dependencies import get_current_user, get_org_context, require_admin
from app.config import Settings, get_settings
from app.services.partner_marketplace_service import (
    AUDIT_CERTIFICATION_SCANNED,
    AUDIT_CONNECTOR_PUBLISHED,
    AUDIT_SUBMISSION_CREATED,
    AUDIT_SUBMISSION_REVIEWED,
    RESOURCE_TYPE_PARTNER_REGISTRY,
    RESOURCE_TYPE_PARTNER_SUBMISSION,
    create_submission,
    get_submission,
    list_registry,
    list_submissions,
    rescan_submission_certification,
    review_submission,
)
from app.services.marketplace_billing_service import (
    AUDIT_CONNECT_ONBOARDING,
    AUDIT_PRICING_UPDATED,
    RESOURCE_TYPE_MARKETPLACE_BILLING,
    create_partner_onboarding_link,
    enrich_registry_with_pricing,
    get_partner_billing_status,
    list_partner_pricing,
    list_recent_usage_events,
    sync_partner_connect_account,
    upsert_connector_pricing,
)
from app.services.private_connector_bundle_service import (
    AUDIT_PRIVATE_BUNDLE_ACTIVATED,
    AUDIT_PRIVATE_BUNDLE_DISABLED,
    AUDIT_PRIVATE_BUNDLE_UPLOADED,
    RESOURCE_TYPE_PRIVATE_BUNDLE,
    activate_private_bundle,
    disable_private_bundle,
    get_private_bundle,
    list_private_bundles,
    upload_private_bundle,
)
from app.services.marketplace_sandbox_service import (
    AUDIT_SANDBOX_DEMO,
    AUDIT_SANDBOX_PROVISIONED,
    AUDIT_SANDBOX_RESET,
    RESOURCE_TYPE_MARKETPLACE_SANDBOX,
    get_sandbox_status,
    provision_sandbox,
    reset_sandbox,
    run_sandbox_demo,
)
from app.services.agent_role_marketplace_service import (
    RoleMarketplaceError,
    get_department_pack,
    install_department_pack,
    list_department_packs,
)
from app.workflows.audit import write_audit_event

router = APIRouter(prefix="/api/marketplace", tags=["marketplace"])


class SecurityChecklistRequest(BaseModel):
    no_hardcoded_secrets: bool = Field(alias="noHardcodedSecrets")
    oauth_redirects_documented: bool = Field(alias="oauthRedirectsDocumented")
    scopes_minimized: bool = Field(alias="scopesMinimized")
    data_residency_documented: bool = Field(alias="dataResidencyDocumented")
    audit_logging_compatible: bool = Field(alias="auditLoggingCompatible")
    error_handling_documented: bool = Field(alias="errorHandlingDocumented")

    model_config = {"populate_by_name": True}


class SubmissionCreateRequest(BaseModel):
    manifest: dict[str, Any]
    security_checklist: SecurityChecklistRequest = Field(alias="securityChecklist")
    package_sources: dict[str, str] = Field(default_factory=dict, alias="packageSources")

    model_config = {"populate_by_name": True}


class ReviewSubmissionRequest(BaseModel):
    decision: Literal["approve", "reject"]
    notes: str | None = None


class ConnectorPricingRequest(BaseModel):
    pricing_model: Literal["free", "flat_monthly", "per_invocation"] = Field(alias="pricingModel")
    price_cents: int = Field(default=0, alias="priceCents", ge=0)
    currency: str = "usd"

    model_config = {"populate_by_name": True}


class ConnectOnboardRequest(BaseModel):
    return_url: str = Field(alias="returnUrl")
    refresh_url: str = Field(alias="refreshUrl")

    model_config = {"populate_by_name": True}


class PrivateBundleUploadRequest(BaseModel):
    name: str
    manifest: dict[str, Any]
    package_sources: dict[str, str] = Field(alias="packageSources")
    signing_public_key_pem: str = Field(alias="signingPublicKeyPem")
    signature: str

    model_config = {"populate_by_name": True}


@router.get("/registry")
async def list_marketplace_registry(
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """List published partner connectors."""
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    connectors = enrich_registry_with_pricing(client, list_registry(client))
    return {"connectors": connectors}


@router.get("/submissions")
async def list_marketplace_submissions(
    admin_ctx: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
    status_filter: Annotated[str | None, Query(alias="status")] = None,
) -> dict:
    """List submissions. Admins see all pending/review queue."""
    _user, org_id = admin_ctx
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    return {
        "submissions": list_submissions(
            client,
            org_id=org_id,
            admin=True,
            status_filter=status_filter,
        )
    }


@router.get("/submissions/mine")
async def list_my_submissions(
    current_user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
    status_filter: Annotated[str | None, Query(alias="status")] = None,
) -> dict:
    """List submissions for the current org."""
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    return {
        "submissions": list_submissions(
            client,
            org_id=org_id,
            admin=False,
            status_filter=status_filter,
        )
    }


@router.post("/submissions", status_code=status.HTTP_201_CREATED)
async def submit_partner_connector(
    body: SubmissionCreateRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """Submit a partner connector package for review."""
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    submission = create_submission(
        client,
        org_id=org_id,
        submitted_by=current_user["user_id"],
        manifest=body.manifest,
        security_checklist=body.security_checklist.model_dump(),
        package_sources=body.package_sources or None,
    )
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=current_user["user_id"],
        action=AUDIT_SUBMISSION_CREATED,
        resource_type=RESOURCE_TYPE_PARTNER_SUBMISSION,
        resource_id=submission["id"],
        metadata={"vendor": submission["vendor"], "packageId": submission["packageId"]},
    )
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=current_user["user_id"],
        action=AUDIT_CERTIFICATION_SCANNED,
        resource_type=RESOURCE_TYPE_PARTNER_SUBMISSION,
        resource_id=submission["id"],
        metadata={
            "vendor": submission["vendor"],
            "certificationStatus": submission.get("certificationStatus"),
        },
    )
    return {"submission": submission}


@router.get("/submissions/{submission_id}")
async def get_marketplace_submission(
    submission_id: str,
    admin_ctx: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """Get submission detail (admin)."""
    _user, org_id = admin_ctx
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    return {"submission": get_submission(client, submission_id, org_id=org_id, admin=True, include_sources=True)}


@router.post("/submissions/{submission_id}/rescan")
async def rescan_marketplace_submission(
    submission_id: str,
    admin_ctx: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """Re-run automated security scan and scope review (admin)."""
    user, org_id = admin_ctx
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    submission = rescan_submission_certification(client, submission_id)
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=user["user_id"],
        action=AUDIT_CERTIFICATION_SCANNED,
        resource_type=RESOURCE_TYPE_PARTNER_SUBMISSION,
        resource_id=submission_id,
        metadata={"certificationStatus": submission.get("certificationStatus")},
    )
    return {"submission": submission}


@router.post("/submissions/{submission_id}/review")
async def review_marketplace_submission(
    submission_id: str,
    body: ReviewSubmissionRequest,
    admin_ctx: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """Approve or reject a partner connector submission."""
    user, org_id = admin_ctx
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    result = review_submission(
        client,
        submission_id=submission_id,
        reviewer_id=user["user_id"],
        org_id=org_id,
        decision=body.decision,
        notes=body.notes,
    )
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=user["user_id"],
        action=AUDIT_SUBMISSION_REVIEWED,
        resource_type=RESOURCE_TYPE_PARTNER_SUBMISSION,
        resource_id=submission_id,
        metadata={"decision": body.decision, "notes": (body.notes or "")[:500]},
    )
    registry = result.get("registry")
    if registry:
        write_audit_event(
            client,
            org_id=str(registry["orgId"]),
            actor_id=user["user_id"],
            action=AUDIT_CONNECTOR_PUBLISHED,
            resource_type=RESOURCE_TYPE_PARTNER_REGISTRY,
            resource_id=registry["id"],
            metadata={"vendor": registry["vendor"], "version": registry["version"]},
        )
    return result


@router.get("/sandbox")
async def marketplace_sandbox_status(
    current_user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """Return partner sandbox status for the current publisher org."""
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    return get_sandbox_status(client, org_id)


@router.post("/sandbox", status_code=status.HTTP_201_CREATED)
async def marketplace_sandbox_provision(
    current_user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """Provision isolated sandbox org for partner connector QA (idempotent)."""
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    result = provision_sandbox(
        client,
        settings,
        publisher_org_id=org_id,
        user_id=current_user["user_id"],
    )
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=current_user["user_id"],
        action=AUDIT_SANDBOX_PROVISIONED,
        resource_type=RESOURCE_TYPE_MARKETPLACE_SANDBOX,
        resource_id=result["sandboxOrgId"],
        metadata={"created": result.get("created"), "sandboxOrgId": result["sandboxOrgId"]},
    )
    return result


@router.post("/sandbox/reset")
async def marketplace_sandbox_reset(
    current_user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """Re-seed sandbox demo agents, connectors, and workflows."""
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    result = reset_sandbox(client, settings, publisher_org_id=org_id)
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=current_user["user_id"],
        action=AUDIT_SANDBOX_RESET,
        resource_type=RESOURCE_TYPE_MARKETPLACE_SANDBOX,
        resource_id=result["sandboxOrgId"],
        metadata={"sandboxOrgId": result["sandboxOrgId"]},
    )
    return result


@router.post("/sandbox/demo")
async def marketplace_sandbox_demo(
    current_user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """STA-73: Run Acme Tools demo invoke in sandbox and return audit trail."""
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    result = run_sandbox_demo(
        client,
        settings,
        publisher_org_id=org_id,
        actor_id=current_user["user_id"],
    )
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=current_user["user_id"],
        action=AUDIT_SANDBOX_DEMO,
        resource_type=RESOURCE_TYPE_MARKETPLACE_SANDBOX,
        resource_id=result["sandboxOrgId"],
        metadata={
            "sandboxOrgId": result["sandboxOrgId"],
            "action": result["action"],
            "success": result["success"],
        },
    )
    return result


@router.get("/billing/status")
async def marketplace_billing_status(
    current_user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """Partner Connect account, pricing, and earnings summary (STA-96)."""
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    status_payload = get_partner_billing_status(client, org_id)
    status_payload["platformFeeBps"] = settings.marketplace_platform_fee_bps
    status_payload["recentUsage"] = list_recent_usage_events(client, org_id)
    return status_payload


@router.post("/billing/connect/onboard")
async def marketplace_billing_connect_onboard(
    body: ConnectOnboardRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """Create Stripe Connect onboarding link for partner payouts."""
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    link = create_partner_onboarding_link(
        client,
        settings,
        org_id=org_id,
        return_url=body.return_url,
        refresh_url=body.refresh_url,
    )
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=current_user["user_id"],
        action=AUDIT_CONNECT_ONBOARDING,
        resource_type=RESOURCE_TYPE_MARKETPLACE_BILLING,
        resource_id=org_id,
        metadata={"returnUrl": body.return_url},
    )
    return link


@router.post("/billing/connect/sync")
async def marketplace_billing_connect_sync(
    current_user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """Refresh Connect account status from Stripe after onboarding."""
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    account = sync_partner_connect_account(client, settings, org_id=org_id)
    return {"account": account}


@router.get("/billing/pricing")
async def marketplace_billing_pricing_list(
    current_user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    return {"pricing": list_partner_pricing(client, org_id)}


@router.put("/billing/pricing/{registry_id}")
async def marketplace_billing_pricing_upsert(
    registry_id: str,
    body: ConnectorPricingRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    pricing = upsert_connector_pricing(
        client,
        settings,
        partner_org_id=org_id,
        registry_id=registry_id,
        pricing_model=body.pricing_model,
        price_cents=body.price_cents,
        currency=body.currency,
    )
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=current_user["user_id"],
        action=AUDIT_PRICING_UPDATED,
        resource_type=RESOURCE_TYPE_MARKETPLACE_BILLING,
        resource_id=registry_id,
        metadata={
            "pricingModel": pricing.get("pricingModel"),
            "priceCents": pricing.get("priceCents"),
        },
    )
    return {"pricing": pricing}


@router.get("/private-bundles")
async def marketplace_private_bundles_list(
    current_user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """List org-scoped private connector bundles (STA-98)."""
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    return {"bundles": list_private_bundles(client, org_id=org_id)}


@router.get("/private-bundles/{bundle_id}")
async def marketplace_private_bundle_get(
    bundle_id: str,
    current_user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    return {"bundle": get_private_bundle(client, org_id=org_id, bundle_id=bundle_id)}


@router.post("/private-bundles", status_code=status.HTTP_201_CREATED)
async def marketplace_private_bundle_upload(
    body: PrivateBundleUploadRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """Upload a signed private connector bundle (draft)."""
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    bundle = upload_private_bundle(
        client,
        org_id=org_id,
        created_by=current_user["user_id"],
        name=body.name,
        manifest=body.manifest,
        package_sources=body.package_sources,
        signing_public_key_pem=body.signing_public_key_pem,
        signature=body.signature,
    )
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=current_user["user_id"],
        action=AUDIT_PRIVATE_BUNDLE_UPLOADED,
        resource_type=RESOURCE_TYPE_PRIVATE_BUNDLE,
        resource_id=bundle["id"],
        metadata={"vendor": bundle["vendor"], "version": bundle["version"]},
    )
    return {"bundle": bundle}


@router.post("/private-bundles/{bundle_id}/activate")
async def marketplace_private_bundle_activate(
    bundle_id: str,
    admin_ctx: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """Activate a signed private bundle for sandbox invoke_tool execution."""
    user, org_id = admin_ctx
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    bundle = activate_private_bundle(
        client,
        org_id=org_id,
        bundle_id=bundle_id,
        actor_id=user["user_id"],
    )
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=user["user_id"],
        action=AUDIT_PRIVATE_BUNDLE_ACTIVATED,
        resource_type=RESOURCE_TYPE_PRIVATE_BUNDLE,
        resource_id=bundle_id,
        metadata={"vendor": bundle["vendor"], "runtime": "sandbox"},
    )
    return {"bundle": bundle}


@router.post("/private-bundles/{bundle_id}/disable")
async def marketplace_private_bundle_disable(
    bundle_id: str,
    admin_ctx: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    user, org_id = admin_ctx
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    bundle = disable_private_bundle(client, org_id=org_id, bundle_id=bundle_id)
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=user["user_id"],
        action=AUDIT_PRIVATE_BUNDLE_DISABLED,
        resource_type=RESOURCE_TYPE_PRIVATE_BUNDLE,
        resource_id=bundle_id,
        metadata={"vendor": bundle["vendor"]},
    )
    return {"bundle": bundle}


@router.get("/role-packs")
async def list_role_packs(
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
    environment: Annotated[str, Depends(get_environment_context)],
) -> dict:
    """List installable department role packs with connector readiness checklist."""
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    return {"packs": list_department_packs(client, org_id, environment_name=environment)}


@router.get("/role-packs/{pack_id}")
async def get_role_pack(
    pack_id: str,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
    environment: Annotated[str, Depends(get_environment_context)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    try:
        return get_department_pack(client, org_id, pack_id, environment_name=environment)
    except RoleMarketplaceError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND if exc.code == "NOT_FOUND" else status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post("/role-packs/{pack_id}/install")
async def install_role_pack(
    pack_id: str,
    admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
    environment: Annotated[str, Depends(get_environment_context)],
) -> dict:
    """One-click install: agents + RAG sources + workflow + connector checklist."""
    user, org_id = admin
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    try:
        return install_department_pack(
            client,
            org_id,
            pack_id,
            actor_id=user["user_id"],
            environment_name=environment,
        )
    except RoleMarketplaceError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND if exc.code == "NOT_FOUND" else status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
