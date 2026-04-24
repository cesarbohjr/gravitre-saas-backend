from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from supabase import create_client

from app.auth.dependencies import get_current_user, get_environment_context, get_org_context, require_admin
from app.billing.service import (
    DEFAULT_PLAN_CODE,
    get_base_plan_for_org,
    get_billing_plans,
    get_current_period,
    get_org_billing,
    get_org_billing_overrides,
    get_plan_for_org,
    get_supabase_client,
    get_usage_totals,
    overrides_active,
    usage_warning,
)
from app.billing.stripe import (
    create_checkout_session,
    create_customer_portal,
    plan_code_for_price,
    price_id_for_plan,
    verify_webhook,
)
from app.config import Settings, get_settings
from app.core.errors import error_detail
from app.workflows.audit import write_audit_event

router = APIRouter(prefix="/api/billing", tags=["billing"])
@router.get("/plans")
async def list_billing_plans(
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = get_supabase_client(settings)
    plans = list(get_billing_plans(client).values())
    return {"plans": plans}



class CheckoutRequest(BaseModel):
    plan_code: str = Field(..., alias="planCode")


@router.get("/status")
async def get_billing_status(
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    environment: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = get_supabase_client(settings)
    billing = get_org_billing(client, org_id) or {"plan_code": DEFAULT_PLAN_CODE, "billing_status": "trialing"}
    base_plan = get_base_plan_for_org(client, org_id)
    overrides = get_org_billing_overrides(client, org_id)
    plan = get_plan_for_org(client, org_id)
    period_start, period_end = get_current_period()
    usage = get_usage_totals(client, org_id, period_start, period_end, environment)
    ai_used = usage.get("ai_credits", 0)
    runs_used = usage.get("workflow_runs", 0)
    ai_included = int(plan.get("ai_credits_included") or 0)
    runs_included = int(plan.get("workflow_runs_included") or 0)
    ai_warn = usage_warning(ai_used, ai_included)
    run_warn = usage_warning(runs_used, runs_included)
    return {
        "plan": plan,
        "basePlan": base_plan,
        "overridesActive": overrides_active(overrides),
        "overrides": overrides or {},
        "billingStatus": billing.get("billing_status") or "trialing",
        "currentPeriodEnd": billing.get("current_period_end"),
        "cancelAtPeriodEnd": billing.get("cancel_at_period_end") or False,
        "usage": {
            "aiCredits": {
                "used": ai_used,
                "included": ai_included,
                "remaining": max(ai_included - ai_used, 0),
                **ai_warn,
            },
            "workflowRuns": {
                "used": runs_used,
                "included": runs_included,
                "remaining": max(runs_included - runs_used, 0),
                **run_warn,
            },
            "operatorUsage": {"used": usage.get("operator_usage", 0)},
            "ragUsage": {"used": usage.get("rag_usage", 0)},
        },
        "period": {
            "start": period_start.isoformat(),
            "end": period_end.isoformat(),
            "environment": environment,
        },
    }


@router.post("/checkout")
async def create_checkout(
    body: CheckoutRequest,
    _admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    current_user, org_id = _admin
    plan_code = body.plan_code.strip().lower()
    price_id = price_id_for_plan(settings, plan_code)
    if not price_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_detail("Invalid plan", "VALIDATION_ERROR"))
    if not settings.stripe_secret_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=error_detail("Stripe is not configured", "INVALID_CONFIG"),
        )
    app_url = (settings.public_app_url or "http://localhost:3000").rstrip("/")
    success_url = f"{app_url}/billing?status=success"
    cancel_url = f"{app_url}/pricing?status=cancelled"
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    billing = get_org_billing(client, org_id)
    customer_id = billing.get("stripe_customer_id") if billing else None
    if not customer_id:
        from stripe import Customer

        Customer.api_key = settings.stripe_secret_key
        customer = Customer.create(metadata={"org_id": org_id, "created_by": current_user["user_id"]})
        customer_id = customer["id"]
        client.table("org_billing").upsert(
            {
                "org_id": org_id,
                "stripe_customer_id": customer_id,
                "plan_code": plan_code,
                "billing_status": "trialing",
            }
        ).execute()
    session = create_checkout_session(
        settings=settings,
        customer_id=customer_id,
        price_id=price_id,
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={"org_id": org_id, "plan_code": plan_code},
    )
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=current_user["user_id"],
        action="billing.checkout.created",
        resource_type="org_billing",
        resource_id=str(org_id),
        metadata={"plan_code": plan_code},
    )
    return {"url": session.url}


@router.post("/portal")
async def create_portal(
    _admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    _user, org_id = _admin
    if not settings.stripe_secret_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=error_detail("Stripe is not configured", "INVALID_CONFIG"),
        )
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    billing = get_org_billing(client, org_id)
    customer_id = billing.get("stripe_customer_id") if billing else None
    if not customer_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stripe customer not found")
    app_url = (settings.public_app_url or "http://localhost:3000").rstrip("/")
    portal = create_customer_portal(settings=settings, customer_id=customer_id, return_url=f"{app_url}/billing")
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=_user["user_id"],
        action="billing.portal.created",
        resource_type="org_billing",
        resource_id=str(org_id),
        metadata={},
    )
    return {"url": portal.url}


@router.post("/webhook")
async def handle_webhook(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    payload = await request.body()
    signature = request.headers.get("stripe-signature")
    if not settings.stripe_webhook_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=error_detail("Stripe webhook not configured", "INVALID_CONFIG"),
        )
    event = verify_webhook(settings, payload, signature)
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    event_type = event["type"]
    data = event["data"]["object"]
    org_id = None
    if isinstance(data, dict):
        metadata = data.get("metadata") or {}
        org_id = metadata.get("org_id")
    if event_type == "checkout.session.completed":
        subscription_id = data.get("subscription")
        customer_id = data.get("customer")
        client.table("org_billing").upsert(
            {
                "org_id": org_id,
                "stripe_customer_id": customer_id,
                "stripe_subscription_id": subscription_id,
                "billing_status": "active",
            }
        ).execute()
        if org_id:
            write_audit_event(
                client,
                org_id=org_id,
                actor_id="stripe",
                action="billing.subscription.created",
                resource_type="org_billing",
                resource_id=str(org_id),
                metadata={"subscription_id": subscription_id},
            )
    if event_type in {"customer.subscription.updated", "customer.subscription.created"}:
        subscription_id = data.get("id")
        customer_id = data.get("customer")
        current_period_end = data.get("current_period_end")
        status_value = data.get("status") or "active"
        price_id = None
        items = data.get("items", {}).get("data", [])
        if items:
            price_id = items[0].get("price", {}).get("id")
        plan_code = plan_code_for_price(settings, price_id)
        update_row = {
            "org_id": org_id,
            "stripe_customer_id": customer_id,
            "stripe_subscription_id": subscription_id,
            "stripe_price_id": price_id,
            "plan_code": plan_code,
            "billing_status": status_value,
            "current_period_end": datetime.fromtimestamp(current_period_end, tz=timezone.utc).isoformat()
            if current_period_end
            else None,
            "cancel_at_period_end": bool(data.get("cancel_at_period_end")),
        }
        client.table("org_billing").upsert(update_row).execute()
        if org_id:
            write_audit_event(
                client,
                org_id=org_id,
                actor_id="stripe",
                action="billing.subscription.updated",
                resource_type="org_billing",
                resource_id=str(org_id),
                metadata={"subscription_id": subscription_id, "status": status_value},
            )
    if event_type == "customer.subscription.deleted":
        subscription_id = data.get("id")
        client.table("org_billing").update(
            {"stripe_subscription_id": None, "billing_status": "cancelled"}
        ).eq("stripe_subscription_id", subscription_id).execute()
        if org_id:
            write_audit_event(
                client,
                org_id=org_id,
                actor_id="stripe",
                action="billing.subscription.cancelled",
                resource_type="org_billing",
                resource_id=str(org_id),
                metadata={"subscription_id": subscription_id},
            )
    client.table("billing_events").insert(
        {"org_id": org_id, "event_type": event_type, "payload": event}
    ).execute()
    return {"received": True}
