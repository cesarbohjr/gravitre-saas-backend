"""Stripe usage (metered) billing reporting.

The Gravitre plans (node/control/command) are flat-rate subscriptions today.
AI-credit usage is metered internally into `usage_tracking`, but nothing reported
it to Stripe, so usage-based overages were never billed. This module reports
that usage to a Stripe Billing Meter.

API choice — Billing Meter Events (`stripe.billing.MeterEvent.create`):
- The modern usage-based billing primitive; the legacy
  `SubscriptionItem.create_usage_record` API is deprecated and removed from
  current Stripe API versions.
- Meter events are keyed by `stripe_customer_id` (which we store), not a
  subscription-item id (which we don't).
- Idempotency: meter events are *additive*, so we only ever report
  `usage_tracking` rows with `stripe_reported_at IS NULL`, then mark them. A
  deterministic event `identifier` (hash of the batch) lets Stripe de-dupe if a
  marking write failed and the same batch is retried.

Prerequisite to actually bill: the Stripe account must have a Billing Meter for
`STRIPE_METER_EVENT_NAME` and the subscription must include a metered price tied
to that meter. Until then this records usage on the meter without producing
charges. Reporting is the missing half; wiring the metered price is a Stripe
Dashboard / pricing change.
"""
from __future__ import annotations

import hashlib
import time
from datetime import date, datetime, timezone
from typing import Any

import stripe

from app.billing.service import get_supabase_client
from app.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class StripeAttachmentError(RuntimeError):
    """Raised when a metered price cannot be attached to a subscription."""


def metered_price_id_for_plan_code(settings: Settings, plan_code: str) -> str:
    """Resolve the configured metered price id for a plan code.

    Raises StripeAttachmentError when the plan has no configured metered price.
    """
    from app.billing.stripe import metered_price_id_for_plan

    price_id = metered_price_id_for_plan(settings, plan_code)
    if not price_id:
        raise StripeAttachmentError(
            f"No metered price configured for plan_code={plan_code!r}. "
            f"Set STRIPE_METERED_PRICE_ID_{plan_code.upper()} in environment."
        )
    return price_id


def attach_metered_price_to_subscription(
    org_id: str,
    subscription_id: str,
    plan_code: str,
    settings: Settings,
) -> dict[str, Any]:
    """Attach the metered overage price to an existing Stripe subscription.

    Idempotent: if the metered price item already exists, returns the existing
    item without creating a duplicate.

    Raises StripeAttachmentError when subscription is missing, plan has no
    metered price, or Stripe returns an unrecoverable error.
    """
    _ = org_id  # reserved for audit/logging
    metered_price_id = metered_price_id_for_plan_code(settings, plan_code)
    if not (settings.stripe_secret_key or "").strip():
        raise StripeAttachmentError("STRIPE_SECRET_KEY is not configured")

    stripe.api_key = settings.stripe_secret_key
    try:
        subscription = stripe.Subscription.retrieve(subscription_id)
    except stripe.error.InvalidRequestError as exc:
        raise StripeAttachmentError(f"subscription_id not found: {subscription_id}") from exc
    except Exception as exc:  # noqa: BLE001
        raise StripeAttachmentError(f"Stripe subscription retrieve failed: {exc}") from exc

    items = getattr(getattr(subscription, "items", None), "data", None) or []
    for item in items:
        price = getattr(item, "price", None)
        if price and getattr(price, "id", None) == metered_price_id:
            return {"status": "already_attached", "item_id": item.id}

    try:
        new_item = stripe.SubscriptionItem.create(
            subscription=subscription_id,
            price=metered_price_id,
            payment_behavior="default_incomplete",
        )
    except Exception as exc:  # noqa: BLE001
        raise StripeAttachmentError(f"Stripe SubscriptionItem.create failed: {exc}") from exc

    return {"status": "attached", "item_id": new_item.id}


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


def report_usage_to_stripe(
    org_id: str,
    period_start: date,
    period_end: date,
    settings: Settings,
    *,
    client: Any | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Report unreported AI-credit usage for an org/period to Stripe.

    Returns a summary dict including how many rows were reported.
    """
    client = client or get_supabase_client(settings)
    result: dict[str, Any] = {
        "org_id": org_id,
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "dry_run": dry_run,
        "credits": 0,
        "unreported_rows": 0,
        "reported_rows": 0,
        "reported": False,
    }

    try:
        rows = (
            client.table("usage_tracking")
            .select("id,quantity,credits")
            .eq("org_id", org_id)
            .eq("metric_type", "ai_credits")
            .eq("period_start", period_start.isoformat())
            .eq("period_end", period_end.isoformat())
            .is_("stripe_reported_at", "null")
            .execute()
            .data
            or []
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("usage_tracking query failed org_id=%s error=%s", org_id, str(exc))
        result["error"] = "query_failed"
        return result

    row_ids = [r["id"] for r in rows]
    total_credits = sum(int(r.get("quantity") or r.get("credits") or 0) for r in rows)
    result["unreported_rows"] = len(row_ids)
    result["credits"] = total_credits

    if not row_ids or total_credits <= 0:
        return result

    customer_id = _get_customer_id(client, org_id)
    if not customer_id:
        logger.warning("no stripe customer for org_id=%s; skipping usage report", org_id)
        result["error"] = "no_customer"
        return result
    result["customer_id"] = customer_id

    if dry_run:
        return result

    if not (settings.stripe_secret_key or "").strip():
        result["error"] = "stripe_not_configured"
        return result

    event_name = (settings.stripe_meter_event_name or "ai_credits_used").strip()
    # Deterministic identifier over the exact batch -> Stripe de-dupes a retry of
    # the same rows even if our mark-as-reported write previously failed.
    batch = ",".join(sorted(str(i) for i in row_ids))
    identifier = hashlib.sha256(f"{org_id}:{period_start}:{period_end}:{batch}".encode()).hexdigest()
    # Meter events represent usage at report time; stamp "now" (clamped so we
    # never send a future-dated period_end, which Stripe rejects).
    period_end_ts = int(datetime(period_end.year, period_end.month, period_end.day, tzinfo=timezone.utc).timestamp())
    timestamp = min(period_end_ts, int(time.time()))

    try:
        stripe.api_key = settings.stripe_secret_key
        stripe.billing.MeterEvent.create(
            event_name=event_name,
            payload={"stripe_customer_id": customer_id, "value": str(total_credits)},
            identifier=identifier,
            timestamp=timestamp,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("stripe meter event failed org_id=%s error=%s", org_id, str(exc))
        result["error"] = f"stripe_error: {exc}"
        return result

    try:
        client.table("usage_tracking").update(
            {"stripe_reported_at": datetime.now(timezone.utc).isoformat()}
        ).in_("id", row_ids).execute()
    except Exception as exc:  # noqa: BLE001
        # The meter event used a deterministic identifier, so a retry of the same
        # batch is de-duped by Stripe; log loudly but don't fail the report.
        logger.error("mark-reported failed org_id=%s rows=%s error=%s", org_id, len(row_ids), str(exc))
        result["error"] = "mark_reported_failed"

    result["reported"] = True
    result["reported_rows"] = len(row_ids)
    result["event_name"] = event_name
    result["identifier"] = identifier
    return result


def report_usage_for_active_orgs(
    period_start: date,
    period_end: date,
    settings: Settings,
    *,
    client: Any | None = None,
) -> dict[str, Any]:
    """Report usage for every org with an active subscription. Used by the cron."""
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
    reported_rows = 0
    for org_id in org_ids:
        res = report_usage_to_stripe(org_id, period_start, period_end, settings, client=client)
        reported_rows += int(res.get("reported_rows") or 0)
        results.append(res)
    return {"orgs": len(org_ids), "reported_rows": reported_rows, "results": results}
