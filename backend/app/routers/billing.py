from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from supabase import create_client

from app.auth.dependencies import get_current_user, get_environment_context, get_org_context, require_admin, require_org_member
from app.billing.entitlements import compute_app_access, normalize_billing_status
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
    resolve_org_id_from_checkout_metadata,
    usage_warning,
)
from app.billing.stripe import (
    create_checkout_session,
    create_customer_portal,
    create_subscription_for_payment_element,
    init_stripe,
    plan_code_for_price,
    price_id_for_plan,
)
from app.config import Settings, get_settings
from app.core.errors import error_detail
from app.core.logging import get_logger
from app.workflows.audit import write_audit_event

logger = get_logger(__name__)
router = APIRouter(prefix="/api/billing", tags=["billing"])


def _raise_stripe_http_error(exc: stripe.error.StripeError) -> None:
    message = (getattr(exc, "user_message", None) or str(exc) or "Stripe request failed").strip()
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=error_detail(message, "STRIPE_ERROR"),
    ) from exc


def _stripe_customer_missing(exc: stripe.error.StripeError) -> bool:
    if not isinstance(exc, stripe.error.InvalidRequestError):
        return False
    message = (getattr(exc, "user_message", None) or str(exc) or "").lower()
    return "no such customer" in message


def _create_stripe_customer(settings: Settings, client, org_id: str, user_id: str, plan_code: str | None) -> str:
    from stripe import Customer

    # Always init the module-level key — Customer.api_key alone is unreliable
    # across stripe-python versions and can surface "No API key provided".
    init_stripe(settings)
    customer = Customer.create(metadata={"org_id": org_id, "created_by": user_id})
    customer_id = customer["id"]
    client.table("org_billing").upsert(
        {
            "org_id": org_id,
            "stripe_customer_id": customer_id,
            "plan_code": plan_code,
            "billing_status": "trialing",
        }
    ).execute()
    return customer_id


# Health check endpoint to verify Stripe configuration
@router.get("/health")
async def billing_health(settings: Annotated[Settings, Depends(get_settings)]):
    """Check if Stripe is properly configured."""
    issues = []
    
    # Check Stripe secret key
    if not settings.stripe_secret_key:
        issues.append("STRIPE_SECRET_KEY is not set")
    elif not settings.stripe_secret_key.startswith(("sk_test_", "sk_live_")):
        issues.append("STRIPE_SECRET_KEY has invalid format")
    
    # Check webhook secret
    if not settings.stripe_webhook_secret:
        issues.append("STRIPE_WEBHOOK_SECRET is not set")
    
    # Check price IDs
    price_checks = [
        ("STRIPE_PRICE_ID_NODE_MONTHLY", settings.stripe_price_id_node_monthly),
        ("STRIPE_PRICE_ID_NODE_ANNUAL", settings.stripe_price_id_node_annual),
        ("STRIPE_PRICE_ID_CONTROL_MONTHLY", settings.stripe_price_id_control_monthly),
        ("STRIPE_PRICE_ID_CONTROL_ANNUAL", settings.stripe_price_id_control_annual),
        ("STRIPE_PRICE_ID_COMMAND_MONTHLY", settings.stripe_price_id_command_monthly),
        ("STRIPE_PRICE_ID_COMMAND_ANNUAL", settings.stripe_price_id_command_annual),
    ]
    
    for name, value in price_checks:
        if not value:
            issues.append(f"{name} is not set")
        elif not value.startswith("price_"):
            issues.append(f"{name} has invalid format (should start with 'price_')")
    
    # Test Stripe API connectivity
    stripe_connected = False
    if settings.stripe_secret_key and settings.stripe_secret_key.startswith(("sk_test_", "sk_live_")):
        try:
            stripe.api_key = settings.stripe_secret_key
            stripe.Account.retrieve()
            stripe_connected = True
        except stripe.AuthenticationError:
            issues.append("STRIPE_SECRET_KEY is invalid (authentication failed)")
        except Exception as e:
            issues.append(f"Stripe API error: {str(e)}")
    
    mode = "test" if settings.stripe_secret_key and "test" in settings.stripe_secret_key else "live"
    
    return {
        "status": "healthy" if not issues else "unhealthy",
        "stripe_connected": stripe_connected,
        "mode": mode,
        "issues": issues,
        "config": {
            "secret_key_set": bool(settings.stripe_secret_key),
            "webhook_secret_set": bool(settings.stripe_webhook_secret),
            "node_monthly_set": bool(settings.stripe_price_id_node_monthly),
            "node_annual_set": bool(settings.stripe_price_id_node_annual),
            "control_monthly_set": bool(settings.stripe_price_id_control_monthly),
            "control_annual_set": bool(settings.stripe_price_id_control_annual),
            "command_monthly_set": bool(settings.stripe_price_id_command_monthly),
            "command_annual_set": bool(settings.stripe_price_id_command_annual),
        }
    }


@router.get("/webhook/health")
async def billing_webhook_health(settings: Annotated[Settings, Depends(get_settings)]):
    """Verify Stripe webhook config and idempotency table readiness."""
    from app.billing.webhook_idempotency import check_webhook_idempotency_table

    issues: list[str] = []

    if not settings.stripe_webhook_secret:
        issues.append("STRIPE_WEBHOOK_SECRET is not set")
    elif not settings.stripe_webhook_secret.startswith("whsec_"):
        issues.append("STRIPE_WEBHOOK_SECRET has invalid format (should start with whsec_)")

    idempotency_table = {"table": "stripe_webhook_events", "reachable": False, "error": "supabase_not_configured"}
    if settings.supabase_url and settings.supabase_service_role_key:
        client = create_client(settings.supabase_url, settings.supabase_service_role_key)
        idempotency_table = check_webhook_idempotency_table(client)
        if not idempotency_table.get("reachable"):
            issues.append(
                f"stripe_webhook_events table is not reachable ({idempotency_table.get('error')})"
            )
    else:
        issues.append("Supabase is not configured for webhook idempotency checks")

    return {
        "status": "healthy" if not issues else "unhealthy",
        "issues": issues,
        "webhook_secret_set": bool(settings.stripe_webhook_secret),
        "idempotency_table": idempotency_table,
        "endpoints": {
            "legacy": "/api/billing/webhook",
            "canonical": "/api/webhooks/stripe",
        },
    }


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


def _normalize_subscription(row: dict | None, org_id: str, *, tier: str | None = None) -> dict:
    if not row:
        base = _default_subscription(org_id)
        if tier:
            base["tier"] = tier
        return base
    meson_addons = row.get("meson_addons") or []
    if not isinstance(meson_addons, list):
        meson_addons = []
    resolved_tier = str(tier or row.get("tier") or "free").strip().lower()
    return {
        "id": str(row.get("id") or org_id),
        "stripe_subscription_id": row.get("stripe_subscription_id"),
        "tier": resolved_tier,
        "status": str(row.get("status") or "trialing"),
        "seat_count": int(row.get("seat_count") or 1),
        "lite_seats": int(row.get("lite_seats") or 0),
        "current_period_start": (row.get("current_period_start") or datetime.now(timezone.utc).isoformat()),
        "current_period_end": (row.get("current_period_end") or datetime.now(timezone.utc).isoformat()),
        "cancel_at_period_end": bool(row.get("cancel_at_period_end") or False),
        "meson_addons": meson_addons,
    }


def _canonical_plan_code(client, org_id: str, subscription_row: dict | None) -> str:
    """Prefer org_billing.plan_code (entitlements source of truth) over subscriptions.tier."""
    from app.billing.service import normalize_plan_code

    billing = get_org_billing(client, org_id) or {}
    billing_code = normalize_plan_code(billing.get("plan_code"))
    sub_tier = normalize_plan_code((subscription_row or {}).get("tier"))
    # Paid org_billing always wins when present and not the bootstrap default mismatch case
    # handled by Stripe reconcile below.
    if billing.get("plan_code"):
        return billing_code
    return sub_tier or DEFAULT_PLAN_CODE


def _reconcile_plan_from_stripe(
    client,
    settings: Settings,
    org_id: str,
    subscription_row: dict | None,
) -> str | None:
    """Repair local plan/price rows from the live Stripe subscription (single SoT)."""
    sub_id = str((subscription_row or {}).get("stripe_subscription_id") or "").strip()
    if not sub_id or not settings.stripe_secret_key:
        return None
    try:
        init_stripe(settings)
        stripe_sub = stripe.Subscription.retrieve(sub_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("stripe reconcile retrieve failed org_id=%s error=%s", org_id, exc)
        return None

    if hasattr(stripe_sub, "to_dict"):
        try:
            data = stripe_sub.to_dict()
        except Exception:
            data = dict(stripe_sub)
    elif isinstance(stripe_sub, dict):
        data = stripe_sub
    else:
        try:
            data = dict(stripe_sub)
        except Exception:
            return None

    metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
    from app.routers.webhooks.stripe import (
        _licensed_base_price_id,
        _normalize_subscription_status,
        _resolve_plan_code,
    )

    now = datetime.now(timezone.utc).isoformat()
    period_end = (
        datetime.fromtimestamp(int(data["current_period_end"]), tz=timezone.utc).isoformat()
        if data.get("current_period_end")
        else (subscription_row or {}).get("current_period_end")
    )
    sub_status = _normalize_subscription_status(data.get("status"))

    # Deleted/canceled Stripe subs must write a complete terminal state — never leave
    # a paid plan_code + active-looking local rows (or resurrect them from items).
    if sub_status == "canceled":
        org_billing_payload = {
            "org_id": org_id,
            "plan_code": DEFAULT_PLAN_CODE,
            "stripe_subscription_id": None,
            "stripe_customer_id": data.get("customer")
            or (subscription_row or {}).get("stripe_customer_id"),
            "stripe_price_id": None,
            "billing_status": "cancelled",
            "cancel_at_period_end": False,
            "current_period_end": period_end,
            "updated_at": now,
        }
        try:
            client.table("subscriptions").update(
                {
                    "tier": DEFAULT_PLAN_CODE,
                    "status": "canceled",
                    "stripe_subscription_id": None,
                    "current_period_end": period_end,
                    "updated_at": now,
                }
            ).eq("org_id", org_id).execute()
            client.table("org_billing").upsert(org_billing_payload, on_conflict="org_id").execute()
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "stripe reconcile cancel upsert failed org_id=%s error=%s",
                org_id,
                exc,
            )
            return None
        return DEFAULT_PLAN_CODE

    plan_code = _resolve_plan_code(settings, data, metadata)
    if not plan_code:
        return None
    price_id = _licensed_base_price_id(data)

    billing_status = (
        "active"
        if data.get("status") in {None, "active", "trialing"}
        else normalize_billing_status(str(data.get("status") or "active"))
    )
    org_billing_payload: dict = {
        "org_id": org_id,
        "plan_code": plan_code,
        "stripe_subscription_id": sub_id,
        "stripe_customer_id": data.get("customer") or (subscription_row or {}).get("stripe_customer_id"),
        "billing_status": billing_status,
        "current_period_end": period_end,
        "updated_at": now,
    }
    if price_id:
        org_billing_payload["stripe_price_id"] = price_id
    try:
        client.table("subscriptions").update(
            {
                "tier": plan_code,
                "status": sub_status or (subscription_row or {}).get("status") or "active",
                "current_period_end": period_end,
                "updated_at": now,
            }
        ).eq("org_id", org_id).execute()
        client.table("org_billing").upsert(org_billing_payload, on_conflict="org_id").execute()
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "stripe reconcile upsert failed org_id=%s plan=%s price=%s error=%s",
            org_id,
            plan_code,
            price_id,
            exc,
        )
        return None
    return plan_code


def _weekly_workflow_totals(client, org_id: str, period_start_iso: str) -> list[int]:
    usage_rows = (
        client.table("usage_records")
        .select("metric_type, quantity, recorded_at")
        .eq("org_id", org_id)
        .gte("recorded_at", period_start_iso)
        .execute()
    )
    buckets: dict[int, int] = {0: 0, 1: 0, 2: 0, 3: 0}
    start = datetime.fromisoformat(period_start_iso.replace("Z", "+00:00"))
    for row in usage_rows.data or []:
        if str(row.get("metric_type") or "") != "workflow_runs":
            continue
        recorded = str(row.get("recorded_at") or period_start_iso)
        try:
            ts = datetime.fromisoformat(recorded.replace("Z", "+00:00"))
        except ValueError:
            ts = start
        week_index = min(3, max(0, int((ts - start).days // 7)))
        buckets[week_index] = buckets.get(week_index, 0) + int(row.get("quantity") or 0)
    return [buckets[i] for i in range(4)]


def _map_usage_for_billing_status(usage_payload: dict, *, weekly_totals: list[int] | None = None) -> dict:
    period_start = str(usage_payload.get("period_start") or datetime.now(timezone.utc).isoformat())
    tier = usage_payload.get("tier")
    totals = usage_payload.get("totals") or {}
    plan = usage_payload.get("plan") or {}
    mapped = {
        "period_start": period_start,
        "tier": tier,
        "totals": {
            "outputs": int(totals.get("outputs") or 0),
            "workflow_runs": int(totals.get("workflow_runs") or 0),
            "api_calls": int(totals.get("api_calls") or 0),
            "ai_tokens": int(totals.get("ai_tokens") or 0),
            "research_lookups": int(totals.get("research_lookups") or 0),
            "voice_minutes": int(totals.get("voice_minutes") or 0),
        },
        "included_outputs": usage_payload.get("included_outputs"),
        "workflow_runs_included": int(
            usage_payload.get("workflow_runs_included")
            or plan.get("workflow_runs_included")
            or 0
        ),
        "ai_credits_included": int(
            usage_payload.get("ai_credits_included")
            or plan.get("ai_credits_included")
            or 0
        ),
        "weekly_totals": weekly_totals or [],
        "overage_outputs": int(usage_payload.get("overage_outputs") or 0),
        "overage_cost_usd": float(usage_payload.get("overage_cost_usd") or 0),
        "output_overage_rate_usd": float(usage_payload.get("output_overage_rate_usd") or 0),
        "included_research_lookups": int(usage_payload.get("included_research_lookups") or 0),
        "remaining_research_lookups": int(usage_payload.get("remaining_research_lookups") or 0),
        "overage_research_lookups": int(usage_payload.get("overage_research_lookups") or 0),
        "overage_research_cost_usd": float(usage_payload.get("overage_research_cost_usd") or 0),
        "research_lookup_overage_rate_usd": float(usage_payload.get("research_lookup_overage_rate_usd") or 0),
        "internet_research_enabled": bool(usage_payload.get("internet_research_enabled")),
        "research_lookups_billing_visible": bool(usage_payload.get("research_lookups_billing_visible")),
        "included_voice_minutes": int(usage_payload.get("included_voice_minutes") or 0),
        "remaining_voice_minutes": int(usage_payload.get("remaining_voice_minutes") or 0),
        "overage_voice_minutes": int(usage_payload.get("overage_voice_minutes") or 0),
        "overage_voice_cost_usd": float(usage_payload.get("overage_voice_cost_usd") or 0),
        "voice_minute_overage_rate_usd": float(usage_payload.get("voice_minute_overage_rate_usd") or 0),
        "voice_minutes_billing_visible": bool(usage_payload.get("voice_minutes_billing_visible")),
    }
    return mapped
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
    model_config = ConfigDict(populate_by_name=True)
    plan_code: str | None = Field(default=None, alias="planCode")
    billing_interval: str | None = Field(default=None, alias="billingInterval")
    price_id: str | None = Field(default=None, alias="price_id")
    quantity: int | None = Field(default=1, ge=1)


class PublicCheckoutRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    plan_code: str | None = Field(default=None, alias="planCode")
    billing_interval: str | None = Field(default=None, alias="billingInterval")
    price_id: str | None = Field(default=None, alias="price_id")
    email: EmailStr
    company_name: str | None = Field(default=None, alias="companyName")
    org_id: str | None = Field(default=None, alias="orgId")
    user_id: str | None = Field(default=None, alias="userId")


class SeatsRequest(BaseModel):
    quantity: int = Field(..., ge=1)


class CancelRequest(BaseModel):
    at_period_end: bool = Field(default=True)


def _resolve_org_id_from_checkout_metadata(client, metadata: dict) -> str | None:
    return resolve_org_id_from_checkout_metadata(client, metadata)


def _usage_from_records(client, org_id: str, tier: str | None, *, settings: Settings | None = None) -> dict:
    from app.billing.plan_rates import (
        included_ai_credits_for_plan,
        included_outputs_for_plan,
        included_workflow_runs_for_plan,
        overage_usd_per_output,
    )
    from app.billing.usage_records_summary import summarize_usage_records_billing

    try:
        return summarize_usage_records_billing(client, org_id, tier=tier, settings=settings)
    except RuntimeError:
        now = datetime.now(timezone.utc)
        period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        resolved_tier = str(tier or "free").strip().lower()
        return {
            "period_start": period_start.isoformat(),
            "tier": resolved_tier,
            "totals": {"outputs": 0, "workflow_runs": 0, "api_calls": 0, "ai_tokens": 0, "research_lookups": 0},
            "included_outputs": included_outputs_for_plan(None, plan_code=resolved_tier),
            "workflow_runs_included": included_workflow_runs_for_plan(None, plan_code=resolved_tier),
            "ai_credits_included": included_ai_credits_for_plan(None, plan_code=resolved_tier),
            "overage_outputs": 0,
            "overage_cost_usd": 0.0,
            "output_overage_rate_usd": overage_usd_per_output(None),
            "included_research_lookups": 0,
            "remaining_research_lookups": 0,
            "overage_research_lookups": 0,
            "overage_research_cost_usd": 0.0,
            "research_lookup_overage_rate_usd": 0.35,
            "internet_research_enabled": bool(settings and settings.internet_research_enabled),
            "research_lookups_billing_visible": False,
            "plan": {},
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
    billing_row = get_org_billing(client, org_id) or {}
    billing_status = normalize_billing_status(billing_row.get("billing_status"))
    sub_resp = client.table("subscriptions").select("*").eq("org_id", org_id).limit(1).execute()
    sub_err = getattr(sub_resp, "error", None)
    if sub_err:
        raise HTTPException(status_code=500, detail=str(sub_err))
    subscription_row = (sub_resp.data or [None])[0]
    if subscription_row is None:
        # Never invent an active Trial for orgs already cancelled in org_billing —
        # that paints "Node Plan / Trial" on Billing & Plan after real cancellation.
        if billing_status == "cancelled":
            seed = {
                "org_id": org_id,
                "tier": str(billing_row.get("plan_code") or DEFAULT_PLAN_CODE).strip().lower()
                or DEFAULT_PLAN_CODE,
                "status": "canceled",
                "seat_count": 1,
                "lite_seats": 0,
                "stripe_customer_id": billing_row.get("stripe_customer_id"),
                "stripe_subscription_id": billing_row.get("stripe_subscription_id"),
            }
            insert_resp = client.table("subscriptions").insert(seed).execute()
            subscription_row = (insert_resp.data or [seed])[0]
        else:
            seed = {
                "org_id": org_id,
                "tier": "free",
                "status": "trialing",
                "seat_count": 1,
                "lite_seats": 0,
            }
            insert_resp = client.table("subscriptions").insert(seed).execute()
            subscription_row = (insert_resp.data or [seed])[0]

    canonical_tier = _canonical_plan_code(client, org_id, subscription_row)
    sub_tier = str((subscription_row or {}).get("tier") or "").strip().lower()
    billing_tier = str(billing_row.get("plan_code") or "").strip().lower()
    # Always reconcile from Stripe when a subscription id exists. Prior logic only
    # ran for node/free or tier mismatch, which left stripe_price_id stuck on Node
    # after a Command upgrade while plan_code already said command.
    if (subscription_row or {}).get("stripe_subscription_id") and settings.stripe_secret_key:
        repaired = _reconcile_plan_from_stripe(client, settings, org_id, subscription_row)
        if repaired:
            canonical_tier = repaired
            refreshed = client.table("subscriptions").select("*").eq("org_id", org_id).limit(1).execute()
            subscription_row = (refreshed.data or [subscription_row])[0]
            billing_row = get_org_billing(client, org_id) or billing_row
            billing_status = normalize_billing_status(billing_row.get("billing_status"))
    elif (subscription_row or {}).get("stripe_subscription_id") and (
        canonical_tier in {"node", "free"} or sub_tier != billing_tier or not billing_tier
    ):
        # No Stripe key locally: still surface the dual-row mismatch for ops logs.
        logger.warning(
            "billing overview skip stripe reconcile (no key) org_id=%s billing=%s sub=%s",
            org_id,
            billing_tier,
            sub_tier,
        )

    # Keep subscriptions.tier aligned with org_billing so UI + usage share one plan.
    if subscription_row and str(subscription_row.get("tier") or "").strip().lower() != canonical_tier:
        try:
            client.table("subscriptions").update(
                {"tier": canonical_tier, "updated_at": datetime.now(timezone.utc).isoformat()}
            ).eq("org_id", org_id).execute()
            subscription_row = {**(subscription_row or {}), "tier": canonical_tier}
        except Exception:
            subscription_row = {**(subscription_row or {}), "tier": canonical_tier}

    # org_billing.billing_status is authoritative for cancel — do not let a missing
    # or stale subscriptions.status invent Active/Trial on the Billing page.
    if billing_status == "cancelled" and subscription_row:
        if str(subscription_row.get("status") or "").strip().lower() != "canceled":
            try:
                client.table("subscriptions").update(
                    {
                        "status": "canceled",
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    }
                ).eq("org_id", org_id).execute()
            except Exception:
                pass
            subscription_row = {**(subscription_row or {}), "status": "canceled"}

    subscription = _normalize_subscription(subscription_row, org_id, tier=canonical_tier)
    if billing_status == "cancelled":
        subscription["status"] = "canceled"
        subscription["cancel_at_period_end"] = False
    usage = _usage_from_records(client, org_id, canonical_tier, settings=settings)
    plan = get_plan_for_org(client, org_id)
    usage["plan"] = plan
    usage["tier"] = str(plan.get("code") or canonical_tier)
    period_start = str(usage.get("period_start") or datetime.now(timezone.utc).isoformat())
    weekly_totals = _weekly_workflow_totals(client, org_id, period_start)
    invoices, payment_methods = _fetch_invoices_and_payment_methods(
        settings=settings,
        customer_id=(subscription_row or {}).get("stripe_customer_id")
        or billing_row.get("stripe_customer_id"),
    )
    return {
        "subscription": subscription,
        "billing_status": billing_status,
        "usage": _map_usage_for_billing_status(usage, weekly_totals=weekly_totals),
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
    billing_status = normalize_billing_status(billing.get("billing_status"))
    plan_code = (billing.get("plan_code") or DEFAULT_PLAN_CODE).strip().lower()
    trial_ends_at = billing.get("current_period_end")
    if billing_status == "trialing" and not trial_ends_at:
        org_row = (
            client.table("organizations")
            .select("settings")
            .eq("id", org_id)
            .limit(1)
            .execute()
            .data
            or []
        )
        if org_row:
            org_settings = org_row[0].get("settings") or {}
            billing_settings = org_settings.get("billing") if isinstance(org_settings, dict) else {}
            if isinstance(billing_settings, dict):
                trial_ends_at = billing_settings.get("trial_ends_at")
    from app.billing.entitlement_service import get_org_billing_state

    billing_state = get_org_billing_state(client, org_id)
    if billing_state["is_blocked"]:
        reason = (
            "trial_expired"
            if billing_state["status"] == "trial_expired"
            else "payment_past_due"
            if billing_state["status"] == "past_due"
            else "subscription_cancelled"
        )
        access = {
            "can_access_app": False,
            "requires_upgrade": True,
            "upgrade_reason": reason,
        }
    else:
        access = compute_app_access(
            billing_status,
            trial_ends_at=trial_ends_at,
            plan_code=plan_code,
        )
    return {
        "plan": plan,
        "basePlan": base_plan,
        "overridesActive": overrides_active(overrides),
        "overrides": overrides or {},
        "billingStatus": billing_status,
        "planCode": plan_code,
        "billingKnown": True,
        "canAccessApp": access["can_access_app"],
        "requiresUpgrade": access["requires_upgrade"],
        "upgradeReason": access["upgrade_reason"],
        "trialEndsAt": trial_ends_at,
        "billingState": billing_state.get("status"),
        "trialExpired": billing_state.get("status") == "trial_expired",
        "daysRemainingInTrial": billing_state.get("days_remaining_in_trial"),
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
    member: Annotated[tuple, Depends(require_org_member)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    current_user, org_id, _role = member
    plan_code = (body.plan_code or "").strip().lower() or None
    billing_interval = (body.billing_interval or "").strip().lower() or None
    price_id = (body.price_id or "").strip() or None
    if not price_id and plan_code:
        price_id = price_id_for_plan(settings, plan_code, billing_interval=billing_interval)
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
    success_url = f"{app_url}/settings/billing?status=success"
    cancel_url = f"{app_url}/settings/billing?status=cancelled"
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    billing = get_org_billing(client, org_id)
    customer_id = billing.get("stripe_customer_id") if billing else None
    if not customer_id:
        try:
            customer_id = _create_stripe_customer(
                settings, client, org_id, current_user["user_id"], plan_code
            )
        except stripe.error.StripeError as exc:
            _raise_stripe_http_error(exc)
    try:
        session = create_checkout_session(
            settings=settings,
            customer_id=customer_id,
            price_id=price_id,
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                "org_id": org_id,
                "plan_code": plan_code,
                "billing_interval": billing_interval or "monthly",
                "user_id": current_user["user_id"],
            },
        )
    except stripe.error.StripeError as exc:
        if customer_id and _stripe_customer_missing(exc):
            customer_id = _create_stripe_customer(
                settings, client, org_id, current_user["user_id"], plan_code
            )
            try:
                session = create_checkout_session(
                    settings=settings,
                    customer_id=customer_id,
                    price_id=price_id,
                    success_url=success_url,
                    cancel_url=cancel_url,
                    metadata={
                        "org_id": org_id,
                        "plan_code": plan_code,
                        "billing_interval": billing_interval or "monthly",
                        "user_id": current_user["user_id"],
                    },
                )
            except stripe.error.StripeError as retry_exc:
                _raise_stripe_http_error(retry_exc)
        else:
            _raise_stripe_http_error(exc)
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=current_user["user_id"],
        action="billing.checkout.created",
        resource_type="org_billing",
        resource_id=str(org_id),
        metadata={"plan_code": plan_code, "billing_interval": billing_interval or "monthly"},
    )
    return {"url": session.url, "checkout_url": session.url}


@router.post("/subscribe")
async def create_subscription_payment(
    body: CheckoutRequest,
    member: Annotated[tuple, Depends(require_org_member)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """Create an incomplete Stripe subscription and return Payment Element client_secret."""
    current_user, org_id, _role = member
    plan_code = (body.plan_code or "").strip().lower() or None
    billing_interval = (body.billing_interval or "").strip().lower() or None
    price_id = (body.price_id or "").strip() or None
    if not price_id and plan_code:
        price_id = price_id_for_plan(settings, plan_code, billing_interval=billing_interval)
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

    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    billing = get_org_billing(client, org_id)
    customer_id = billing.get("stripe_customer_id") if billing else None
    if not customer_id:
        try:
            customer_id = _create_stripe_customer(
                settings, client, org_id, current_user["user_id"], plan_code
            )
        except stripe.error.StripeError as exc:
            _raise_stripe_http_error(exc)

    metadata = {
        "org_id": org_id,
        "plan_code": plan_code,
        "billing_interval": billing_interval or "monthly",
    }
    quantity = body.quantity or 1

    try:
        result = create_subscription_for_payment_element(
            settings=settings,
            customer_id=customer_id,
            price_id=price_id,
            metadata=metadata,
            quantity=quantity,
        )
    except stripe.error.StripeError as exc:
        if customer_id and _stripe_customer_missing(exc):
            customer_id = _create_stripe_customer(
                settings, client, org_id, current_user["user_id"], plan_code
            )
            try:
                result = create_subscription_for_payment_element(
                    settings=settings,
                    customer_id=customer_id,
                    price_id=price_id,
                    metadata=metadata,
                    quantity=quantity,
                )
            except stripe.error.StripeError as retry_exc:
                _raise_stripe_http_error(retry_exc)
        else:
            _raise_stripe_http_error(exc)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=error_detail(str(exc), "STRIPE_ERROR"),
        ) from exc

    write_audit_event(
        client,
        org_id=org_id,
        actor_id=current_user["user_id"],
        action="billing.subscribe.created",
        resource_type="org_billing",
        resource_id=str(org_id),
        metadata={
            "plan_code": plan_code,
            "billing_interval": billing_interval or "monthly",
            "subscription_id": result["subscription_id"],
        },
    )
    return {
        "client_secret": result["client_secret"],
        "subscription_id": result["subscription_id"],
        "customer_id": result["customer_id"],
        "subscription_status": result["subscription_status"],
    }


@router.post("/checkout/public")
async def create_public_checkout(
    body: PublicCheckoutRequest,
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    plan_code = (body.plan_code or "").strip().lower() or None
    billing_interval = (body.billing_interval or "").strip().lower() or None
    price_id = (body.price_id or "").strip() or None
    if not price_id and plan_code:
        price_id = price_id_for_plan(settings, plan_code, billing_interval=billing_interval)
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
    success_url = f"{app_url}/get-started?checkout=success"
    cancel_url = f"{app_url}/get-started?checkout=cancelled"

    from stripe import Customer

    init_stripe(settings)
    try:
        customer = Customer.create(
            email=str(body.email).strip().lower(),
            metadata={
                "signup_flow": "public_checkout",
                "plan_code": plan_code or "free",
                "billing_interval": billing_interval or "monthly",
                "company_name": (body.company_name or "").strip(),
                "checkout_email": str(body.email).strip().lower(),
                **({"org_id": str(body.org_id).strip()} if body.org_id else {}),
                **({"user_id": str(body.user_id).strip()} if body.user_id else {}),
            },
        )
        session = create_checkout_session(
            settings=settings,
            customer_id=customer["id"],
            price_id=price_id,
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                "signup_flow": "public_checkout",
                "plan_code": plan_code or "free",
                "billing_interval": billing_interval or "monthly",
                "checkout_email": str(body.email).strip().lower(),
                "company_name": (body.company_name or "").strip(),
                **({"org_id": str(body.org_id).strip()} if body.org_id else {}),
                **({"user_id": str(body.user_id).strip()} if body.user_id else {}),
            },
        )
    except stripe.error.StripeError as exc:
        _raise_stripe_http_error(exc)
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
    resp_err = getattr(response, "error", None)
    if resp_err:
        raise HTTPException(status_code=500, detail=str(resp_err))
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
    resp_err = getattr(response, "error", None)
    if resp_err:
        raise HTTPException(status_code=500, detail=str(resp_err))
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
    resp_err = getattr(response, "error", None)
    if resp_err:
        raise HTTPException(status_code=500, detail=str(resp_err))
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
    """Legacy Stripe webhook URL (/api/billing/webhook) — canonical handler lives in webhooks.stripe."""
    from app.routers.webhooks.stripe import stripe_webhook

    return await stripe_webhook(request, settings)

# Deploy gate touch for Command plan billing fix (9b1d748c)
