"""Stripe usage-sync endpoints.

- POST /api/internal/billing/sync-usage  — cron-triggered; reports usage for all
  active orgs. Protected by the INTERNAL_API_SECRET shared secret (X-Internal-Secret
  header), NOT a user JWT, so an external scheduler (e.g. Railway cron) can call it.
- POST /api/admin/billing/sync-usage     — admin-only manual trigger for one org,
  with dry_run support for testing.
"""
from __future__ import annotations

import asyncio
import hmac
from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel

from app.auth.dependencies import require_admin, require_platform_admin
from app.billing.service import (
    DEFAULT_PLAN_CODE,
    get_current_period,
    get_org_billing,
    get_supabase_client,
    normalize_plan_code,
)
from app.billing.stripe_research_lookup_metering import (
    attach_research_lookup_metered_price_to_subscription,
    report_research_lookup_overage_for_active_orgs,
    report_research_lookup_overage_to_stripe,
    research_lookup_metered_price_id,
)
from app.billing.stripe_voice_minutes_metering import (
    attach_voice_minutes_metered_price_to_subscription,
    report_voice_minutes_overage_for_active_orgs,
    report_voice_minutes_overage_to_stripe,
    voice_minutes_metered_price_id,
)
from app.billing.stripe_metering import (
    StripeAttachmentError,
    attach_metered_price_to_subscription,
    metered_price_id_for_plan_code,
    report_usage_for_active_orgs,
    report_usage_to_stripe,
)
from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.workflows.audit import write_audit_event

logger = get_logger(__name__)

internal_router = APIRouter(prefix="/api/internal/billing", tags=["billing-internal"])
admin_router = APIRouter(prefix="/api/admin/billing", tags=["billing-admin"])


async def require_internal_secret(
    settings: Annotated[Settings, Depends(get_settings)],
    x_internal_secret: Annotated[str | None, Header()] = None,
) -> None:
    secret = (settings.internal_api_secret or "").strip()
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="INTERNAL_API_SECRET is not configured",
        )
    if not x_internal_secret or not hmac.compare_digest(x_internal_secret, secret):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid internal secret")


class AdminSyncRequest(BaseModel):
    org_id: str | None = None
    dry_run: bool = True


class BudgetEnforcementRequest(BaseModel):
    # org_id defaults to the admin's own org; if provided it must match it.
    org_id: str | None = None
    # required: true = force gate on, false = force off, null = clear (inherit global).
    enabled: bool | None


class InternalBudgetEnforcementRequest(BaseModel):
    # Platform/cron endpoint can target any org, so org_id is required.
    org_id: str
    enabled: bool | None


class AttachMeteredPriceRequest(BaseModel):
    org_id: str
    dry_run: bool = True


class AttachAllMeteredPricesRequest(BaseModel):
    dry_run: bool = True


class AdminPlanChangeRequest(BaseModel):
    org_id: str
    plan_code: str
    # internal_override: update Gravitre rows only (labeled in audit).
    # stripe_sync: also attempt to move the Stripe subscription to the plan price.
    mode: str = "internal_override"
    reason: str | None = None


def _lookup_org_subscription(client: Any, org_id: str) -> dict[str, Any] | None:
    """Return subscription_id + plan_code for an org from billing tables."""
    for table in ("org_billing", "subscriptions"):
        try:
            rows = (
                client.table(table)
                .select("stripe_subscription_id, plan_code, status")
                .eq("org_id", org_id)
                .limit(1)
                .execute()
                .data
                or []
            )
            if rows and rows[0].get("stripe_subscription_id"):
                return rows[0]
        except Exception as exc:  # noqa: BLE001
            logger.warning("subscription lookup failed table=%s org_id=%s error=%s", table, org_id, str(exc))
    return None


def _attach_research_lookup_for_org(
    settings: Settings,
    org_id: str,
    subscription_id: str,
    *,
    dry_run: bool,
) -> dict[str, Any]:
    price_id = research_lookup_metered_price_id(settings)
    base = {
        "org_id": org_id,
        "subscription_id": subscription_id,
        "metered_price_id": price_id or None,
        "metric": "research_lookups",
        "dry_run": dry_run,
    }
    if not price_id:
        return {**base, "error": "research_lookup_metered_price_not_configured"}
    if dry_run:
        return {**base, "action": "would_attach"}
    try:
        result = attach_research_lookup_metered_price_to_subscription(
            org_id, subscription_id, settings
        )
        return {**base, **result, "dry_run": False}
    except StripeAttachmentError as exc:
        logger.warning(
            "attach research lookup meter failed org_id=%s error=%s", org_id, str(exc)
        )
        return {**base, "error": str(exc), "dry_run": False}


def _attach_voice_minutes_for_org(
    settings: Settings,
    org_id: str,
    subscription_id: str,
    *,
    dry_run: bool,
) -> dict[str, Any]:
    price_id = voice_minutes_metered_price_id(settings)
    base = {
        "org_id": org_id,
        "subscription_id": subscription_id,
        "metered_price_id": price_id or None,
        "metric": "voice_minutes",
        "dry_run": dry_run,
    }
    if not price_id:
        return {**base, "error": "voice_minutes_metered_price_not_configured"}
    if dry_run:
        return {**base, "action": "would_attach"}
    try:
        result = attach_voice_minutes_metered_price_to_subscription(
            org_id, subscription_id, settings
        )
        return {**base, **result, "dry_run": False}
    except StripeAttachmentError as exc:
        logger.warning(
            "attach voice minutes meter failed org_id=%s error=%s", org_id, str(exc)
        )
        return {**base, "error": str(exc), "dry_run": False}


def _attach_plan_for_org(settings: Settings, org_id: str, *, dry_run: bool) -> dict[str, Any]:
    """Dry-run or live metered-price attachment for one org (AI credits + research lookups)."""
    client = get_supabase_client(settings)
    billing = _lookup_org_subscription(client, org_id)
    if not billing:
        return {"org_id": org_id, "error": "no_subscription", "dry_run": dry_run}
    subscription_id = str(billing["stripe_subscription_id"])
    plan_code = str(billing.get("plan_code") or "node")
    ai_result: dict[str, Any]
    try:
        metered_price_id = metered_price_id_for_plan_code(settings, plan_code)
    except StripeAttachmentError as exc:
        ai_result = {
            "org_id": org_id,
            "subscription_id": subscription_id,
            "plan_code": plan_code,
            "metric": "ai_credits",
            "error": str(exc),
            "dry_run": dry_run,
        }
    else:
        ai_result = {
            "org_id": org_id,
            "subscription_id": subscription_id,
            "plan_code": plan_code,
            "metered_price_id": metered_price_id,
            "metric": "ai_credits",
            "dry_run": dry_run,
        }
        if dry_run:
            ai_result["action"] = "would_attach"
        else:
            try:
                attach_result = attach_metered_price_to_subscription(
                    org_id, subscription_id, plan_code, settings
                )
                ai_result = {**ai_result, **attach_result, "dry_run": False}
            except StripeAttachmentError as exc:
                logger.warning("attach metered price failed org_id=%s error=%s", org_id, str(exc))
                ai_result = {**ai_result, "error": str(exc), "dry_run": False}

    research_result = _attach_research_lookup_for_org(
        settings, org_id, subscription_id, dry_run=dry_run
    )
    voice_result = _attach_voice_minutes_for_org(
        settings, org_id, subscription_id, dry_run=dry_run
    )
    combined_error = None
    errors = [
        e
        for e in (ai_result.get("error"), research_result.get("error"), voice_result.get("error"))
        if e
    ]
    if len(errors) >= 2:
        combined_error = "multiple_meter_attach_failed"
    elif errors:
        combined_error = errors[0]

    return {
        "org_id": org_id,
        "subscription_id": subscription_id,
        "plan_code": plan_code,
        "dry_run": dry_run,
        "ai_credits": ai_result,
        "research_lookups": research_result,
        "voice_minutes": voice_result,
        **({"error": combined_error} if combined_error else {}),
    }


def _set_hard_budget_override(settings: Settings, org_id: str, enabled: bool | None) -> dict[str, Any]:
    """Upsert org_billing.hard_budget_enabled. Upsert (not get_or_create) avoids
    the billing_plans FK path; on insert plan_code stays null + billing_status
    uses its default."""
    client = get_supabase_client(settings)
    client.table("org_billing").upsert(
        {
            "org_id": org_id,
            "hard_budget_enabled": enabled,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
        on_conflict="org_id",
    ).execute()
    logger.info("budget enforcement override org_id=%s enabled=%s", org_id, enabled)
    return {"org_id": org_id, "hard_budget_enabled": enabled}


@internal_router.post("/sync-usage")
async def sync_usage_cron(
    settings: Annotated[Settings, Depends(get_settings)],
    _: Annotated[None, Depends(require_internal_secret)],
) -> dict[str, Any]:
    """Report metered usage for all active orgs for the current period."""
    period_start, period_end = get_current_period()
    ai_summary = report_usage_for_active_orgs(period_start, period_end, settings)
    research_summary = report_research_lookup_overage_for_active_orgs(period_start, period_end, settings)
    voice_summary = report_voice_minutes_overage_for_active_orgs(period_start, period_end, settings)
    logger.info(
        "billing usage sync ai_orgs=%s ai_rows=%s research_orgs=%s research_reported=%s voice_orgs=%s voice_reported=%s",
        ai_summary.get("orgs"),
        ai_summary.get("reported_rows"),
        research_summary.get("orgs"),
        research_summary.get("reported_orgs"),
        voice_summary.get("orgs"),
        voice_summary.get("reported_orgs"),
    )
    return {
        "ai_credits": ai_summary,
        "research_lookups": research_summary,
        "voice_minutes": voice_summary,
    }


@admin_router.post("/sync-usage")
async def sync_usage_admin(
    body: AdminSyncRequest,
    admin: Annotated[tuple[dict, str], Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    """Manual trigger for a single org. dry_run=True (default) calculates without
    calling Stripe."""
    _user, admin_org_id = admin
    org_id = (body.org_id or admin_org_id or "").strip()
    if not org_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="org_id is required")
    if org_id != admin_org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only sync usage for your own organization",
        )
    period_start, period_end = get_current_period()
    ai_result = report_usage_to_stripe(
        org_id, period_start, period_end, settings, dry_run=body.dry_run
    )
    research_result = report_research_lookup_overage_to_stripe(
        org_id, period_start, period_end, settings, dry_run=body.dry_run
    )
    voice_result = report_voice_minutes_overage_to_stripe(
        org_id, period_start, period_end, settings, dry_run=body.dry_run
    )
    return {
        "ai_credits": ai_result,
        "research_lookups": research_result,
        "voice_minutes": voice_result,
    }


@admin_router.post("/budget-enforcement")
async def set_budget_enforcement(
    body: BudgetEnforcementRequest,
    admin: Annotated[tuple[dict, str], Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    """Set the per-org hard-budget override (org_billing.hard_budget_enabled).

    enabled=true forces the budget gate on for this org even when the global
    flag is off; false forces it off; null clears the override (inherit global).
    Scoped to the admin's own org for tenant isolation.
    """
    _user, admin_org_id = admin
    org_id = (body.org_id or admin_org_id or "").strip()
    if not org_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="org_id is required")
    if org_id != admin_org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only manage budget enforcement for your own organization",
        )
    return _set_hard_budget_override(settings, org_id, body.enabled)


@admin_router.post("/attach-metered-price")
async def attach_metered_price_admin(
    body: AttachMeteredPriceRequest,
    admin: Annotated[tuple[dict, str], Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    """Attach (or dry-run) the metered overage price for one org's subscription."""
    _user, admin_org_id = admin
    org_id = (body.org_id or "").strip()
    if not org_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="org_id is required")
    if org_id != admin_org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only attach metered prices for your own organization",
        )
    result = _attach_plan_for_org(settings, org_id, dry_run=body.dry_run)
    if result.get("error") == "no_subscription":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active subscription for org")
    if not body.dry_run and result.get("error"):
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=result["error"])
    return result


@admin_router.post("/attach-all-metered-prices")
async def attach_all_metered_prices_admin(
    body: AttachAllMeteredPricesRequest,
    _: Annotated[tuple[dict, str], Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    """Attach metered prices for all orgs with active subscriptions (rate-limited)."""
    client = get_supabase_client(settings)
    try:
        rows = (
            client.table("subscriptions")
            .select("org_id")
            .eq("status", "active")
            .execute()
            .data
            or []
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("active orgs lookup failed error=%s", str(exc))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="active orgs query failed") from exc

    org_ids = sorted({str(r["org_id"]) for r in rows if r.get("org_id")})
    details: list[dict[str, Any]] = []
    attached = already_attached = failed = 0
    for org_id in org_ids:
        res = _attach_plan_for_org(settings, org_id, dry_run=body.dry_run)
        details.append(res)
        if res.get("error"):
            failed += 1
            continue
        for metric in ("ai_credits", "research_lookups", "voice_minutes"):
            part = res.get(metric) if isinstance(res.get(metric), dict) else {}
            if part.get("error"):
                continue
            if part.get("status") == "already_attached":
                already_attached += 1
            elif part.get("status") == "attached" or (
                body.dry_run and part.get("action") == "would_attach"
            ):
                attached += 1
        await asyncio.sleep(1)

    return {
        "total": len(org_ids),
        "attached": attached,
        "already_attached": already_attached,
        "failed": failed,
        "dry_run": body.dry_run,
        "details": details,
    }


@internal_router.post("/budget-enforcement")
async def set_budget_enforcement_internal(
    body: InternalBudgetEnforcementRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    _: Annotated[None, Depends(require_internal_secret)],
) -> dict[str, Any]:
    """Platform-wide per-org budget override for ops/cron (any org). Protected by
    INTERNAL_API_SECRET, not a user JWT."""
    org_id = (body.org_id or "").strip()
    if not org_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="org_id is required")
    return _set_hard_budget_override(settings, org_id, body.enabled)


@admin_router.post("/plan")
async def admin_set_org_plan(
    body: AdminPlanChangeRequest,
    platform_admin: Annotated[dict, Depends(require_platform_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    """Platform-admin plan change against the single SoT (org_billing + subscriptions).

    mode=internal_override updates Gravitre only and is audited as such — it does
    not invent a second plan store. mode=stripe_sync also updates the Stripe
    subscription price when configured.
    """
    org_id = (body.org_id or "").strip()
    plan_code = normalize_plan_code(body.plan_code)
    mode = (body.mode or "internal_override").strip().lower()
    if not org_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="org_id is required")
    if plan_code not in {"node", "control", "command", "enterprise"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid plan_code")
    if mode not in {"internal_override", "stripe_sync"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid mode")

    client = get_supabase_client(settings)
    before = get_org_billing(client, org_id) or {}
    previous = normalize_plan_code(before.get("plan_code") or DEFAULT_PLAN_CODE)
    now = datetime.now(timezone.utc).isoformat()
    stripe_result: dict[str, Any] | None = None

    if mode == "stripe_sync":
        from app.billing.stripe import init_stripe, price_id_for_plan
        import stripe

        sub_id = str(before.get("stripe_subscription_id") or "").strip()
        if not sub_id or not settings.stripe_secret_key:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="stripe_sync requires an active Stripe subscription and STRIPE_SECRET_KEY",
            )
        try:
            price_id = price_id_for_plan(settings, plan_code, "monthly")
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        if not price_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No Stripe price configured for plan_code={plan_code}",
            )
        init_stripe(settings)
        try:
            stripe_sub = stripe.Subscription.retrieve(sub_id)
            items = (stripe_sub.get("items") or {}).get("data") or []
            licensed = next(
                (
                    item
                    for item in items
                    if str(((item.get("price") or {}).get("recurring") or {}).get("usage_type") or "").lower()
                    != "metered"
                ),
                items[0] if items else None,
            )
            if not licensed:
                raise HTTPException(status_code=400, detail="No licensed subscription item to update")
            updated = stripe.Subscription.modify(
                sub_id,
                items=[{"id": licensed["id"], "price": price_id}],
                proration_behavior="create_prorations",
                metadata={"plan_code": plan_code, "org_id": org_id},
            )
            stripe_result = {"subscription_id": sub_id, "price_id": price_id, "status": updated.get("status")}
        except HTTPException:
            raise
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    billing_payload: dict[str, Any] = {
        "org_id": org_id,
        "plan_code": plan_code,
        "billing_status": before.get("billing_status") or "active",
        "updated_at": now,
    }
    if stripe_result and stripe_result.get("price_id"):
        billing_payload["stripe_price_id"] = stripe_result["price_id"]
    client.table("org_billing").upsert(billing_payload, on_conflict="org_id").execute()
    client.table("subscriptions").upsert(
        {
            "org_id": org_id,
            "tier": plan_code,
            "status": "active",
            "updated_at": now,
            **(
                {"stripe_subscription_id": before["stripe_subscription_id"]}
                if before.get("stripe_subscription_id")
                else {}
            ),
        },
        on_conflict="org_id",
    ).execute()

    actor_id = str(platform_admin.get("user_id") or platform_admin.get("id") or "")
    write_audit_event(
        client,
        org_id,
        actor_id,
        "billing.plan.changed",
        "org_billing",
        org_id,
        {
            "from_plan": previous,
            "to_plan": plan_code,
            "mode": mode,
            "reason": body.reason,
            "stripe": stripe_result,
            "internal_override": mode == "internal_override",
        },
    )
    client.table("billing_events").insert(
        {
            "org_id": org_id,
            "action": "billing.plan.changed",
            "event_type": "billing.plan.changed",
            "status": "success",
            "payload": {
                "from_plan": previous,
                "to_plan": plan_code,
                "mode": mode,
                "reason": body.reason,
                "stripe": stripe_result,
            },
        }
    ).execute()

    return {
        "org_id": org_id,
        "from_plan": previous,
        "to_plan": plan_code,
        "mode": mode,
        "stripe": stripe_result,
        "source_of_truth": "org_billing.plan_code",
    }
