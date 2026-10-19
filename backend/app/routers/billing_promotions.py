"""Promotions API: public promo codes, customer discount status, and the
platform-admin promo-code / founder-offer operations.

Mounted under ``/api/billing`` next to ``billing.router``. Founder-offer issue
and revoke stay in ``billing.py``; this router adds the new surfaces.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

import stripe
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from supabase import create_client

from app.auth.dependencies import require_org_member, require_platform_admin
from app.billing import promotion_codes as promos
from app.billing.founder_offer_ops import (
    customer_founder_offer,
    release_reserved_checkout,
)
from app.config import Settings, get_settings
from app.core.db import shared_service_client
from app.core.logging import get_logger
from app.workflows.audit import write_audit_event

logger = get_logger(__name__)
router = APIRouter(prefix="/api/billing", tags=["billing-promotions"])

VALIDATE_LIMIT_PER_MINUTE = 20


def _uuid(value: str, label: str) -> str:
    try:
        return str(UUID(value))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"Invalid {label}") from exc


def _stripe_error(exc: stripe.error.StripeError) -> HTTPException:
    message = (getattr(exc, "user_message", None) or str(exc) or "Stripe request failed").strip()
    return HTTPException(status_code=400, detail=message)


@router.get("/promo-codes/validate")
async def validate_promo_code(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    code: Annotated[str, Query(max_length=64)] = "",
    plan: Annotated[str | None, Query(max_length=32)] = None,
) -> dict:
    """Public: is this code usable for ``plan``? Rate limited per client IP.

    Responses never distinguish unknown / expired / exhausted codes.
    """
    import asyncio

    from app.core.rate_limiter import _client_ip, get_rate_limiter

    # Per-IP (not x-org-id, which an anonymous caller controls).
    result = await get_rate_limiter().check(
        f"promo-validate:ip:{_client_ip(request)}", VALIDATE_LIMIT_PER_MINUTE, 60
    )
    if not result.get("allowed"):
        raise HTTPException(
            status_code=429,
            detail="Too many promo code attempts. Try again in a minute.",
            headers={"Retry-After": str(int(result.get("retry_after") or 60))},
        )
    client = shared_service_client(settings, create_client)
    validation = await asyncio.to_thread(promos.validate_promotion_code, client, settings, code, plan)
    return promos.public_validation(validation)


@router.get("/promotions/current")
def current_promotions(
    member: Annotated[tuple, Depends(require_org_member)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """The caller's org: available founder offer and the live Stripe discount."""
    _user, org_id, _role = member
    client = shared_service_client(settings, create_client)
    founder = None
    try:
        founder = customer_founder_offer(client, settings, org_id)
    except Exception:  # noqa: BLE001 — a banner must never break billing
        logger.exception("customer_founder_offer_failed org=%s", org_id)
    discount = None
    discount_unverified = False
    billing = (
        client.table("org_billing")
        .select("stripe_subscription_id")
        .eq("org_id", org_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    subscription_id = (billing[0].get("stripe_subscription_id") if billing else None) or None
    if subscription_id:
        try:
            discount = promos.active_subscription_discount(settings, subscription_id)
        except Exception:  # noqa: BLE001 — show "unverified", never break billing
            logger.warning("active_discount_lookup_failed org=%s", org_id)
            discount_unverified = True
    return {
        "founder_offer": founder,
        "active_discount": discount,
        "discount_unverified": discount_unverified,
        "promotion_codes_enabled": promos.promotion_codes_enabled(settings),
    }


# ---------------------------------------------------------------------------
# Platform admin
# ---------------------------------------------------------------------------


class PromotionCodeCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str = Field(min_length=3, max_length=40)
    percent_off: float | None = Field(default=None, gt=0, le=100)
    amount_off_cents: int | None = Field(default=None, ge=1, le=10_000_000)
    currency: str | None = Field(default=None, max_length=3)
    duration: Literal["once", "repeating", "forever"] = "repeating"
    duration_in_months: int | None = Field(default=None, ge=1, le=36)
    max_redemptions: int | None = Field(default=None, ge=1, le=1_000_000)
    expires_at: datetime | None = None
    first_time_only: bool = False
    plan_codes: list[Literal["node", "control", "command"]] = Field(default_factory=list)


@router.get("/admin/promotion-codes")
def admin_list_promotion_codes(
    _founder: Annotated[dict, Depends(require_platform_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
    refresh: bool = True,
) -> dict:
    client = shared_service_client(settings, create_client)
    return promos.list_promotion_codes(client, settings, refresh=refresh)


@router.post("/admin/promotion-codes")
def admin_create_promotion_code(
    body: PromotionCodeCreateRequest,
    founder: Annotated[dict, Depends(require_platform_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    spec = promos.validate_create_request(body)
    client = shared_service_client(settings, create_client)
    try:
        created = promos.create_promotion_code(client, settings, spec, founder["user_id"])
    except stripe.error.StripeError as exc:
        raise _stripe_error(exc) from exc
    write_audit_event(
        client,
        org_id=None,
        actor_id=founder["user_id"],
        action="billing.promotion_code.created",
        resource_type="promotion_codes",
        resource_id=str(created["id"]),
        metadata={"code": spec["code"], "summary": created["summary"]},
    )
    return created


@router.post("/admin/promotion-codes/{code_id}/deactivate")
def admin_deactivate_promotion_code(
    code_id: str,
    founder: Annotated[dict, Depends(require_platform_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    code_id = _uuid(code_id, "promo code ID")
    client = shared_service_client(settings, create_client)
    try:
        result = promos.deactivate_promotion_code(client, settings, code_id, founder["user_id"])
    except stripe.error.StripeError as exc:
        raise _stripe_error(exc) from exc
    write_audit_event(
        client,
        org_id=None,
        actor_id=founder["user_id"],
        action="billing.promotion_code.deactivated",
        resource_type="promotion_codes",
        resource_id=code_id,
        metadata={"code": result.get("code")},
    )
    return result


class ReleaseReservationRequest(BaseModel):
    revoke: bool = False


@router.post("/admin/promotional-offers/{grant_id}/release")
def admin_release_founder_checkout(
    grant_id: str,
    founder: Annotated[dict, Depends(require_platform_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
    body: ReleaseReservationRequest | None = None,
) -> dict:
    """Release a stuck "Checkout reserved" grant, optionally revoking it too."""
    grant_id = _uuid(grant_id, "grant ID")
    client = shared_service_client(settings, create_client)
    result = release_reserved_checkout(client, settings, grant_id)
    write_audit_event(
        client,
        org_id=result["org_id"],
        actor_id=founder["user_id"],
        action="billing.founder_offer.checkout_released",
        resource_type="org_promotional_grants",
        resource_id=grant_id,
        metadata={
            "attempt_id": result["released_attempt_id"],
            "expired_sessions": result["expired_checkout_sessions"],
        },
    )
    status = "available"
    if body and body.revoke:
        from app.routers.billing import revoke_founder_offer

        status = revoke_founder_offer(grant_id, founder, settings)["status"]
    return {**result, "status": status}

