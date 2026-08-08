"""Stripe usage reporting for Voice Minutes overage (clone of research_lookup metering)."""
from __future__ import annotations

import hashlib
import time
from datetime import date, datetime, timezone
from typing import Any

import stripe

from app.billing.service import get_plan_for_org, get_supabase_client
from app.billing.voice_minutes_plan_rates import included_voice_minutes_for_plan
from app.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def voice_minutes_meter_event_name(settings: Settings) -> str:
    return (
        getattr(settings, "stripe_voice_minutes_meter_event_name", None) or "voice_minutes_used"
    ).strip()


def voice_minutes_metered_price_id(settings: Settings) -> str:
    return (getattr(settings, "stripe_voice_minutes_metered_price_id", None) or "").strip()


def _get_customer_id(client: Any, org_id: str) -> str | None:
    for table in ("subscriptions", "org_billing"):
        try:
            rows = (
                client.table(table)
                .select("stripe_customer_id")
                .eq("org_id", org_id)
                .limit(1)
                .execute()
                .data
                or []
            )
            if rows and rows[0].get("stripe_customer_id"):
                return str(rows[0]["stripe_customer_id"])
        except Exception as exc:  # noqa: BLE001
            logger.warning("customer lookup failed table=%s org_id=%s error=%s", table, org_id, str(exc))
    return None


def _month_bounds(period_start: date, period_end: date) -> tuple[str, str]:
    start_iso = datetime(period_start.year, period_start.month, period_start.day, tzinfo=timezone.utc).isoformat()
    end_iso = datetime(period_end.year, period_end.month, period_end.day, tzinfo=timezone.utc).isoformat()
    return start_iso, end_iso


def report_voice_minutes_overage_to_stripe(
    org_id: str,
    period_start: date,
    period_end: date,
    settings: Settings,
    *,
    client: Any | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    client = client or get_supabase_client(settings)
    result: dict[str, Any] = {
        "org_id": org_id,
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "dry_run": dry_run,
        "metric": "voice_minutes",
        "total_minutes": 0,
        "included_minutes": 0,
        "overage_minutes": 0,
        "unreported_rows": 0,
        "reported": False,
    }
    start_iso, end_iso = _month_bounds(period_start, period_end)
    try:
        rows = (
            client.table("usage_records")
            .select("id, quantity, recorded_at")
            .eq("org_id", org_id)
            .eq("metric_type", "voice_minutes")
            .gte("recorded_at", start_iso)
            .lt("recorded_at", end_iso)
            .is_("stripe_reported_at", "null")
            .execute()
            .data
            or []
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("voice minutes usage query failed org_id=%s error=%s", org_id, str(exc))
        rows = []
    row_ids = [r["id"] for r in rows if r.get("id")]
    total_minutes = sum(int(r.get("quantity") or 0) for r in rows)
    result["unreported_rows"] = len(row_ids)
    result["total_minutes"] = total_minutes
    if not row_ids or total_minutes <= 0:
        return result

    plan = get_plan_for_org(client, org_id)
    included = included_voice_minutes_for_plan(plan)
    result["included_minutes"] = included
    try:
        all_rows = (
            client.table("usage_records")
            .select("quantity")
            .eq("org_id", org_id)
            .eq("metric_type", "voice_minutes")
            .gte("recorded_at", start_iso)
            .lt("recorded_at", end_iso)
            .execute()
            .data
            or []
        )
        period_total = sum(int(r.get("quantity") or 0) for r in all_rows)
    except Exception:  # noqa: BLE001
        period_total = total_minutes
    overage_total = max(period_total - included, 0)
    result["overage_minutes"] = overage_total
    if overage_total <= 0:
        return result
    report_qty = min(total_minutes, overage_total)
    result["report_quantity"] = report_qty
    if not (settings.stripe_secret_key or "").strip():
        result["error"] = "stripe_not_configured"
        return result
    if not voice_minutes_metered_price_id(settings):
        result["error"] = "voice_minutes_metered_price_not_configured"
        return result
    customer_id = _get_customer_id(client, org_id)
    if not customer_id:
        result["error"] = "no_customer"
        return result
    result["customer_id"] = customer_id
    if dry_run:
        return result

    event_name = voice_minutes_meter_event_name(settings)
    batch = ",".join(sorted(str(i) for i in row_ids))
    identifier = hashlib.sha256(
        f"voice_minutes:{org_id}:{period_start}:{period_end}:{batch}".encode()
    ).hexdigest()
    period_end_ts = int(datetime(period_end.year, period_end.month, period_end.day, tzinfo=timezone.utc).timestamp())
    timestamp = min(period_end_ts, int(time.time()))
    try:
        stripe.api_key = settings.stripe_secret_key
        stripe.billing.MeterEvent.create(
            event_name=event_name,
            payload={"stripe_customer_id": customer_id, "value": str(report_qty)},
            identifier=identifier,
            timestamp=timestamp,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("voice minutes meter event failed org_id=%s error=%s", org_id, str(exc))
        result["error"] = f"stripe_error: {exc}"
        return result
    try:
        client.table("usage_records").update(
            {"stripe_reported_at": datetime.now(timezone.utc).isoformat()}
        ).in_("id", row_ids).execute()
    except Exception as exc:  # noqa: BLE001
        logger.error("voice minutes mark-reported failed org_id=%s error=%s", org_id, str(exc))
        result["error"] = "mark_reported_failed"
    result["reported"] = True
    result["event_name"] = event_name
    result["identifier"] = identifier
    return result


def attach_voice_minutes_metered_price_to_subscription(
    org_id: str,
    subscription_id: str,
    settings: Settings,
) -> dict[str, Any]:
    from app.billing.stripe_metering import StripeAttachmentError

    _ = org_id
    metered_price_id = voice_minutes_metered_price_id(settings)
    if not metered_price_id:
        raise StripeAttachmentError("STRIPE_VOICE_MINUTES_METERED_PRICE_ID is not configured.")
    if not (settings.stripe_secret_key or "").strip():
        raise StripeAttachmentError("STRIPE_SECRET_KEY is not configured")
    stripe.api_key = settings.stripe_secret_key
    try:
        subscription = stripe.Subscription.retrieve(subscription_id)
    except Exception as exc:  # noqa: BLE001
        raise StripeAttachmentError(f"Stripe subscription retrieve failed: {exc}") from exc
    items = getattr(getattr(subscription, "items", None), "data", None) or []
    for item in items:
        price = getattr(item, "price", None)
        if price and getattr(price, "id", None) == metered_price_id:
            return {"status": "already_attached", "item_id": item.id, "metered_price_id": metered_price_id}
    try:
        new_item = stripe.SubscriptionItem.create(
            subscription=subscription_id,
            price=metered_price_id,
            payment_behavior="default_incomplete",
        )
    except Exception as exc:  # noqa: BLE001
        raise StripeAttachmentError(f"Stripe SubscriptionItem.create failed: {exc}") from exc
    return {"status": "attached", "item_id": new_item.id, "metered_price_id": metered_price_id}


def report_voice_minutes_overage_for_active_orgs(
    period_start: date,
    period_end: date,
    settings: Settings,
    *,
    client: Any | None = None,
) -> dict[str, Any]:
    client = client or get_supabase_client(settings)
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
        return {"orgs": 0, "reported_rows": 0, "results": [], "error": "active_orgs_query_failed"}
    org_ids = sorted({str(r["org_id"]) for r in rows if r.get("org_id")})
    results: list[dict[str, Any]] = []
    reported = 0
    for org_id in org_ids:
        res = report_voice_minutes_overage_to_stripe(
            org_id, period_start, period_end, settings, client=client
        )
        if res.get("reported"):
            reported += 1
        results.append(res)
    return {"orgs": len(org_ids), "reported_orgs": reported, "results": results}
