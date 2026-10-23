"""MSP partner program API: wholesale billing, client workspaces, rebilling.

Every route resolves the caller's role in the right org inside
``app.services.msp_program`` (MSP owner/admin for MSP actions, client owner
for approvals). The current workspace comes from the normal org context
(x-org-id, membership-checked), never from a request body.
"""
from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from supabase import create_client

from app.auth.dependencies import get_current_user, get_org_context
from app.billing import msp_billing
from app.config import Settings, get_settings
from app.core.db import shared_service_client
from app.services import msp_program

router = APIRouter(prefix="/api/msp/program", tags=["msp"])

PlanCode = Literal["node", "control", "command"]
Interval = Literal["month", "year"]


class CreateClientRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    plan_code: PlanCode
    resale_price_cents: int | None = Field(default=None, ge=0, le=100_000_000)
    resale_interval: Interval = "month"


class LinkClientRequest(BaseModel):
    client_org_id: UUID
    plan_code: PlanCode
    resale_price_cents: int | None = Field(default=None, ge=0, le=100_000_000)
    resale_interval: Interval = "month"


class UpdateClientRequest(BaseModel):
    plan_code: PlanCode | None = None
    resale_price_cents: int | None = Field(default=None, ge=0, le=100_000_000)
    resale_interval: Interval | None = None
    clear_resale_price: bool = False


class ApproveRequest(BaseModel):
    access_level: Literal["full", "health_only"]
    member_user_ids: list[UUID] = Field(default_factory=list, max_length=25)


def _client(settings: Settings):
    return shared_service_client(settings, create_client)


def _require_org(org_id: str | None) -> str:
    if not org_id:
        raise HTTPException(403, "Organization context required")
    return org_id


@router.get("")
def program_overview(
    user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """Partner status of the current workspace, for MSPs and their clients."""
    return msp_program.overview(_client(settings), settings, org_id=_require_org(org_id), user_id=user["user_id"])


@router.get("/billed-by")
def billed_by(
    user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    client = _client(settings)
    current = _require_org(org_id)
    if msp_program.member_role(client, current, user["user_id"]) is None:
        raise HTTPException(403, "Not a member of this workspace")
    return {"billed_by": msp_program.billed_by(client, current)}


@router.post("/enroll")
def enroll(
    user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    return msp_program.enroll(_client(settings), _require_org(org_id), user["user_id"])


@router.get("/clients")
def list_clients(
    user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    return msp_program.list_clients(
        _client(settings), settings, msp_org_id=_require_org(org_id), user_id=user["user_id"]
    )


@router.post("/clients", status_code=201)
def create_client_workspace(
    body: CreateClientRequest,
    user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    from app.routers.org import OrganizationCreateRequest, create_organization

    def create_org(name: str) -> dict:
        return create_organization(OrganizationCreateRequest(name=name), user, settings)

    return msp_program.create_client_workspace(
        _client(settings),
        settings,
        msp_org_id=_require_org(org_id),
        user=user,
        name=body.name.strip(),
        plan_code=body.plan_code,
        resale_price_cents=body.resale_price_cents,
        resale_interval=body.resale_interval,
        create_org=create_org,
    )


@router.post("/clients/link", status_code=201)
def link_existing_workspace(
    body: LinkClientRequest,
    user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    return msp_program.request_link(
        _client(settings),
        msp_org_id=_require_org(org_id),
        user_id=user["user_id"],
        client_org_id=str(body.client_org_id),
        plan_code=body.plan_code,
        resale_price_cents=body.resale_price_cents,
        resale_interval=body.resale_interval,
    )


@router.patch("/clients/{relationship_id}")
def update_client(
    relationship_id: UUID,
    body: UpdateClientRequest,
    user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    return msp_program.update_terms(
        _client(settings),
        settings,
        msp_org_id=_require_org(org_id),
        relationship_id=str(relationship_id),
        user_id=user["user_id"],
        plan_code=body.plan_code,
        resale_price_cents=body.resale_price_cents,
        resale_interval=body.resale_interval,
        clear_resale=body.clear_resale_price,
    )


@router.post("/clients/{relationship_id}/detach")
def detach_client(
    relationship_id: UUID,
    user: Annotated[dict, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """Either the client's owner or the MSP's owners/admins may detach."""
    return msp_program.detach(_client(settings), settings, relationship_id=str(relationship_id), user_id=user["user_id"])


@router.post("/requests/{relationship_id}/approve")
def approve_request(
    relationship_id: UUID,
    body: ApproveRequest,
    user: Annotated[dict, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    return msp_program.approve(
        _client(settings),
        settings,
        relationship_id=str(relationship_id),
        user_id=user["user_id"],
        access_level=body.access_level,
        member_user_ids=[str(u) for u in body.member_user_ids],
    )


@router.post("/requests/{relationship_id}/decline")
def decline_request(
    relationship_id: UUID,
    user: Annotated[dict, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    return msp_program.decline(_client(settings), relationship_id=str(relationship_id), user_id=user["user_id"])


@router.get("/statement.csv")
def rebilling_statement(
    user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
    period: Annotated[str | None, Query(pattern=r"^\d{4}-\d{2}$")] = None,
) -> Response:
    body, filename = msp_program.statement_csv(
        _client(settings), settings, msp_org_id=_require_org(org_id), user_id=user["user_id"], period=period
    )
    return Response(
        content=body,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "no-store"},
    )


class WholesaleCheckoutRequest(BaseModel):
    interval: Interval = "month"


@router.post("/billing/checkout")
def start_wholesale_billing(
    body: WholesaleCheckoutRequest,
    user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    client = _client(settings)
    msp_org_id = _require_org(org_id)
    msp_program.require_msp_manager(client, msp_org_id, user["user_id"])
    try:
        url = msp_billing.create_wholesale_checkout(client, settings, msp_org_id=msp_org_id, user_id=user["user_id"], interval=body.interval)
    except msp_billing.WholesaleBillingError as exc:
        status = 503 if exc.code == "not_configured" else 409
        raise HTTPException(status, {"code": exc.code, "message": exc.message}) from exc
    except Exception as exc:  # noqa: BLE001 - Stripe outage or config error
        raise HTTPException(502, {"code": "stripe_error", "message": "Stripe couldn't start checkout. Try again shortly."}) from exc
    return {"url": url}


@router.post("/billing/sync")
def sync_wholesale_billing(
    user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    client = _client(settings)
    msp_org_id = _require_org(org_id)
    msp_program.require_msp_manager(client, msp_org_id, user["user_id"])
    result = msp_billing.sync_wholesale_quantities(client, settings, msp_org_id)
    msp_billing.propagate_to_clients(client, msp_org_id)
    return result
