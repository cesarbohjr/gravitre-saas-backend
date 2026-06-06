"""Partner connector marketplace — submissions and registry (STA-71)."""
from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from supabase import create_client

from app.auth.dependencies import get_current_user, get_org_context, require_admin
from app.config import Settings, get_settings
from app.services.partner_marketplace_service import (
    AUDIT_CONNECTOR_PUBLISHED,
    AUDIT_SUBMISSION_CREATED,
    AUDIT_SUBMISSION_REVIEWED,
    RESOURCE_TYPE_PARTNER_REGISTRY,
    RESOURCE_TYPE_PARTNER_SUBMISSION,
    create_submission,
    get_submission,
    list_registry,
    list_submissions,
    review_submission,
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

    model_config = {"populate_by_name": True}


class ReviewSubmissionRequest(BaseModel):
    decision: Literal["approve", "reject"]
    notes: str | None = None


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
    return {"connectors": list_registry(client)}


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
    return {"submission": get_submission(client, submission_id, org_id=org_id, admin=True)}


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
