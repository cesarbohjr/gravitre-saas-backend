"""Partner connector marketplace — submissions and registry (STA-71)."""
from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from supabase import create_client

from app.auth.dependencies import (
    get_current_user,
    get_environment_context,
    get_org_context,
    require_admin,
    require_platform_admin,
)
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
from app.marketplace.crud import (
    MarketplaceCrudError,
    archive_org_asset,
    create_org_asset,
    list_org_assets,
    update_org_asset,
)
from app.marketplace.publish import (
    MarketplacePublishError,
    approve_asset_for_internal_publish,
    approve_asset_for_public_publish,
    list_public_review_queue,
    reject_asset_public_review,
    reject_asset_review,
    submit_asset_for_public_review,
    submit_asset_for_review,
)
from app.marketplace.publishers import (
    MarketplacePublisherError,
    get_org_publisher_profile,
    onboard_org_publisher,
)
from app.marketplace.flags import MarketplaceFlagsError, set_asset_featured, set_asset_verified
from app.marketplace.browse import (
    MarketplaceBrowseError,
    get_marketplace_asset,
    list_marketplace_assets,
    marketplace_browse_error_to_marketplace_error,
)
from app.marketplace.clone import MarketplaceCloneError, clone_asset
from app.marketplace.support import (
    MarketplaceSupportError,
    delete_my_asset_review,
    list_asset_reviews,
    list_marketplace_categories,
    list_my_saves,
    list_org_installs,
    marketplace_analytics_summary,
    save_asset,
    support_error_to_browse_error,
    uninstall_marketplace_asset,
    unsave_asset,
    upsert_my_asset_review,
)
from app.marketplace.service import MarketplaceError, install_asset, preview_install
from app.marketplace.versions import MarketplaceVersionError, list_asset_versions, rollback_asset_version
from app.marketplace.entitlements import (
    AUDIT_CHECKOUT_CREATED,
    MarketplaceEntitlementError,
    RESOURCE_TYPE_MARKETPLACE_ENTITLEMENT,
    create_asset_checkout_session,
    get_entitlement_status,
)
from app.marketplace.convergence import list_federated_connector_assets
from app.marketplace.payouts import get_publisher_payout_summary, sync_pending_payouts
from app.marketplace.roi import marketplace_roi_summary
from app.marketplace.service import fetch_marketplace_asset
from app.workflows.audit import write_audit_event

router = APIRouter(prefix="/api/marketplace", tags=["marketplace"])


def _marketplace_http_error(exc: MarketplaceError) -> HTTPException:
    status_code = status.HTTP_400_BAD_REQUEST
    if exc.code == "NOT_FOUND":
        status_code = status.HTTP_404_NOT_FOUND
    elif exc.code == "CONNECTORS_NOT_READY":
        status_code = status.HTTP_409_CONFLICT
    elif exc.code == "NOT_PUBLISHED":
        status_code = status.HTTP_409_CONFLICT
    elif exc.code == "LIMIT_EXCEEDED":
        status_code = status.HTTP_400_BAD_REQUEST
    elif exc.code == "PAYMENT_REQUIRED":
        status_code = status.HTTP_402_PAYMENT_REQUIRED
    detail: dict[str, Any] | str = str(exc)
    if exc.blockers or exc.details:
        detail = {
            "message": str(exc),
            "code": exc.code,
            "can_install": False,
            "blockers": exc.blockers,
            **exc.details,
        }
    return HTTPException(status_code=status_code, detail=detail)


def _browse_http_error(exc: MarketplaceBrowseError) -> HTTPException:
    return _marketplace_http_error(marketplace_browse_error_to_marketplace_error(exc))


def _support_http_error(exc: MarketplaceSupportError) -> HTTPException:
    return _browse_http_error(support_error_to_browse_error(exc))


def _clone_http_error(exc: MarketplaceCloneError) -> HTTPException:
    return _browse_http_error(MarketplaceBrowseError(str(exc), code=exc.code))


def _version_http_error(exc: MarketplaceVersionError) -> HTTPException:
    status_code = status.HTTP_400_BAD_REQUEST
    if exc.code == "NOT_FOUND":
        status_code = status.HTTP_404_NOT_FOUND
    elif exc.code == "FORBIDDEN":
        status_code = status.HTTP_403_FORBIDDEN
    elif exc.code == "ALREADY_CURRENT":
        status_code = status.HTTP_409_CONFLICT
    return HTTPException(status_code=status_code, detail={"message": str(exc), "code": exc.code})


def _crud_http_error(exc: MarketplaceCrudError) -> HTTPException:
    status_code = status.HTTP_400_BAD_REQUEST
    if exc.code == "NOT_FOUND":
        status_code = status.HTTP_404_NOT_FOUND
    elif exc.code == "FORBIDDEN":
        status_code = status.HTTP_403_FORBIDDEN
    elif exc.code == "CONFLICT":
        status_code = status.HTTP_409_CONFLICT
    return HTTPException(status_code=status_code, detail={"message": str(exc), "code": exc.code})


def _publish_http_error(exc: MarketplacePublishError) -> HTTPException:
    return _crud_http_error(MarketplaceCrudError(str(exc), code=exc.code))


def _publisher_http_error(exc: MarketplacePublisherError) -> HTTPException:
    return _crud_http_error(MarketplaceCrudError(str(exc), code=exc.code))


def _flags_http_error(exc: MarketplaceFlagsError) -> HTTPException:
    return _crud_http_error(MarketplaceCrudError(str(exc), code=exc.code))


def _entitlement_http_error(exc: MarketplaceEntitlementError) -> HTTPException:
    status_code = status.HTTP_400_BAD_REQUEST
    if exc.code == "NOT_PUBLISHED":
        status_code = status.HTTP_404_NOT_FOUND
    elif exc.code == "ALREADY_ENTITLED":
        status_code = status.HTTP_409_CONFLICT
    return HTTPException(status_code=status_code, detail={"message": str(exc), "code": exc.code})


class AssetCheckoutRequest(BaseModel):
    success_url: str = Field(alias="successUrl")
    cancel_url: str = Field(alias="cancelUrl")

    model_config = {"populate_by_name": True}


class InstallAssetRequest(BaseModel):
    install_variables: dict[str, str] = Field(default_factory=dict, alias="installVariables")

    model_config = {"populate_by_name": True}


class RollbackAssetRequest(BaseModel):
    version: int = Field(ge=1)


class AssetReviewRequest(BaseModel):
    rating: int = Field(ge=1, le=5)
    title: str | None = None
    body: str | None = None


class CreateMarketplaceAssetRequest(BaseModel):
    slug: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=200)
    asset_type: str = Field(alias="assetType")
    config: dict[str, Any]
    description: str | None = None
    category: str | None = None
    department: str | None = None
    tags: list[str] = Field(default_factory=list)
    required_connectors: list[dict[str, Any]] = Field(default_factory=list, alias="requiredConnectors")
    required_permissions: list[Any] = Field(default_factory=list, alias="requiredPermissions")
    install_variables: list[dict[str, Any]] = Field(default_factory=list, alias="installVariables")
    business_outcome: str | None = Field(default=None, alias="businessOutcome")
    use_case: str | None = Field(default=None, alias="useCase")
    estimated_hours_saved: float | None = Field(default=None, alias="estimatedHoursSaved")

    model_config = {"populate_by_name": True}


class UpdateMarketplaceAssetRequest(BaseModel):
    slug: str | None = None
    title: str | None = None
    description: str | None = None
    category: str | None = None
    department: str | None = None
    tags: list[str] | None = None
    config: dict[str, Any] | None = None
    required_connectors: list[dict[str, Any]] | None = Field(default=None, alias="requiredConnectors")
    required_permissions: list[Any] | None = Field(default=None, alias="requiredPermissions")
    install_variables: list[dict[str, Any]] | None = Field(default=None, alias="installVariables")
    business_outcome: str | None = Field(default=None, alias="businessOutcome")
    use_case: str | None = Field(default=None, alias="useCase")
    estimated_hours_saved: float | None = Field(default=None, alias="estimatedHoursSaved")

    model_config = {"populate_by_name": True}


class RejectAssetReviewRequest(BaseModel):
    reason: str = Field(min_length=1)


class PublisherOnboardRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=120, alias="displayName")
    slug: str | None = Field(default=None, max_length=80)
    description: str | None = None
    website_url: str | None = Field(default=None, alias="websiteUrl")
    logo_url: str | None = Field(default=None, alias="logoUrl")

    model_config = {"populate_by_name": True}


class AssetFlagRequest(BaseModel):
    enabled: bool


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
    environment_name: Annotated[str, Depends(get_environment_context)],
) -> dict:
    """List installable department role packs with connector readiness checklist."""
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    return {"packs": list_department_packs(client, org_id, environment_name=environment_name)}


@router.get("/role-packs/{pack_id}")
async def get_role_pack(
    pack_id: str,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
    environment_name: Annotated[str, Depends(get_environment_context)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    try:
        return get_department_pack(client, org_id, pack_id, environment_name=environment_name)
    except RoleMarketplaceError as exc:
        status_code = status.HTTP_404_NOT_FOUND if exc.code == "NOT_FOUND" else status.HTTP_400_BAD_REQUEST
        if exc.code == "CONNECTORS_NOT_READY":
            status_code = status.HTTP_409_CONFLICT
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@router.post("/role-packs/{pack_id}/install")
async def install_role_pack(
    pack_id: str,
    admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
    environment_name: Annotated[str, Depends(get_environment_context)],
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
            environment_name=environment_name,
        )
    except RoleMarketplaceError as exc:
        status_code = status.HTTP_404_NOT_FOUND if exc.code == "NOT_FOUND" else status.HTTP_400_BAD_REQUEST
        if exc.code == "CONNECTORS_NOT_READY":
            status_code = status.HTTP_409_CONFLICT
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@router.get("/installs")
async def list_marketplace_installs(
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
    status_filter: Annotated[str | None, Query(alias="status")] = "active",
    asset_id: Annotated[str | None, Query(alias="assetId")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict:
    """Org install ledger with deep links to installed agents, workflows, and sources."""
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    try:
        return list_org_installs(
            client,
            org_id,
            status=status_filter,
            asset_id=asset_id,
            limit=limit,
            offset=offset,
        )
    except MarketplaceSupportError as exc:
        raise _support_http_error(exc) from exc


@router.get("/saves")
async def list_marketplace_saves(
    current_user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    try:
        return list_my_saves(
            client,
            org_id,
            current_user["user_id"],
            limit=limit,
            offset=offset,
        )
    except MarketplaceSupportError as exc:
        raise _support_http_error(exc) from exc


@router.get("/categories")
async def get_marketplace_categories(
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    return list_marketplace_categories(client, org_id)


@router.get("/analytics/summary")
async def get_marketplace_analytics_summary(
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    return marketplace_analytics_summary(client, org_id)


@router.get("/analytics/roi")
async def get_marketplace_roi_summary(
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
    limit: Annotated[int, Query(ge=1, le=50)] = 15,
) -> dict:
    """Strategic hours-saved ROI dashboard (MKT-AUDIT-13.2)."""
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    return marketplace_roi_summary(client, org_id, limit=limit)


@router.get("/federated-connectors")
async def list_federated_connectors(
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
    search: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict:
    """Partner registry entries in unified catalog shape (MKT-AUDIT-13.1)."""
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    return list_federated_connector_assets(client, search=search, limit=limit, offset=offset)


@router.get("/org/assets")
async def list_org_marketplace_assets(
    admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict:
    """Org-owned assets for internal publish admin queue (MKT-AUDIT-9.3)."""
    _user, org_id = admin
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    return list_org_assets(
        client,
        org_id,
        status=status_filter,
        limit=limit,
        offset=offset,
    )


@router.post("/assets", status_code=status.HTTP_201_CREATED)
async def create_marketplace_asset_route(
    body: CreateMarketplaceAssetRequest,
    admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    user, org_id = admin
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    try:
        return create_org_asset(
            client,
            org_id,
            actor_id=user["user_id"],
            slug=body.slug,
            title=body.title,
            asset_type=body.asset_type,
            config=body.config,
            description=body.description,
            category=body.category,
            department=body.department,
            tags=body.tags,
            required_connectors=body.required_connectors,
            required_permissions=body.required_permissions,
            install_variables=body.install_variables,
            business_outcome=body.business_outcome,
            use_case=body.use_case,
            estimated_hours_saved=body.estimated_hours_saved,
        )
    except MarketplaceCrudError as exc:
        raise _crud_http_error(exc) from exc


@router.patch("/assets/{asset_ref}")
async def update_marketplace_asset_route(
    asset_ref: str,
    body: UpdateMarketplaceAssetRequest,
    admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    user, org_id = admin
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    patch = body.model_dump(exclude_unset=True, by_alias=False)
    try:
        return update_org_asset(
            client,
            org_id,
            asset_ref,
            actor_id=user["user_id"],
            patch=patch,
        )
    except MarketplaceCrudError as exc:
        raise _crud_http_error(exc) from exc


@router.delete("/assets/{asset_ref}")
async def archive_marketplace_asset_route(
    asset_ref: str,
    admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    user, org_id = admin
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    try:
        return archive_org_asset(
            client,
            org_id,
            asset_ref,
            actor_id=user["user_id"],
        )
    except MarketplaceCrudError as exc:
        raise _crud_http_error(exc) from exc


@router.post("/assets/{asset_ref}/submit-for-review")
async def submit_marketplace_asset_for_review(
    asset_ref: str,
    admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    user, org_id = admin
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    try:
        return submit_asset_for_review(
            client,
            org_id,
            asset_ref,
            actor_id=user["user_id"],
        )
    except MarketplacePublishError as exc:
        raise _publish_http_error(exc) from exc


@router.post("/assets/{asset_ref}/approve")
async def approve_marketplace_asset_for_internal_publish(
    asset_ref: str,
    admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    user, org_id = admin
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    try:
        return approve_asset_for_internal_publish(
            client,
            org_id,
            asset_ref,
            actor_id=user["user_id"],
        )
    except MarketplacePublishError as exc:
        raise _publish_http_error(exc) from exc


@router.post("/assets/{asset_ref}/reject")
async def reject_marketplace_asset_review(
    asset_ref: str,
    body: RejectAssetReviewRequest,
    admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    user, org_id = admin
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    try:
        return reject_asset_review(
            client,
            org_id,
            asset_ref,
            actor_id=user["user_id"],
            reason=body.reason,
        )
    except MarketplacePublishError as exc:
        raise _publish_http_error(exc) from exc


@router.get("/publisher/me")
async def get_marketplace_publisher_profile(
    admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    _user, org_id = admin
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    publisher = get_org_publisher_profile(client, org_id)
    return {"publisher": publisher}


@router.post("/publisher/onboard")
async def onboard_marketplace_publisher(
    body: PublisherOnboardRequest,
    admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    user, org_id = admin
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    try:
        return onboard_org_publisher(
            client,
            org_id,
            actor_id=user["user_id"],
            display_name=body.display_name,
            slug=body.slug,
            description=body.description,
            website_url=body.website_url,
            logo_url=body.logo_url,
        )
    except MarketplacePublisherError as exc:
        raise _publisher_http_error(exc) from exc


@router.post("/assets/{asset_ref}/submit-for-public-review")
async def submit_marketplace_asset_for_public_review(
    asset_ref: str,
    admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    user, org_id = admin
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    try:
        return submit_asset_for_public_review(
            client,
            org_id,
            asset_ref,
            actor_id=user["user_id"],
        )
    except MarketplacePublishError as exc:
        raise _publish_http_error(exc) from exc


@router.get("/platform/review-queue")
async def list_platform_public_review_queue(
    _user: Annotated[dict, Depends(require_platform_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict:
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    return list_public_review_queue(client, limit=limit, offset=offset)


@router.post("/platform/assets/{asset_ref}/approve")
async def approve_platform_public_asset(
    asset_ref: str,
    user: Annotated[dict, Depends(require_platform_admin)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    try:
        return approve_asset_for_public_publish(
            client,
            asset_ref,
            actor_id=user["user_id"],
            org_id=org_id,
        )
    except MarketplacePublishError as exc:
        raise _publish_http_error(exc) from exc


@router.post("/platform/assets/{asset_ref}/reject")
async def reject_platform_public_asset(
    asset_ref: str,
    body: RejectAssetReviewRequest,
    user: Annotated[dict, Depends(require_platform_admin)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    try:
        return reject_asset_public_review(
            client,
            asset_ref,
            actor_id=user["user_id"],
            reason=body.reason,
            org_id=org_id,
        )
    except MarketplacePublishError as exc:
        raise _publish_http_error(exc) from exc


@router.post("/platform/assets/{asset_ref}/featured")
async def set_platform_asset_featured(
    asset_ref: str,
    body: AssetFlagRequest,
    user: Annotated[dict, Depends(require_platform_admin)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    try:
        return set_asset_featured(
            client,
            asset_ref,
            featured=body.enabled,
            actor_id=user["user_id"],
            org_id=org_id or "",
        )
    except MarketplaceFlagsError as exc:
        raise _flags_http_error(exc) from exc


@router.post("/platform/assets/{asset_ref}/verified")
async def set_platform_asset_verified(
    asset_ref: str,
    body: AssetFlagRequest,
    user: Annotated[dict, Depends(require_platform_admin)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    try:
        return set_asset_verified(
            client,
            asset_ref,
            verified=body.enabled,
            actor_id=user["user_id"],
            org_id=org_id or "",
        )
    except MarketplaceFlagsError as exc:
        raise _flags_http_error(exc) from exc


@router.get("/assets")
async def list_marketplace_assets_route(
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    category: Annotated[str | None, Query()] = None,
    department: Annotated[str | None, Query()] = None,
    asset_type: Annotated[str | None, Query(alias="assetType")] = None,
    pricing_type: Annotated[str | None, Query(alias="pricingType")] = None,
    visibility: Annotated[str | None, Query()] = None,
    featured: Annotated[bool | None, Query()] = None,
    search: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict:
    """Unified marketplace browse — published catalog with org install + connector readiness."""
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    try:
        return list_marketplace_assets(
            client,
            org_id,
            environment_name=environment_name,
            category=category,
            department=department,
            asset_type=asset_type,
            pricing_type=pricing_type,
            visibility=visibility,
            featured=featured,
            search=search,
            limit=limit,
            offset=offset,
        )
    except MarketplaceBrowseError as exc:
        raise _browse_http_error(exc) from exc


@router.get("/assets/{asset_ref}")
async def get_marketplace_asset_route(
    asset_ref: str,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
    environment_name: Annotated[str, Depends(get_environment_context)],
) -> dict:
    """Asset detail by UUID or slug, including connector pre-check for the requesting org."""
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    try:
        return get_marketplace_asset(
            client,
            org_id,
            asset_ref,
            environment_name=environment_name,
        )
    except MarketplaceBrowseError as exc:
        raise _browse_http_error(exc) from exc


@router.get("/assets/{asset_ref}/reviews")
async def list_marketplace_asset_reviews(
    asset_ref: str,
    current_user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    try:
        return list_asset_reviews(
            client,
            org_id,
            current_user["user_id"],
            asset_ref,
            limit=limit,
            offset=offset,
        )
    except MarketplaceBrowseError as exc:
        raise _browse_http_error(exc) from exc


@router.put("/assets/{asset_ref}/reviews/mine")
async def upsert_marketplace_asset_review(
    asset_ref: str,
    body: AssetReviewRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    try:
        return upsert_my_asset_review(
            client,
            org_id,
            current_user["user_id"],
            asset_ref,
            rating=body.rating,
            title=body.title,
            body=body.body,
        )
    except MarketplaceSupportError as exc:
        raise _support_http_error(exc) from exc
    except MarketplaceBrowseError as exc:
        raise _browse_http_error(exc) from exc


@router.delete("/assets/{asset_ref}/reviews/mine")
async def delete_marketplace_asset_review(
    asset_ref: str,
    current_user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    try:
        return delete_my_asset_review(
            client,
            org_id,
            current_user["user_id"],
            asset_ref,
        )
    except MarketplaceSupportError as exc:
        raise _support_http_error(exc) from exc
    except MarketplaceBrowseError as exc:
        raise _browse_http_error(exc) from exc


@router.post("/assets/{asset_ref}/save", status_code=status.HTTP_201_CREATED)
async def save_marketplace_asset(
    asset_ref: str,
    current_user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    try:
        return save_asset(client, org_id, current_user["user_id"], asset_ref)
    except MarketplaceBrowseError as exc:
        raise _browse_http_error(exc) from exc


@router.delete("/assets/{asset_ref}/save")
async def unsave_marketplace_asset(
    asset_ref: str,
    current_user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    try:
        return unsave_asset(client, org_id, current_user["user_id"], asset_ref)
    except MarketplaceSupportError as exc:
        raise _support_http_error(exc) from exc
    except MarketplaceBrowseError as exc:
        raise _browse_http_error(exc) from exc


@router.post("/assets/{asset_ref}/uninstall")
async def uninstall_marketplace_asset_route(
    asset_ref: str,
    admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """Mark org install inactive (MKT-AUDIT-8.1)."""
    user, org_id = admin
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    try:
        return uninstall_marketplace_asset(
            client,
            org_id,
            asset_ref,
            actor_id=user["user_id"],
        )
    except MarketplaceSupportError as exc:
        raise _support_http_error(exc) from exc


@router.post("/assets/{asset_ref}/clone", status_code=status.HTTP_201_CREATED)
async def clone_marketplace_asset(
    asset_ref: str,
    current_user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """Create a private draft copy of a published asset within the same org (MKT-7.2)."""
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    try:
        return clone_asset(
            client,
            org_id,
            asset_ref,
            actor_id=current_user["user_id"],
        )
    except MarketplaceCloneError as exc:
        raise _clone_http_error(exc) from exc


@router.get("/assets/{asset_ref}/versions")
async def list_marketplace_asset_versions(
    asset_ref: str,
    admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """List version history for an org-owned asset (MKT-9.4)."""
    _user, org_id = admin
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    try:
        return list_asset_versions(client, org_id, asset_ref)
    except MarketplaceVersionError as exc:
        raise _version_http_error(exc) from exc


@router.post("/assets/{asset_ref}/rollback")
async def rollback_marketplace_asset_version(
    asset_ref: str,
    body: RollbackAssetRequest,
    admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """Restore an org-owned asset from ``marketplace_asset_versions`` (MKT-9.4)."""
    user, org_id = admin
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    try:
        return rollback_asset_version(
            client,
            org_id,
            asset_ref,
            version_number=body.version,
            actor_id=user["user_id"],
        )
    except MarketplaceVersionError as exc:
        raise _version_http_error(exc) from exc


@router.get("/assets/{asset_ref}/install-check")
async def marketplace_asset_install_check(
    asset_ref: str,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
    environment_name: Annotated[str, Depends(get_environment_context)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    try:
        return preview_install(
            client,
            org_id,
            asset_ref,
            environment_name=environment_name,
        )
    except MarketplaceError as exc:
        raise _marketplace_http_error(exc) from exc


@router.get("/assets/{asset_ref}/entitlement")
async def marketplace_asset_entitlement(
    asset_ref: str,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    asset = fetch_marketplace_asset(client, asset_ref)
    return get_entitlement_status(client, org_id, asset)


@router.post("/assets/{asset_ref}/checkout")
async def marketplace_asset_checkout(
    asset_ref: str,
    body: AssetCheckoutRequest,
    admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    user, org_id = admin
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    try:
        result = create_asset_checkout_session(
            client,
            settings,
            org_id=org_id,
            asset_ref=asset_ref,
            actor_id=user["user_id"],
            success_url=body.success_url,
            cancel_url=body.cancel_url,
        )
    except MarketplaceEntitlementError as exc:
        raise _entitlement_http_error(exc) from exc
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=user["user_id"],
        action=AUDIT_CHECKOUT_CREATED,
        resource_type=RESOURCE_TYPE_MARKETPLACE_ENTITLEMENT,
        resource_id=result["entitlementId"],
        metadata={"sessionId": result["sessionId"], "assetRef": asset_ref},
    )
    return result


@router.post("/publisher/payouts/sync")
async def marketplace_publisher_payouts_sync(
    admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    _user, org_id = admin
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    result = sync_pending_payouts(client, settings, partner_org_id=org_id)
    summary = get_publisher_payout_summary(client, org_id)
    return {"sync": result, "summary": summary}


@router.post("/assets/{asset_ref}/install")
async def marketplace_asset_install(
    asset_ref: str,
    admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
    environment_name: Annotated[str, Depends(get_environment_context)],
    body: InstallAssetRequest | None = None,
) -> dict:
    user, org_id = admin
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    try:
        return install_asset(
            client,
            org_id,
            asset_ref,
            actor_id=user["user_id"],
            environment_name=environment_name,
            install_variables=(body.install_variables if body else None),
        )
    except MarketplaceError as exc:
        raise _marketplace_http_error(exc) from exc
