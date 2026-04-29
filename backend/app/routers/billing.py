from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
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


def _default_subscription(org_id: str) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "id": org_id,
        "stripe_subscription_id": None,
        "tier": "free",
        "status": "trialing",
        "seat_count": 1,
        "lite_seats": 0,
        "current_period_start": now,
        "current_period_end": now,
        "cancel_at_period_end": False,
        "meson_addons": [],
    }


def _normalize_subscription(row: dict | None, org_id: str) -> dict:
    if not row:
        return _default_subscription(org_id)
    meson_addons = row.get("meson_addons") or []
    if not isinstance(meson_addons, list):
        meson_addons = []
    return {
        "id": str(row.get("id") or org_id),
        "stripe_subscription_id": row.get("stripe_subscription_id"),
        "tier": str(row.get("tier") or "free"),
        "status": str(row.get("status") or "trialing"),
        "seat_count": int(row.get("seat_count") or 1),
        "lite_seats": int(row.get("lite_seats") or 0),
        "current_period_start": (row.get("current_period_start") or datetime.now(timezone.utc).isoformat()),
        "current_period_end": (row.get("current_period_end") or datetime.now(timezone.utc).isoformat()),
        "cancel_at_period_end": bool(row.get("cancel_at_period_end") or False),
        "meson_addons": meson_addons,
    }


def _map_usage_for_billing_status(usage_payload: dict) -> dict:
    period_start = str(usage_payload.get("period_start") or datetime.now(timezone.utc).isoformat())
    tier = usage_payload.get("tier")
    totals = usage_payload.get("totals") or {}
    return {
        "period_start": period_start,
        "tier": tier,
        "totals": {
            "outputs": int(totals.get("outputs") or 0),
            "workflow_runs": int(totals.get("workflow_runs") or 0),
            "api_calls": int(totals.get("api_calls") or 0),
            "ai_tokens": int(totals.get("ai_tokens") or 0),
        },
        "included_outputs": usage_payload.get("included_outputs"),
        "overage_outputs": int(usage_payload.get("overage_outputs") or 0),
        "overage_cost_usd": float(usage_payload.get("overage_cost_usd") or 0),
    }
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
    plan_code: str | None = Field(default=None, alias="planCode")
    price_id: str | None = Field(default=None, alias="price_id")
    quantity: int | None = Field(default=1, ge=1)


class SeatsRequest(BaseModel):
    quantity: int = Field(..., ge=1)


class CancelRequest(BaseModel):
    at_period_end: bool = Field(default=True)


def _usage_from_records(client, org_id: str, tier: str | None) -> dict:
    now = datetime.now(timezone.utc)
    period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    usage_rows = (
        client.table("usage_records")
        .select("metric_type, quantity")
        .eq("org_id", org_id)
        .gte("recorded_at", period_start.isoformat())
        .execute()
    )
    totals = {"outputs": 0, "workflow_runs": 0, "api_calls": 0, "ai_tokens": 0}
    for row in usage_rows.data or []:
        metric_type = str(row.get("metric_type") or "")
        quantity = int(row.get("quantity") or 0)
        if metric_type in totals:
            totals[metric_type] += quantity
    included_outputs_map = {"free": 1000, "node": 10000, "control": 50000, "command": 200000}
    included_outputs = included_outputs_map.get((tier or "free").lower(), 1000)
    overage_outputs = max(totals["outputs"] - included_outputs, 0)
    return {
        "period_start": period_start.isoformat(),
        "tier": tier,
        "totals": totals,
        "included_outputs": included_outputs,
        "overage_outputs": overage_outputs,
        "overage_cost_usd": round(overage_outputs * 0.0002, 4),
    }


def _fetch_invoices_and_payment_methods(settings: Settings, customer_id: str | None) -> tuple[list[dict], list[dict]]:
    if not settings.stripe_secret_key or not customer_id:
        return ([], [])
    stripe.api_key = settings.stripe_secret_key
    invoices: list[dict] = []
    payment_methods: list[dict] = []
    def _ts_to_iso(ts_value: int | None) -> str:
        if not ts_value:
            return datetime.now(timezone.utc).isoformat()
        return datetime.fromtimestamp(int(ts_value), tz=timezone.utc).isoformat()
    try:
        stripe_invoices = stripe.Invoice.list(customer=customer_id, limit=20)
        for invoice in stripe_invoices.data:
            invoices.append(
                {
                    "id": invoice.get("id"),
                    "stripe_invoice_id": invoice.get("id"),
                    "amount_cents": int(invoice.get("amount_paid") or invoice.get("amount_due") or 0),
                    "currency": str(invoice.get("currency") or "usd"),
                    "status": str(invoice.get("status") or "open"),
                    "period_start": _ts_to_iso(invoice.get("period_start") or invoice.get("created")),
                    "period_end": _ts_to_iso(invoice.get("period_end") or invoice.get("created")),
                    "pdf_url": invoice.get("invoice_pdf"),
                    "created_at": _ts_to_iso(invoice.get("created")),
                }
            )
    except Exception:
        invoices = []
    try:
        pm_list = stripe.PaymentMethod.list(customer=customer_id, type="card", limit=10)
        customer = stripe.Customer.retrieve(customer_id)
        default_pm = None
        if isinstance(customer, dict):
            invoice_settings = customer.get("invoice_settings") or {}
            default_pm = invoice_settings.get("default_payment_method")
        for method in pm_list.data:
            card = method.get("card") or {}
            payment_methods.append(
                {
                    "id": method.get("id"),
                    "type": method.get("type") or "card",
                    "last4": card.get("last4") or "0000",
                    "exp_month": int(card.get("exp_month") or 0),
                    "exp_year": int(card.get("exp_year") or 0),
                    "is_default": bool(default_pm and method.get("id") == default_pm),
                }
            )
    except Exception:
        payment_methods = []
    return (invoices, payment_methods)


@router.get("")
async def billing_overview(
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    sub_resp = client.table("subscriptions").select("*").eq("org_id", org_id).limit(1).execute()
    if sub_resp.error:
        raise HTTPException(status_code=500, detail=str(sub_resp.error))
    subscription_row = (sub_resp.data or [None])[0]
    if subscription_row is None:
        insert_resp = (
            client.table("subscriptions")
            .insert({"org_id": org_id, "tier": "free", "status": "trialing", "seat_count": 1, "lite_seats": 0})
            .select("*")
            .limit(1)
            .execute()
        )
        subscription_row = (insert_resp.data or [None])[0]
    subscription = _normalize_subscription(subscription_row, org_id)
    usage = _usage_from_records(client, org_id, subscription.get("tier"))
    invoices, payment_methods = _fetch_invoices_and_payment_methods(
        settings=settings,
        customer_id=(subscription_row or {}).get("stripe_customer_id"),
    )
    return {
        "subscription": subscription,
        "usage": _map_usage_for_billing_status(usage),
        "invoices": invoices,
        "payment_methods": payment_methods,
    }


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
    plan_code = (body.plan_code or "").strip().lower() or None
    price_id = (body.price_id or "").strip() or None
    if not price_id and plan_code:
        price_id = price_id_for_plan(settings, plan_code)
    if not plan_code and price_id:
        mapped = plan_code_for_price(settings, price_id)
        plan_code = mapped or "free"
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
    return {"url": session.url, "checkout_url": session.url}


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
    return {"url": portal.url, "portal_url": portal.url}


@router.post("/seats")
async def update_seats(
    body: SeatsRequest,
    _admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    _user, org_id = _admin
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    response = (
        client.table("subscriptions")
        .upsert({"org_id": org_id, "seat_count": body.quantity, "updated_at": datetime.now(timezone.utc).isoformat()}, on_conflict="org_id")
        .select("*")
        .limit(1)
        .execute()
    )
    if response.error:
        raise HTTPException(status_code=500, detail=str(response.error))
    row = (response.data or [None])[0]
    return {"subscription": _normalize_subscription(row, org_id)}


@router.post("/cancel")
async def cancel_subscription(
    body: CancelRequest,
    _admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    _user, org_id = _admin
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    status_value = "active" if body.at_period_end else "canceled"
    response = (
        client.table("subscriptions")
        .upsert(
            {
                "org_id": org_id,
                "cancel_at_period_end": body.at_period_end,
                "status": status_value,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
            on_conflict="org_id",
        )
        .select("*")
        .limit(1)
        .execute()
    )
    if response.error:
        raise HTTPException(status_code=500, detail=str(response.error))
    return _normalize_subscription((response.data or [None])[0], org_id)


@router.post("/reactivate")
async def reactivate_subscription(
    _admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    _user, org_id = _admin
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    response = (
        client.table("subscriptions")
        .upsert(
            {
                "org_id": org_id,
                "cancel_at_period_end": False,
                "status": "active",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
            on_conflict="org_id",
        )
        .select("*")
        .limit(1)
        .execute()
    )
    if response.error:
        raise HTTPException(status_code=500, detail=str(response.error))
    return _normalize_subscription((response.data or [None])[0], org_id)


@router.get("/invoices")
async def list_invoices(
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    sub_resp = client.table("subscriptions").select("stripe_customer_id").eq("org_id", org_id).limit(1).execute()
    customer_id = ((sub_resp.data or [{}])[0]).get("stripe_customer_id")
    invoices, _payment_methods = _fetch_invoices_and_payment_methods(settings, customer_id)
    return {"invoices": invoices}


@router.get("/invoices/{invoice_id}/pdf")
async def download_invoice_pdf(
    invoice_id: str,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    if not settings.stripe_secret_key:
        raise HTTPException(status_code=503, detail="Stripe is not configured")
    stripe.api_key = settings.stripe_secret_key
    try:
        invoice = stripe.Invoice.retrieve(invoice_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"Invoice not found: {exc}") from exc
    pdf_url = invoice.get("invoice_pdf")
    if not pdf_url:
        raise HTTPException(status_code=404, detail="Invoice PDF unavailable")
    return Response(
        content=pdf_url,
        media_type="text/plain",
        headers={"Content-Disposition": f'inline; filename="{invoice_id}.txt"'},
    )


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
