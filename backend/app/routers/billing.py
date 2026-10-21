"""Billing API — subscriptions, checkout, usage overview, cancel/reactivate."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Literal

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from postgrest.exceptions import APIError
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from supabase import create_client
from app.core.db import shared_service_client

from app.auth.dependencies import (
    get_current_user,
    get_environment_context,
    get_org_context,
    require_capability,
    require_org_member,
    require_platform_admin,
)
from app.billing.commercial_offers import (
    checkout_offer_for_org,
    reserve_checkout_offer,
    segment_for_org,
)
from app.billing.entitlements import compute_app_access, normalize_billing_status
from app.billing.promotion_codes import (
    checkout_discount,
    checkout_response_fields,
    checkout_session_kwargs,
)
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
    billing_interval_for_plan_price,
    create_checkout_session,
    create_customer_portal,
    create_subscription_for_payment_element,
    init_stripe,
    plan_code_for_price,
    price_id_for_plan,
    unit_amount_cents_for_plan_price,
)
from app.config import Settings, get_settings
from app.core.errors import error_detail
from app.core.logging import get_logger
from app.core.org_state_cache import (
    billing_status_cache,
    cache_allowed,
    invalidate_org_state,
    org_tag,
)
from app.workflows.audit import write_audit_event
from app.billing.msp_billing import assert_not_msp_billed

logger = get_logger(__name__)
router = APIRouter(prefix="/api/billing", tags=["billing"])


def _raise_stripe_http_error(exc: stripe.error.StripeError) -> None:
    message = (
        getattr(exc, "user_message", None) or str(exc) or "Stripe request failed"
    ).strip()
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=error_detail(message, "STRIPE_ERROR"),
    ) from exc


def _stripe_customer_missing(exc: stripe.error.StripeError) -> bool:
    if not isinstance(exc, stripe.error.InvalidRequestError):
        return False
    message = (getattr(exc, "user_message", None) or str(exc) or "").lower()
    return "no such customer" in message


def _create_stripe_customer(
    settings: Settings, client, org_id: str, user_id: str, plan_code: str | None
) -> str:
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
    invalidate_org_state(org_id)
    return customer_id


# Health check endpoint to verify Stripe configuration
@router.get("/health")
def billing_health(settings: Annotated[Settings, Depends(get_settings)]):
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
    if settings.stripe_secret_key and settings.stripe_secret_key.startswith(
        ("sk_test_", "sk_live_")
    ):
        try:
            stripe.api_key = settings.stripe_secret_key
            stripe.Account.retrieve()
            stripe_connected = True
        except stripe.AuthenticationError:
            issues.append("STRIPE_SECRET_KEY is invalid (authentication failed)")
        except Exception as e:
            issues.append(f"Stripe API error: {str(e)}")

    mode = (
        "test"
        if settings.stripe_secret_key and "test" in settings.stripe_secret_key
        else "live"
    )

    def _price_tail(value: str | None) -> str | None:
        text = str(value or "").strip()
        if not text:
            return None
        return text[-8:]

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
            # Last 8 chars only — enough to confirm which Price objects are wired.
            "node_monthly_tail": _price_tail(settings.stripe_price_id_node_monthly),
            "control_monthly_tail": _price_tail(
                settings.stripe_price_id_control_monthly
            ),
            "command_monthly_tail": _price_tail(
                settings.stripe_price_id_command_monthly
            ),
        },
    }


@router.get("/webhook/health")
async def billing_webhook_health(settings: Annotated[Settings, Depends(get_settings)]):
    """Verify Stripe webhook config and idempotency table readiness."""
    from app.billing.webhook_idempotency import check_webhook_idempotency_table

    issues: list[str] = []

    if not settings.stripe_webhook_secret:
        issues.append("STRIPE_WEBHOOK_SECRET is not set")
    elif not settings.stripe_webhook_secret.startswith("whsec_"):
        issues.append(
            "STRIPE_WEBHOOK_SECRET has invalid format (should start with whsec_)"
        )

    idempotency_table = {
        "table": "stripe_webhook_events",
        "reachable": False,
        "error": "supabase_not_configured",
    }
    if settings.supabase_url and settings.supabase_service_role_key:
        client = shared_service_client(settings, create_client)
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


def _normalize_subscription(
    row: dict | None, org_id: str, *, tier: str | None = None
) -> dict:
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
        "seat_count": _safe_int(row.get("seat_count"), 1),
        "lite_seats": _safe_int(row.get("lite_seats"), 0),
        "current_period_start": (
            row.get("current_period_start") or datetime.now(timezone.utc).isoformat()
        ),
        "current_period_end": (
            row.get("current_period_end") or datetime.now(timezone.utc).isoformat()
        ),
        "cancel_at_period_end": bool(row.get("cancel_at_period_end") or False),
        "meson_addons": meson_addons,
        "stripe_price_id": row.get("stripe_price_id"),
        "plan_unit_amount_cents": row.get("plan_unit_amount_cents"),
        "plan_billing_interval": row.get("plan_billing_interval"),
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
        logger.warning(
            "stripe reconcile retrieve failed org_id=%s error=%s", org_id, exc
        )
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
    remote_period_end = (
        data.get("trial_end")
        if data.get("status") == "trialing"
        else data.get("current_period_end")
    )
    period_end = (
        datetime.fromtimestamp(
            int(remote_period_end), tz=timezone.utc
        ).isoformat()
        if remote_period_end
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
            client.table("org_billing").upsert(
                org_billing_payload, on_conflict="org_id"
            ).execute()
        except Exception as exc:  # noqa: BLE001
            invalidate_org_state(org_id)
            logger.error(
                "stripe reconcile cancel upsert failed org_id=%s error=%s",
                org_id,
                exc,
            )
            return None
        invalidate_org_state(org_id)
        return DEFAULT_PLAN_CODE

    plan_code = _resolve_plan_code(settings, data, metadata)
    if not plan_code:
        return None
    price_id = _licensed_base_price_id(data)

    billing_status = (
        "active"
        if data.get("status") in {None, "active"}
        else normalize_billing_status(str(data.get("status") or "active"))
    )
    cancel_at_period_end = bool(data.get("cancel_at_period_end") or False)
    org_billing_payload: dict = {
        "org_id": org_id,
        "plan_code": plan_code,
        "stripe_subscription_id": sub_id,
        "stripe_customer_id": data.get("customer")
        or (subscription_row or {}).get("stripe_customer_id"),
        "billing_status": billing_status,
        "current_period_end": period_end,
        "cancel_at_period_end": cancel_at_period_end,
        "updated_at": now,
    }
    if price_id:
        org_billing_payload["stripe_price_id"] = price_id
    try:
        client.table("subscriptions").update(
            {
                "tier": plan_code,
                "status": sub_status
                or (subscription_row or {}).get("status")
                or "active",
                "current_period_end": period_end,
                "updated_at": now,
            }
        ).eq("org_id", org_id).execute()
        client.table("org_billing").upsert(
            org_billing_payload, on_conflict="org_id"
        ).execute()
    except Exception as exc:  # noqa: BLE001
        invalidate_org_state(org_id)
        logger.error(
            "stripe reconcile upsert failed org_id=%s plan=%s price=%s error=%s",
            org_id,
            plan_code,
            price_id,
            exc,
        )
        return None
    invalidate_org_state(org_id)
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


def _map_usage_for_billing_status(
    usage_payload: dict, *, weekly_totals: list[int] | None = None
) -> dict:
    period_start = str(
        usage_payload.get("period_start") or datetime.now(timezone.utc).isoformat()
    )
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
        "output_overage_rate_usd": float(
            usage_payload.get("output_overage_rate_usd") or 0
        ),
        "included_research_lookups": int(
            usage_payload.get("included_research_lookups") or 0
        ),
        "remaining_research_lookups": int(
            usage_payload.get("remaining_research_lookups") or 0
        ),
        "overage_research_lookups": int(
            usage_payload.get("overage_research_lookups") or 0
        ),
        "overage_research_cost_usd": float(
            usage_payload.get("overage_research_cost_usd") or 0
        ),
        "research_lookup_overage_rate_usd": float(
            usage_payload.get("research_lookup_overage_rate_usd") or 0
        ),
        "internet_research_enabled": bool(
            usage_payload.get("internet_research_enabled")
        ),
        "research_lookups_billing_visible": bool(
            usage_payload.get("research_lookups_billing_visible")
        ),
        "included_voice_minutes": int(usage_payload.get("included_voice_minutes") or 0),
        "remaining_voice_minutes": int(
            usage_payload.get("remaining_voice_minutes") or 0
        ),
        "overage_voice_minutes": int(usage_payload.get("overage_voice_minutes") or 0),
        "overage_voice_cost_usd": float(
            usage_payload.get("overage_voice_cost_usd") or 0
        ),
        "voice_minute_overage_rate_usd": float(
            usage_payload.get("voice_minute_overage_rate_usd") or 0
        ),
        "voice_minutes_billing_visible": bool(
            usage_payload.get("voice_minutes_billing_visible")
        ),
    }
    return mapped


@router.get("/plans")
def list_billing_plans(
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization context required",
        )
    client = get_supabase_client(settings)
    plans = list(get_billing_plans(client).values())
    return {"plans": plans}


class CheckoutRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    plan_code: str | None = Field(default=None, alias="planCode")
    billing_interval: str | None = Field(default=None, alias="billingInterval")
    price_id: str | None = Field(default=None, alias="price_id")
    quantity: int | None = Field(default=1, ge=1)
    promotion_code: str | None = Field(default=None, alias="promotionCode", max_length=64)


class PublicCheckoutRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    plan_code: str | None = Field(default=None, alias="planCode")
    billing_interval: str | None = Field(default=None, alias="billingInterval")
    price_id: str | None = Field(default=None, alias="price_id")
    email: EmailStr
    company_name: str | None = Field(default=None, alias="companyName")
    promotion_code: str | None = Field(default=None, alias="promotionCode", max_length=64)
    org_id: str | None = Field(default=None, alias="orgId")
    user_id: str | None = Field(default=None, alias="userId")


class SeatsRequest(BaseModel):
    quantity: int = Field(..., ge=1)


class CancelRequest(BaseModel):
    at_period_end: bool = Field(default=True)


def _safe_int(value: object, default: int = 0) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _normalize_subscription_tier(plan_code: str | None) -> str:
    tier = str(plan_code or "free").strip().lower()
    if tier in {"free", "node", "control", "command"}:
        return tier
    if tier == "starter":
        return "node"
    if tier == "growth":
        return "control"
    if tier in {"scale", "enterprise"}:
        return "command"
    return "free"


def _supabase_response_error(response: object) -> str | None:
    err = getattr(response, "error", None)
    if err:
        return str(err)
    return None


def _execute_billing_query(query: object, *, action: str):
    """Run PostgREST query; supabase-py v2 raises APIError instead of response.error."""
    try:
        return query.execute()
    except APIError as exc:
        logger.error("billing supabase %s failed err=%s", action, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_detail(str(exc), "DATABASE_ERROR"),
        ) from exc


def _stripe_cancel_is_soft_fail(exc: Exception) -> bool:
    msg = (getattr(exc, "user_message", None) or str(exc) or "").lower()
    return any(
        token in msg
        for token in (
            "no such subscription",
            "does not exist",
            "already canceled",
            "already cancelled",
            "canceled subscription",
            "cancelled subscription",
        )
    )


def _persist_subscription_status(
    client,
    org_id: str,
    *,
    status: str,
    billing: dict,
    sub_row: dict | None,
    now: str,
) -> dict | None:
    tier = _normalize_subscription_tier(
        billing.get("plan_code") or (sub_row or {}).get("tier")
    )
    payload: dict = {
        "org_id": org_id,
        "status": status,
        "tier": tier,
        "updated_at": now,
    }
    stripe_sub = billing.get("stripe_subscription_id") or (sub_row or {}).get(
        "stripe_subscription_id"
    )
    if stripe_sub:
        payload["stripe_subscription_id"] = stripe_sub
    stripe_cus = billing.get("stripe_customer_id") or (sub_row or {}).get(
        "stripe_customer_id"
    )
    if stripe_cus:
        payload["stripe_customer_id"] = stripe_cus
    period_end = billing.get("current_period_end") or (sub_row or {}).get(
        "current_period_end"
    )
    if period_end:
        payload["current_period_end"] = period_end

    try:
        _execute_billing_query(
            client.table("subscriptions").upsert(payload, on_conflict="org_id"),
            action="subscriptions.upsert",
        )
    finally:
        invalidate_org_state(org_id)
    response = _execute_billing_query(
        client.table("subscriptions").select("*").eq("org_id", org_id).limit(1),
        action="subscriptions.select",
    )
    err = _supabase_response_error(response)
    if err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_detail(err, "DATABASE_ERROR"),
        )
    return (response.data or [None])[0]


def _resolve_org_id_from_checkout_metadata(client, metadata: dict) -> str | None:
    return resolve_org_id_from_checkout_metadata(client, metadata)


def _usage_from_records(
    client, org_id: str, tier: str | None, *, settings: Settings | None = None
) -> dict:
    from app.billing.plan_rates import (
        included_ai_credits_for_plan,
        included_outputs_for_plan,
        included_workflow_runs_for_plan,
        overage_usd_per_output,
    )
    from app.billing.usage_records_summary import summarize_usage_records_billing

    try:
        return summarize_usage_records_billing(
            client, org_id, tier=tier, settings=settings
        )
    except RuntimeError:
        now = datetime.now(timezone.utc)
        period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        resolved_tier = str(tier or "free").strip().lower()
        return {
            "period_start": period_start.isoformat(),
            "tier": resolved_tier,
            "totals": {
                "outputs": 0,
                "workflow_runs": 0,
                "api_calls": 0,
                "ai_tokens": 0,
                "research_lookups": 0,
            },
            "included_outputs": included_outputs_for_plan(
                None, plan_code=resolved_tier
            ),
            "workflow_runs_included": included_workflow_runs_for_plan(
                None, plan_code=resolved_tier
            ),
            "ai_credits_included": included_ai_credits_for_plan(
                None, plan_code=resolved_tier
            ),
            "overage_outputs": 0,
            "overage_cost_usd": 0.0,
            "output_overage_rate_usd": overage_usd_per_output(None),
            "included_research_lookups": 0,
            "remaining_research_lookups": 0,
            "overage_research_lookups": 0,
            "overage_research_cost_usd": 0.0,
            "research_lookup_overage_rate_usd": 0.35,
            "internet_research_enabled": bool(
                settings and settings.internet_research_enabled
            ),
            "research_lookups_billing_visible": False,
            "plan": {},
        }


def _fetch_invoices_and_payment_methods(
    settings: Settings, customer_id: str | None
) -> tuple[list[dict], list[dict]]:
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
        stripe_invoices = stripe.Invoice.list(customer=customer_id, limit=100)
        for invoice in stripe_invoices.data:
            invoices.append(
                {
                    "id": invoice.get("id"),
                    "stripe_invoice_id": invoice.get("id"),
                    "amount_cents": int(
                        invoice.get("amount_paid") or invoice.get("amount_due") or 0
                    ),
                    "currency": str(invoice.get("currency") or "usd"),
                    "status": str(invoice.get("status") or "open"),
                    "period_start": _ts_to_iso(
                        invoice.get("period_start") or invoice.get("created")
                    ),
                    "period_end": _ts_to_iso(
                        invoice.get("period_end") or invoice.get("created")
                    ),
                    "pdf_url": invoice.get("invoice_pdf"),
                    # Display fields for the Invoices card: Stripe's invoice
                    # number and its hosted page (both null until finalized).
                    "number": invoice.get("number"),
                    "hosted_invoice_url": invoice.get("hosted_invoice_url"),
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
            # Only display-safe card fields leave the backend: brand, last 4,
            # expiry. Never invent digits when Stripe has none.
            payment_methods.append(
                {
                    "id": method.get("id"),
                    "type": method.get("type") or "card",
                    "brand": card.get("brand") or None,
                    "last4": card.get("last4") or None,
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
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization context required",
        )
    client = shared_service_client(settings, create_client)
    billing_row = get_org_billing(client, org_id) or {}
    billing_status = normalize_billing_status(billing_row.get("billing_status"))
    sub_resp = (
        client.table("subscriptions")
        .select("*")
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    )
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
                "tier": str(billing_row.get("plan_code") or DEFAULT_PLAN_CODE)
                .strip()
                .lower()
                or DEFAULT_PLAN_CODE,
                "status": "canceled",
                "seat_count": 1,
                "lite_seats": 0,
                "stripe_customer_id": billing_row.get("stripe_customer_id"),
                "stripe_subscription_id": billing_row.get("stripe_subscription_id"),
            }
            insert_resp = client.table("subscriptions").insert(seed).execute()
            invalidate_org_state(org_id)
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
            invalidate_org_state(org_id)
            subscription_row = (insert_resp.data or [seed])[0]

    canonical_tier = _canonical_plan_code(client, org_id, subscription_row)
    sub_tier = str((subscription_row or {}).get("tier") or "").strip().lower()
    billing_tier = str(billing_row.get("plan_code") or "").strip().lower()
    # Always reconcile from Stripe when a subscription id exists. Prior logic only
    # ran for node/free or tier mismatch, which left stripe_price_id stuck on Node
    # after a Command upgrade while plan_code already said command.
    if (subscription_row or {}).get(
        "stripe_subscription_id"
    ) and settings.stripe_secret_key:
        repaired = _reconcile_plan_from_stripe(
            client, settings, org_id, subscription_row
        )
        if repaired:
            canonical_tier = repaired
            refreshed = (
                client.table("subscriptions")
                .select("*")
                .eq("org_id", org_id)
                .limit(1)
                .execute()
            )
            subscription_row = (refreshed.data or [subscription_row])[0]
            billing_row = get_org_billing(client, org_id) or billing_row
            billing_status = normalize_billing_status(billing_row.get("billing_status"))
    elif (subscription_row or {}).get("stripe_subscription_id") and (
        canonical_tier in {"node", "free"}
        or sub_tier != billing_tier
        or not billing_tier
    ):
        # No Stripe key locally: still surface the dual-row mismatch for ops logs.
        logger.warning(
            "billing overview skip stripe reconcile (no key) org_id=%s billing=%s sub=%s",
            org_id,
            billing_tier,
            sub_tier,
        )

    # Keep subscriptions.tier aligned with org_billing so UI + usage share one plan.
    if (
        subscription_row
        and str(subscription_row.get("tier") or "").strip().lower() != canonical_tier
    ):
        try:
            client.table("subscriptions").update(
                {
                    "tier": canonical_tier,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
            ).eq("org_id", org_id).execute()
            invalidate_org_state(org_id)
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
                invalidate_org_state(org_id)
            except Exception:
                pass
            subscription_row = {**(subscription_row or {}), "status": "canceled"}

    stripe_price_id = str(billing_row.get("stripe_price_id") or "").strip() or None
    plan_unit_amount_cents = unit_amount_cents_for_plan_price(stripe_price_id)
    plan_billing_interval = billing_interval_for_plan_price(stripe_price_id)
    subscription = _normalize_subscription(
        {
            **(subscription_row or {}),
            "stripe_price_id": stripe_price_id,
            "plan_unit_amount_cents": plan_unit_amount_cents,
            "plan_billing_interval": plan_billing_interval,
            "cancel_at_period_end": bool(
                billing_row.get("cancel_at_period_end") or False
            ),
        },
        org_id,
        tier=canonical_tier,
    )
    if billing_status == "cancelled":
        subscription["status"] = "canceled"
        subscription["cancel_at_period_end"] = False
    usage = _usage_from_records(client, org_id, canonical_tier, settings=settings)
    plan = get_plan_for_org(client, org_id)
    usage["plan"] = plan
    usage["tier"] = str(plan.get("code") or canonical_tier)
    period_start = str(
        usage.get("period_start") or datetime.now(timezone.utc).isoformat()
    )
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
def get_billing_status(
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    environment: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization context required",
        )
    client = get_supabase_client(settings)
    cacheable = billing_status_cache.enabled and cache_allowed(client)
    cache_key = (org_id, environment)
    if cacheable:
        cached = billing_status_cache.get(cache_key)
        if cached is not None:
            return cached
        cache_token = billing_status_cache.token()
    payload = _compute_billing_status(client, org_id, environment)
    if cacheable:
        billing_status_cache.set(
            cache_key, payload, tags=(org_tag(org_id),), token=cache_token
        )
    return payload


def _compute_billing_status(client, org_id: str, environment: str) -> dict:
    # Each row is read once per request and handed to the helpers (they used to
    # re-read org_billing ~4x and organizations ~3x).
    billing_row = get_org_billing(client, org_id)
    billing = billing_row or {
        "plan_code": DEFAULT_PLAN_CODE,
        "billing_status": "trialing",
    }
    base_plan = get_base_plan_for_org(client, org_id, billing=billing_row)
    overrides = get_org_billing_overrides(client, org_id)
    plan = get_plan_for_org(client, org_id, base_plan=base_plan, overrides=overrides)
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
    from app.billing.entitlement_service import load_org_settings

    org_settings = load_org_settings(client, org_id)
    trial_ends_at = billing.get("current_period_end")
    if billing_status == "trialing" and not trial_ends_at and org_settings:
        billing_settings = org_settings.get("billing")
        if isinstance(billing_settings, dict):
            trial_ends_at = billing_settings.get("trial_ends_at")
    from app.billing.entitlement_service import get_org_billing_state

    billing_state = get_org_billing_state(
        client, org_id, billing=billing_row, org_settings=org_settings
    )
    if billing_state["is_blocked"]:
        reason = (
            "trial_expired"
            if billing_state["status"] == "trial_expired"
            else (
                "payment_past_due"
                if billing_state["status"] == "past_due"
                else "subscription_cancelled"
            )
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
    stripe_price_id = str(billing.get("stripe_price_id") or "").strip() or None
    plan_unit_amount_cents = unit_amount_cents_for_plan_price(stripe_price_id)
    plan_billing_interval = billing_interval_for_plan_price(stripe_price_id)

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
        "planUnitAmountCents": plan_unit_amount_cents,
        "planBillingInterval": plan_billing_interval,
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


class CommercialCategoryRequest(BaseModel):
    org_id: str
    customer_category: Literal["external", "internal", "test", "unreviewed"]
    reason: str = Field(min_length=5, max_length=500)


class FounderOfferRequest(BaseModel):
    org_id: str
    offer_type: Literal["trial", "discount"]
    trial_days: int | None = Field(default=None, ge=1, le=90)
    percent_off: float | None = Field(default=None, gt=0, le=100)
    discount_months: int | None = Field(default=None, ge=1, le=12)
    valid_until: datetime | None = None
    max_promotion_value_cents: int = Field(ge=1, le=2147483647)
    # Classify an unreviewed org as External in the same audited step.
    classify_as_external: bool = False
    classification_reason: str | None = Field(default=None, max_length=500)


@router.get("/admin/commercial-accounts")
def list_commercial_accounts(
    _founder: Annotated[dict, Depends(require_platform_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
    offset: int = 0,
    limit: int = 200,
) -> dict:
    if offset < 0 or not 1 <= limit <= 200:
        raise HTTPException(status_code=422, detail="Invalid account page")
    client = shared_service_client(settings, create_client)
    rows = (
        client.table("organizations")
        .select("id,name")
        .order("created_at", desc=True)
        .order("id")
        .range(offset, offset + limit)
        .execute()
        .data
        or []
    )
    has_more = len(rows) > limit
    orgs = rows[:limit]
    org_ids = [str(org["id"]) for org in orgs]
    profiles = (
        client.table("org_commercial_profiles")
        .select("org_id,customer_category,classification_reason")
        .in_("org_id", org_ids)
        .execute()
        .data
        or []
        if org_ids
        else []
    )
    grants = []
    # Histories also page: an old redeemed offer must not disappear from its cohort.
    if org_ids:
        grant_offset = 0
        while True:
            page = (
                client.table("org_promotional_grants")
                .select(
                    "id,org_id,offer_type,trial_days,percent_off,discount_months,status,valid_until,redeemed_at,checkout_attempt_id"
                )
                .in_("org_id", org_ids)
                .order("id")
                .range(grant_offset, grant_offset + 499)
                .execute()
                .data
                or []
            )
            grants.extend(page)
            if len(page) < 500:
                break
            grant_offset += 500
    by_org = {str(p["org_id"]): p for p in profiles}
    grants_by_org: dict[str, list[dict]] = {}
    for grant in grants:
        grants_by_org.setdefault(str(grant["org_id"]), []).append(grant)
    return {
        "offers_enabled": settings.commercial_offers_enabled,
        "has_more": has_more,
        "next_offset": offset + len(orgs),
        "accounts": [
            {
                "org_id": str(org["id"]),
                "name": org.get("name"),
                "customer_category": by_org.get(str(org["id"]), {}).get(
                    "customer_category", "unreviewed"
                ),
                "classification_reason": by_org.get(str(org["id"]), {}).get(
                    "classification_reason"
                ),
                "offers": grants_by_org.get(str(org["id"]), []),
            }
            for org in orgs
        ],
    }


@router.get("/admin/commercial-accounts/{org_id}/stripe")
def inspect_commercial_stripe_account(
    org_id: str,
    _founder: Annotated[dict, Depends(require_platform_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    from uuid import UUID

    try:
        org_id = str(UUID(org_id))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="Invalid organization ID") from exc
    client = shared_service_client(settings, create_client)
    billing = get_org_billing(client, org_id) or {}
    customer_id = billing.get("stripe_customer_id")
    if not customer_id:
        return {
            "customer_id": None,
            "subscriptions": [],
            "source": "stripe",
            "verified_at": None,
        }
    init_stripe(settings)
    try:
        customer = stripe.Customer.retrieve(customer_id)
        if (customer.get("metadata") or {}).get("org_id") != org_id:
            raise HTTPException(
                status_code=409, detail="Stripe customer ownership needs reconciliation"
            )
        subscriptions = stripe.Subscription.list(
            customer=customer_id, status="all", limit=100
        )
        return {
            "customer_id": customer_id,
            "source": "stripe",
            "verified_at": datetime.now(timezone.utc).isoformat(),
            "has_more": bool(subscriptions.get("has_more")),
            "subscriptions": [
                {
                    "id": row["id"],
                    "status": row["status"],
                    "trial_end": row.get("trial_end"),
                    "cancel_at_period_end": row.get("cancel_at_period_end", False),
                }
                for row in subscriptions.get("data", [])
            ],
        }
    except stripe.error.StripeError as exc:
        _raise_stripe_http_error(exc)


@router.get("/admin/billing-safety")
def billing_safety_status(
    _founder: Annotated[dict, Depends(require_platform_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    client = shared_service_client(settings, create_client)
    return {
        "alerts": client.table("billing_safety_alerts")
        .select("*")
        .is_("resolved_at", "null")
        .order("last_seen_at", desc=True)
        .limit(100)
        .execute()
        .data
        or [],
        "reconciliation": client.table("billing_reconciliation_runs")
        .select("*")
        .order("started_at", desc=True)
        .limit(1)
        .execute()
        .data
        or [],
    }


@router.post("/admin/billing-reconciliation")
def reconcile_billing(
    founder: Annotated[dict, Depends(require_platform_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    from app.billing.safety import run_billing_reconciliation

    client = shared_service_client(settings, create_client)
    result = run_billing_reconciliation(
        client, settings, run_key=f"manual:{datetime.now(timezone.utc).isoformat()}"
    )
    write_audit_event(
        client,
        org_id=None,
        actor_id=founder["user_id"],
        action="billing.reconciliation.requested",
        resource_type="billing_reconciliation_runs",
        resource_id=result["run_key"],
        metadata={"status": result["status"]},
    )
    return result


@router.post("/admin/customer-segments")
def set_customer_category(
    body: CommercialCategoryRequest,
    founder: Annotated[dict, Depends(require_platform_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    from uuid import UUID

    try:
        org_id = str(UUID(body.org_id))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="Invalid organization ID") from exc
    client = shared_service_client(settings, create_client)
    if not (
        client.table("organizations")
        .select("id")
        .eq("id", org_id)
        .limit(1)
        .execute()
        .data
        or []
    ):
        raise HTTPException(status_code=404, detail="Organization not found")
    client.table("org_commercial_profiles").upsert(
        {
            "org_id": org_id,
            "customer_category": body.customer_category,
            "classification_reason": body.reason,
            "classified_by": founder["user_id"],
            "classified_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
        on_conflict="org_id",
    ).execute()
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=founder["user_id"],
        action="billing.customer_category.changed",
        resource_type="org_commercial_profiles",
        resource_id=org_id,
        metadata={"category": body.customer_category, "reason": body.reason},
    )
    return {"org_id": org_id, "customer_category": body.customer_category}


def _founder_discount_base_products(settings: Settings) -> list[str]:
    """Resolve configured licensed plan products, excluding metered add-ons.

    Restrict Stripe discounts to base plan products so 30% off a subscription
    cannot silently discount AI-credit, voice or research overages.
    """
    init_stripe(settings)
    products: set[str] = set()
    for plan in ("node", "control", "command"):
        monthly_price_id = price_id_for_plan(settings, plan, billing_interval="monthly")
        if not monthly_price_id:
            raise HTTPException(
                status_code=503, detail=f"Missing Stripe base price for {plan}"
            )
        for interval in ("monthly", "annual"):
            price_id = price_id_for_plan(settings, plan, billing_interval=interval)
            if not price_id:
                continue
            price = stripe.Price.retrieve(price_id)
            product = price.get("product")
            product_id = product.get("id") if isinstance(product, dict) else product
            if not isinstance(product_id, str) or not product_id.startswith("prod_"):
                raise HTTPException(
                    status_code=503, detail="Unable to verify Stripe base plan product"
                )
            products.add(product_id)
    if not products:
        raise HTTPException(
            status_code=503, detail="No Stripe base plan products available"
        )
    return sorted(products)


@router.post("/admin/promotional-offers")
def create_founder_offer(
    body: FounderOfferRequest,
    founder: Annotated[dict, Depends(require_platform_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    from uuid import UUID

    try:
        org_id = str(UUID(body.org_id))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="Invalid organization ID") from exc
    if not settings.commercial_offers_enabled:
        raise HTTPException(
            status_code=503, detail="Founder promotions are not yet activated"
        )
    if body.offer_type == "trial":
        if (
            body.trial_days is None
            or body.percent_off is not None
            or body.discount_months is not None
        ):
            raise HTTPException(
                status_code=422, detail="Trial offers require trial_days only"
            )
    elif (
        body.percent_off is None
        or body.discount_months is None
        or body.trial_days is not None
    ):
        raise HTTPException(
            status_code=422,
            detail="Discount offers require percent_off and discount_months",
        )
    if body.valid_until and body.valid_until.tzinfo is None:
        raise HTTPException(
            status_code=422, detail="Offer expiration requires a timezone"
        )
    if body.valid_until and body.valid_until <= datetime.now(timezone.utc):
        raise HTTPException(
            status_code=422, detail="Offer expiration must be in the future"
        )
    client = shared_service_client(settings, create_client)
    if not (
        client.table("organizations")
        .select("id")
        .eq("id", org_id)
        .limit(1)
        .execute()
        .data
        or []
    ):
        raise HTTPException(status_code=404, detail="Organization not found")
    profile = (
        client.table("org_commercial_profiles")
        .select("customer_category")
        .eq("org_id", org_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    current_category = profile[0].get("customer_category") if profile else "unreviewed"
    if (
        current_category == "unreviewed"
        and body.classify_as_external
        and len((body.classification_reason or "").strip()) >= 5
    ):
        has_available = (
            client.table("org_promotional_grants")
            .select("id")
            .eq("org_id", org_id)
            .eq("status", "available")
            .limit(1)
            .execute()
            .data
            or []
        )
        if has_available:
            raise HTTPException(
                status_code=409, detail="Revoke the existing available offer first"
            )
        reason = (body.classification_reason or "").strip()
        client.table("org_commercial_profiles").upsert(
            {
                "org_id": org_id,
                "customer_category": "external",
                "classification_reason": reason,
                "classified_by": founder["user_id"],
                "classified_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
            on_conflict="org_id",
        ).execute()
        write_audit_event(
            client,
            org_id=org_id,
            actor_id=founder["user_id"],
            action="billing.customer_category.changed",
            resource_type="org_commercial_profiles",
            resource_id=org_id,
            metadata={"category": "external", "reason": reason, "via": "issue_offer"},
        )
        current_category = "external"
    if current_category != "external":
        raise HTTPException(
            status_code=403,
            detail=(
                "Only reviewed external customer organizations may receive founder offers"
                if current_category != "unreviewed"
                else "Classify this organization as External (with a reason) before issuing an offer"
            ),
        )
    existing = (
        client.table("org_promotional_grants")
        .select("id")
        .eq("org_id", org_id)
        .eq("status", "available")
        .limit(1)
        .execute()
        .data
        or []
    )
    if existing:
        raise HTTPException(
            status_code=409, detail="Revoke the existing available offer first"
        )
    coupon_id = None
    if body.offer_type == "discount":
        if not settings.stripe_secret_key:
            raise HTTPException(status_code=503, detail="Stripe not configured")
        init_stripe(settings)
        try:
            base_products = _founder_discount_base_products(settings)
            coupon = stripe.Coupon.create(
                applies_to={"products": base_products},
                percent_off=body.percent_off,
                duration="repeating",
                duration_in_months=body.discount_months,
                max_redemptions=1,  # Prevent reusing a founder grant across parallel checkouts.
                name=f"Gravitre founder offer {body.percent_off:g}% for {body.discount_months} month(s)",
                metadata={"org_id": org_id, "issued_by": str(founder["user_id"])},
            )
            coupon_id = coupon["id"]
        except stripe.error.StripeError as exc:
            _raise_stripe_http_error(exc)
    payload = {
        "org_id": org_id,
        "offer_type": body.offer_type,
        "trial_days": body.trial_days,
        "stripe_coupon_id": coupon_id,
        "max_promotion_value_cents": body.max_promotion_value_cents,
        "percent_off": body.percent_off,
        "discount_months": body.discount_months,
        "status": "available",
        "created_by": founder["user_id"],
        "valid_until": body.valid_until.isoformat() if body.valid_until else None,
    }
    inserted = (
        client.table("org_promotional_grants").insert(payload).execute().data or []
    )
    if not inserted:
        raise HTTPException(
            status_code=502, detail="Could not persist promotional offer"
        )
    grant = inserted[0]
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=founder["user_id"],
        action="billing.founder_offer.created",
        resource_type="org_promotional_grants",
        resource_id=str(grant["id"]),
        metadata={
            "type": body.offer_type,
            "trial_days": body.trial_days,
            "percent_off": body.percent_off,
            "discount_months": body.discount_months,
        },
    )
    return {
        "grant_id": grant["id"],
        "org_id": org_id,
        "status": "available",
        "offer_type": body.offer_type,
    }


@router.post("/admin/promotional-offers/{grant_id}/revoke")
def revoke_founder_offer(
    grant_id: str,
    founder: Annotated[dict, Depends(require_platform_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    from uuid import UUID

    try:
        grant_id = str(UUID(grant_id))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="Invalid grant ID") from exc
    client = shared_service_client(settings, create_client)
    rows = (
        client.table("org_promotional_grants")
        .select("id,org_id,status,checkout_attempt_id,stripe_coupon_id")
        .eq("id", grant_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Offer not found")
    grant = rows[0]
    if grant["status"] != "available" or grant.get("checkout_attempt_id"):
        raise HTTPException(
            status_code=409,
            detail="Only unreserved offers may be revoked; reconcile reserved checkout sessions in Stripe first",
        )
    updated = (
        client.table("org_promotional_grants")
        .update(
            {"status": "revoked", "updated_at": datetime.now(timezone.utc).isoformat()}
        )
        .eq("id", grant_id)
        .eq("status", "available")
        .is_("checkout_attempt_id", "null")
        .execute()
        .data
    )
    if not updated:
        raise HTTPException(
            status_code=409,
            detail="Offer was reserved concurrently; review its Stripe checkout",
        )
    # Best effort: a deleted coupon can never be applied later. Existing
    # subscriptions keep any discount already attached.
    from app.billing.founder_offer_ops import delete_coupon_best_effort

    coupon_deleted = delete_coupon_best_effort(settings, grant.get("stripe_coupon_id"))
    write_audit_event(
        client,
        org_id=grant["org_id"],
        actor_id=founder["user_id"],
        action="billing.founder_offer.revoked",
        resource_type="org_promotional_grants",
        resource_id=grant_id,
        metadata={
            "stripe_coupon_id": grant.get("stripe_coupon_id"),
            "coupon_deleted": coupon_deleted,
        },
    )
    return {"grant_id": grant_id, "status": "revoked", "coupon_deleted": coupon_deleted}


@router.post("/checkout")
def create_checkout(
    body: CheckoutRequest,
    member: Annotated[tuple, Depends(require_org_member)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    current_user, org_id, _role = member
    assert_not_msp_billed(settings, org_id)
    plan_code = (body.plan_code or "").strip().lower() or None
    billing_interval = (body.billing_interval or "").strip().lower() or None
    price_id = (body.price_id or "").strip() or None
    if not price_id and plan_code:
        price_id = price_id_for_plan(
            settings, plan_code, billing_interval=billing_interval
        )
    if not plan_code and price_id:
        mapped = plan_code_for_price(settings, price_id)
        plan_code = mapped or "free"
    if not price_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_detail("Invalid plan", "VALIDATION_ERROR"),
        )
    if not settings.stripe_secret_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=error_detail("Stripe is not configured", "INVALID_CONFIG"),
        )
    app_url = (settings.public_app_url or "http://localhost:3000").rstrip("/")
    success_url = f"{app_url}/settings/billing?status=success"
    cancel_url = f"{app_url}/settings/billing?status=cancelled"
    client = shared_service_client(settings, create_client)
    billing = get_org_billing(client, org_id)
    offer = (
        checkout_offer_for_org(client, org_id)
        if settings.commercial_offers_enabled
        else None
    )
    # One discount only: founder offer > validated promo code > Stripe's field.
    discount = checkout_discount(
        client,
        settings,
        promotion_code=body.promotion_code,
        plan_code=plan_code or plan_code_for_price(settings, price_id),
        founder_offer=offer,
    )
    discount_kwargs = checkout_session_kwargs(discount)
    customer_id = billing.get("stripe_customer_id") if billing else None
    if not customer_id:
        try:
            customer_id = _create_stripe_customer(
                settings, client, org_id, current_user["user_id"], plan_code
            )
        except stripe.error.StripeError as exc:
            _raise_stripe_http_error(exc)
    if offer:
        verified_plan = plan_code_for_price(settings, price_id)
        if not verified_plan or (plan_code and verified_plan != plan_code):
            raise HTTPException(
                status_code=422, detail="Offer requires a configured base plan price"
            )
        plan_code = verified_plan
        init_stripe(settings)
        customer = stripe.Customer.retrieve(customer_id)
        if (customer.get("metadata") or {}).get("org_id") != org_id:
            raise HTTPException(
                status_code=409,
                detail="Stripe customer ownership requires reconciliation",
            )
        subscriptions = stripe.Subscription.list(
            customer=customer_id, status="all", limit=100
        )
        if subscriptions.get("has_more") or any(
            row.get("status")
            in {"active", "trialing", "past_due", "unpaid", "incomplete", "paused"}
            or (offer.get("trial_days") and row.get("trial_start"))
            for row in subscriptions.get("data", [])
        ):
            raise HTTPException(
                status_code=409,
                detail="Existing subscription or prior trial requires founder review",
            )
        from app.billing.safety import assert_promotion_cap

        assert_promotion_cap(client, settings, org_id, offer, price_id)
        offer = reserve_checkout_offer(
            client, org_id, offer, customer_id, price_id, current_user["user_id"]
        )
    try:
        session = create_checkout_session(
            settings=settings,
            customer_id=customer_id,
            price_id=price_id,
            success_url=success_url,
            cancel_url=cancel_url,
            offer=offer,
            metadata={
                "org_id": org_id,
                "plan_code": plan_code,
                "billing_interval": billing_interval or "monthly",
                "user_id": current_user["user_id"],
            },
            **discount_kwargs,
        )
    except stripe.error.StripeError as exc:
        if customer_id and not offer and _stripe_customer_missing(exc):
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
                    offer=offer,
                    metadata={
                        "org_id": org_id,
                        "plan_code": plan_code,
                        "billing_interval": billing_interval or "monthly",
                        "user_id": current_user["user_id"],
                    },
                    **discount_kwargs,
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
        metadata={
            "plan_code": plan_code,
            "billing_interval": billing_interval or "monthly",
            "discount_source": discount.get("mode"),
            "promotion_code": discount.get("code"),
        },
    )
    return {
        "url": session.url,
        "checkout_url": session.url,
        **checkout_response_fields(discount),
    }


@router.post("/subscribe")
def create_subscription_payment(
    body: CheckoutRequest,
    member: Annotated[tuple, Depends(require_org_member)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """Create an incomplete Stripe subscription and return Payment Element client_secret."""
    current_user, org_id, _role = member
    assert_not_msp_billed(settings, org_id)
    if settings.commercial_offers_enabled:
        offer_client = shared_service_client(settings, create_client)
        if checkout_offer_for_org(offer_client, org_id):
            raise HTTPException(
                status_code=409,
                detail="Use Stripe Checkout to redeem your founder offer",
            )

    plan_code = (body.plan_code or "").strip().lower() or None
    billing_interval = (body.billing_interval or "").strip().lower() or None
    price_id = (body.price_id or "").strip() or None
    if not price_id and plan_code:
        price_id = price_id_for_plan(
            settings, plan_code, billing_interval=billing_interval
        )
    if not plan_code and price_id:
        mapped = plan_code_for_price(settings, price_id)
        plan_code = mapped or "free"
    if not price_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_detail("Invalid plan", "VALIDATION_ERROR"),
        )
    if not settings.stripe_secret_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=error_detail("Stripe is not configured", "INVALID_CONFIG"),
        )

    client = shared_service_client(settings, create_client)
    # Founder offers were redirected to hosted checkout above, so only a
    # validated public promo code can apply here (Stripe re-validates it).
    discount = (
        checkout_discount(
            client,
            settings,
            promotion_code=body.promotion_code,
            plan_code=plan_code,
            founder_offer=None,
        )
        if (body.promotion_code or "").strip()
        else {"mode": "none"}
    )
    promotion_code_id = discount.get("stripe_promotion_code_id")
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
            promotion_code_id=promotion_code_id,
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
                    promotion_code_id=promotion_code_id,
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
            "discount_source": discount.get("mode"),
            "promotion_code": discount.get("code"),
        },
    )
    return {
        "client_secret": result["client_secret"],
        "subscription_id": result["subscription_id"],
        "customer_id": result["customer_id"],
        "subscription_status": result["subscription_status"],
        **checkout_response_fields(discount),
    }


@router.post("/checkout/public")
def create_public_checkout(
    body: PublicCheckoutRequest,
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    plan_code = (body.plan_code or "").strip().lower() or None
    billing_interval = (body.billing_interval or "").strip().lower() or None
    price_id = (body.price_id or "").strip() or None
    if not price_id and plan_code:
        price_id = price_id_for_plan(
            settings, plan_code, billing_interval=billing_interval
        )
    if not plan_code and price_id:
        mapped = plan_code_for_price(settings, price_id)
        plan_code = mapped or "free"
    if not price_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_detail("Invalid plan", "VALIDATION_ERROR"),
        )
    if not settings.stripe_secret_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=error_detail("Stripe is not configured", "INVALID_CONFIG"),
        )

    app_url = (settings.public_app_url or "http://localhost:3000").rstrip("/")
    success_url = f"{app_url}/get-started?checkout=success"
    cancel_url = f"{app_url}/get-started?checkout=cancelled"
    # Public signup has no org, so no founder offer: a validated code or
    # Stripe's own promo-code field.
    discount = checkout_discount(
        shared_service_client(settings, create_client),
        settings,
        promotion_code=body.promotion_code,
        plan_code=plan_code,
        founder_offer=None,
    )

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
            **checkout_session_kwargs(discount),
        )
    except stripe.error.StripeError as exc:
        _raise_stripe_http_error(exc)
    return {
        "url": session.url,
        "checkout_url": session.url,
        **checkout_response_fields(discount),
    }


@router.post("/portal")
def create_portal(
    _admin: Annotated[tuple, Depends(require_capability("org_settings_billing"))],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    _user, org_id = _admin
    if not settings.stripe_secret_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=error_detail("Stripe is not configured", "INVALID_CONFIG"),
        )
    client = shared_service_client(settings, create_client)
    billing = get_org_billing(client, org_id)
    customer_id = billing.get("stripe_customer_id") if billing else None
    if not customer_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Stripe customer not found"
        )
    app_url = (settings.public_app_url or "http://localhost:3000").rstrip("/")
    portal = create_customer_portal(
        settings=settings,
        customer_id=customer_id,
        return_url=f"{app_url}/settings/billing",
    )
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
def update_seats(
    body: SeatsRequest,
    _admin: Annotated[tuple, Depends(require_capability("org_settings_billing"))],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    _user, org_id = _admin
    client = shared_service_client(settings, create_client)
    # Bug fix (2026-09-12): postgrest-py's SyncQueryRequestBuilder (returned
    # by .upsert()) has no .select()/.limit() method — chaining them raised
    # an uncaught AttributeError on every call. .upsert() already returns the
    # full row by default (returning=representation).
    response = (
        client.table("subscriptions")
        .upsert(
            {
                "org_id": org_id,
                "seat_count": body.quantity,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
            on_conflict="org_id",
        )
        .execute()
    )
    invalidate_org_state(org_id)
    resp_err = getattr(response, "error", None)
    if resp_err:
        raise HTTPException(status_code=500, detail=str(resp_err))
    row = (response.data or [None])[0]
    return {"subscription": _normalize_subscription(row, org_id)}


@router.post("/cancel")
async def cancel_subscription(
    body: CancelRequest,
    _admin: Annotated[tuple, Depends(require_capability("org_settings_billing"))],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    _user, org_id = _admin
    client = shared_service_client(settings, create_client)
    billing = get_org_billing(client, org_id) or {}
    if billing.get("billing_source") == "msp":
        raise HTTPException(409, detail={"code": "BILLED_BY_PARTNER", "message": "Your partner manages this subscription."})
    sub_resp = (
        client.table("subscriptions")
        .select("stripe_subscription_id")
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    )
    sub_row = (sub_resp.data or [{}])[0]
    sub_id = str(
        billing.get("stripe_subscription_id")
        or sub_row.get("stripe_subscription_id")
        or ""
    ).strip()
    now = datetime.now(timezone.utc).isoformat()
    stripe_result: dict = {}

    if sub_id and settings.stripe_secret_key:
        from app.services.stripe_service import (
            cancel_subscription as stripe_cancel_subscription,
        )

        try:
            stripe_result = stripe_cancel_subscription(
                sub_id, immediate=not body.at_period_end, settings=settings
            )
        except stripe.error.StripeError as exc:
            if body.at_period_end and _stripe_cancel_is_soft_fail(exc):
                logger.warning(
                    "stripe cancel soft-fail org_id=%s sub_id=%s err=%s",
                    org_id,
                    sub_id,
                    exc,
                )
            else:
                _raise_stripe_http_error(exc)
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "stripe cancel unexpected org_id=%s sub_id=%s err=%s",
                org_id,
                sub_id,
                exc,
                exc_info=True,
            )
            if not body.at_period_end:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=error_detail("Stripe cancel failed", "STRIPE_ERROR"),
                ) from exc

    org_update: dict = {
        "org_id": org_id,
        "cancel_at_period_end": body.at_period_end,
        "updated_at": now,
    }
    if not body.at_period_end:
        org_update["billing_status"] = "cancelled"
    upsert_resp = _execute_billing_query(
        client.table("org_billing").upsert(org_update, on_conflict="org_id"),
        action="org_billing.upsert_cancel",
    )
    invalidate_org_state(org_id)
    upsert_err = _supabase_response_error(upsert_resp)
    if upsert_err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_detail(upsert_err, "DATABASE_ERROR"),
        )

    from app.routers.webhooks.stripe import _normalize_subscription_status

    sub_status = (
        _normalize_subscription_status(str(stripe_result.get("status") or billing.get("billing_status") or sub_row.get("status") or "inactive"))
        if body.at_period_end else "canceled"
    )
    row = _persist_subscription_status(
        client,
        org_id,
        status=sub_status,
        billing=billing,
        sub_row=sub_row if sub_row else None,
        now=now,
    )
    billing_row = get_org_billing(client, org_id) or {}
    stripe_price_id = str(billing_row.get("stripe_price_id") or "").strip() or None
    return _normalize_subscription(
        {
            **(row or {}),
            "cancel_at_period_end": body.at_period_end,
            "stripe_price_id": stripe_price_id,
            "plan_unit_amount_cents": unit_amount_cents_for_plan_price(stripe_price_id),
            "plan_billing_interval": billing_interval_for_plan_price(stripe_price_id),
        },
        org_id,
    )


@router.post("/reactivate")
async def reactivate_subscription(
    _admin: Annotated[tuple, Depends(require_capability("org_settings_billing"))],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    _user, org_id = _admin
    client = shared_service_client(settings, create_client)
    billing = get_org_billing(client, org_id) or {}
    if billing.get("billing_source") == "msp":
        raise HTTPException(409, detail={"code": "BILLED_BY_PARTNER", "message": "Your partner manages this subscription."})
    sub_resp = (
        client.table("subscriptions")
        .select("stripe_subscription_id")
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    )
    sub_row = (sub_resp.data or [{}])[0]
    sub_id = str(
        billing.get("stripe_subscription_id")
        or sub_row.get("stripe_subscription_id")
        or ""
    ).strip()
    now = datetime.now(timezone.utc).isoformat()

    if not sub_id:
        raise HTTPException(409, detail="No Stripe subscription to resume. Choose a plan first.")
    if not settings.stripe_secret_key:
        raise HTTPException(503, detail="Stripe is not configured")
    stripe_result: dict = {}

    if sub_id and settings.stripe_secret_key:
        from app.services.stripe_service import (
            reactivate_subscription as stripe_reactivate_subscription,
        )

        try:
            stripe_result = stripe_reactivate_subscription(sub_id, settings=settings)
        except stripe.error.StripeError as exc:
            # A missing/invalid subscription cannot grant local paid access.
            _raise_stripe_http_error(exc)
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "stripe reactivate unexpected org_id=%s sub_id=%s err=%s",
                org_id,
                sub_id,
                exc,
                exc_info=True,
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=error_detail("Stripe reactivate failed", "STRIPE_ERROR"),
            ) from exc

    from app.routers.webhooks.stripe import _normalize_subscription_status

    resumed_status = _normalize_subscription_status(str(
        stripe_result.get("status") or billing.get("billing_status") or sub_row.get("status") or "inactive"
    ))
    reactivate_resp = _execute_billing_query(
        client.table("org_billing").upsert(
            {
                "org_id": org_id,
                "cancel_at_period_end": False,
                "billing_status": normalize_billing_status(resumed_status),
                "updated_at": now,
            },
            on_conflict="org_id",
        ),
        action="org_billing.upsert_reactivate",
    )
    invalidate_org_state(org_id)
    reactivate_err = _supabase_response_error(reactivate_resp)
    if reactivate_err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_detail(reactivate_err, "DATABASE_ERROR"),
        )

    row = _persist_subscription_status(
        client,
        org_id,
        status=resumed_status,
        billing=billing,
        sub_row=sub_row if sub_row else None,
        now=now,
    )
    billing_row = get_org_billing(client, org_id) or {}
    stripe_price_id = str(billing_row.get("stripe_price_id") or "").strip() or None
    return _normalize_subscription(
        {
            **(row or {}),
            "cancel_at_period_end": False,
            "stripe_price_id": stripe_price_id,
            "plan_unit_amount_cents": unit_amount_cents_for_plan_price(stripe_price_id),
            "plan_billing_interval": billing_interval_for_plan_price(stripe_price_id),
        },
        org_id,
    )


@router.get("/invoices")
def list_invoices(
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization context required",
        )
    client = shared_service_client(settings, create_client)
    sub_resp = (
        client.table("subscriptions")
        .select("stripe_customer_id")
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    )
    customer_id = ((sub_resp.data or [{}])[0]).get("stripe_customer_id") or (
        get_org_billing(client, org_id) or {}
    ).get("stripe_customer_id")
    invoices, _payment_methods = _fetch_invoices_and_payment_methods(
        settings, customer_id
    )
    return {"invoices": invoices}


def _org_stripe_customer_ids(client, org_id: str) -> set[str]:
    """Stripe customer ids this org owns (subscriptions + org_billing)."""
    ids: set[str] = set()
    try:
        sub_resp = (
            client.table("subscriptions")
            .select("stripe_customer_id")
            .eq("org_id", org_id)
            .limit(1)
            .execute()
        )
        for row in sub_resp.data or []:
            if row.get("stripe_customer_id"):
                ids.add(str(row["stripe_customer_id"]))
    except Exception:  # noqa: BLE001
        pass
    billing_row = get_org_billing(client, org_id) or {}
    if billing_row.get("stripe_customer_id"):
        ids.add(str(billing_row["stripe_customer_id"]))
    return ids


@router.get("/invoices/{invoice_id}/pdf")
def download_invoice_pdf(
    invoice_id: str,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    if org_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization context required",
        )
    if not settings.stripe_secret_key:
        raise HTTPException(status_code=503, detail="Stripe is not configured")
    stripe.api_key = settings.stripe_secret_key
    try:
        invoice = stripe.Invoice.retrieve(invoice_id)
    except Exception as exc:
        raise HTTPException(
            status_code=404, detail=f"Invoice not found: {exc}"
        ) from exc
    # Only hand out PDFs for this org's own Stripe customer; an invoice id from
    # another customer must look exactly like a missing invoice.
    client = shared_service_client(settings, create_client)
    invoice_customer = invoice.get("customer")
    if isinstance(invoice_customer, dict):
        invoice_customer = invoice_customer.get("id")
    if not invoice_customer or str(invoice_customer) not in _org_stripe_customer_ids(
        client, org_id
    ):
        raise HTTPException(status_code=404, detail="Invoice not found")
    pdf_url = invoice.get("invoice_pdf")
    if not pdf_url:
        raise HTTPException(status_code=404, detail="Invoice PDF unavailable")
    return Response(
        content=pdf_url,
        media_type="text/plain",
        headers={"Content-Disposition": f'inline; filename="{invoice_id}.txt"'},
    )


class VoiceTopUpRequest(BaseModel):
    minutes: int = Field(..., description="One of 60, 300, 1200")


@router.post("/top-up/voice-minutes")
def create_voice_minutes_topup(
    body: VoiceTopUpRequest,
    member: Annotated[tuple, Depends(require_org_member)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """Self-serve Voice Minutes pack — Stripe Checkout mode=payment, immediate credit on webhook."""
    current_user, org_id, _role = member
    if not settings.stripe_secret_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=error_detail("Stripe is not configured", "INVALID_CONFIG"),
        )
    from app.billing.voice_topup import create_voice_minutes_topup_checkout

    client = shared_service_client(settings, create_client)
    billing = get_org_billing(client, org_id)
    customer_id = (billing or {}).get("stripe_customer_id")
    if not customer_id:
        raise HTTPException(
            status_code=400,
            detail=error_detail(
                "Add a payment method via an active plan subscription before topping up",
                "VALIDATION_ERROR",
            ),
        )
    app_url = (settings.public_app_url or "http://localhost:3000").rstrip("/")
    try:
        return create_voice_minutes_topup_checkout(
            client,
            settings,
            org_id=org_id,
            minutes=body.minutes,
            customer_id=str(customer_id),
            success_url=f"{app_url}/settings/billing?topup=success",
            cancel_url=f"{app_url}/settings/billing?topup=cancelled",
            actor_user_id=str(current_user.get("user_id") or ""),
        )
    except HTTPException:
        raise
    except stripe.error.StripeError as exc:
        _raise_stripe_http_error(exc)


@router.post("/webhook")
async def handle_webhook(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """Legacy Stripe webhook URL (/api/billing/webhook) — canonical handler lives in webhooks.stripe."""
    from app.routers.webhooks.stripe import stripe_webhook

    return await stripe_webhook(request, settings)


# Deploy gate touch for Command plan billing fix (9b1d748c)
