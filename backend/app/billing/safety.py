"""Fail-closed trial admission, capped offers, and actionable billing evidence."""

from __future__ import annotations
from datetime import datetime, timezone
from decimal import Decimal, ROUND_CEILING
from typing import Any
from fastapi import HTTPException
from app.core.logging import get_logger

logger = get_logger(__name__)


def record_billing_alert(
    client: Any,
    *,
    kind: str,
    key: str,
    org_id: str | None = None,
    details: dict | None = None,
) -> None:
    if org_id:
        from uuid import UUID

        try:
            org_id = str(UUID(org_id))
        except (TypeError, ValueError):
            org_id = None
    try:
        client.rpc(
            "record_billing_safety_alert",
            {
                "p_key": key,
                "p_org_id": org_id,
                "p_kind": kind,
                "p_details": details or {},
            },
        ).execute()
    except Exception:
        logger.exception(
            "billing_safety_alert_persistence_failed kind=%s key=%s", kind, key
        )


def reserve_trial_units(
    client: Any, settings: Any, org_id: str, metric: str, units: int
) -> bool:
    if getattr(settings, "commercial_offers_enabled", False) is not True:
        return False
    from app.billing.service import get_plan_for_org
    from app.billing.research_lookup_plan_rates import (
        included_research_lookups_for_plan,
    )
    from app.billing.voice_minutes_plan_rates import included_voice_minutes_for_plan

    try:
        plan = get_plan_for_org(client, org_id)
        limits = {
            "ai_credits": int(plan.get("ai_credits_included") or 0),
            "voice_minutes": included_voice_minutes_for_plan(plan),
            "research_lookups": included_research_lookups_for_plan(plan),
        }
        result = (
            client.rpc(
                "reserve_founder_trial_units",
                {
                    "p_org_id": org_id,
                    "p_metric": metric,
                    "p_units": units,
                    "p_limit": limits[metric],
                },
            )
            .execute()
            .data
        )
        if result not in {"not_trial", "reserved"}:
            raise ValueError("Unverified trial quota")
        return result == "reserved"
    except Exception as exc:
        raise HTTPException(
            status_code=402,
            detail="Trial allowance is exhausted, expired, or unavailable for verification",
        ) from exc


def promotion_value_cents(grant: dict, price: dict) -> int:
    recurring = price.get("recurring") or {}
    if (
        price.get("currency") != "usd"
        or recurring.get("usage_type") != "licensed"
        or recurring.get("interval_count", 1) != 1
    ):
        raise HTTPException(
            status_code=422,
            detail="Promotion caps require a licensed USD monthly or annual base plan",
        )
    amount = Decimal(str(price.get("unit_amount") or 0))
    interval = recurring.get("interval")
    if amount <= 0 or interval not in {"month", "year"}:
        raise HTTPException(status_code=422, detail="Unable to verify promotion value")
    if grant["offer_type"] == "trial":
        value = (
            amount
            * int(grant["trial_days"])
            / Decimal(28 if interval == "month" else 365)
        )
    else:
        months = int(grant["discount_months"])
        cycles = (months + 11) // 12 if interval == "year" else months
        value = amount * cycles * Decimal(str(grant["percent_off"])) / 100
    return int(value.to_integral_value(rounding=ROUND_CEILING))


def assert_promotion_cap(
    client: Any, settings: Any, org_id: str, offer: dict, price_id: str
) -> int:
    import stripe

    rows = (
        client.table("org_promotional_grants")
        .select("*")
        .eq("org_id", org_id)
        .eq("id", offer["grant_id"])
        .limit(1)
        .execute()
        .data
        or []
    )
    if len(rows) != 1:
        raise HTTPException(status_code=409, detail="Promotion unavailable")
    price = stripe.StripeClient(settings.stripe_secret_key).v1.prices.retrieve(price_id)
    value = promotion_value_cents(rows[0], price)
    if value > int(rows[0].get("max_promotion_value_cents") or 0):
        raise HTTPException(
            status_code=409, detail="Promotion exceeds the founder-approved value cap"
        )
    return value


def run_billing_reconciliation(
    client: Any, settings: Any, *, run_key: str | None = None
) -> dict:
    """Read Stripe truth; retain discrepancies as alerts, never rewrite invoices."""
    import stripe

    key = run_key or datetime.now(timezone.utc).date().isoformat()
    previous = (
        client.table("billing_reconciliation_runs")
        .select("run_key,status")
        .eq("run_key", key)
        .limit(1)
        .execute()
        .data
        or []
    )
    if previous:
        return {"status": "already_claimed", "run_key": key}
    try:
        client.table("billing_reconciliation_runs").insert(
            {"run_key": key, "status": "running"}
        ).execute()
    except Exception as exc:
        if "23505" in str(exc) or "duplicate key" in str(exc).lower():
            return {"status": "already_claimed", "run_key": key}
        raise
    summary = {"checked": 0, "mismatches": 0, "errors": 0, "paid_invoice_amounts": {}}
    try:
        remote = stripe.StripeClient(settings.stripe_secret_key)
        offset = 0
        while True:
            rows = (
                client.table("org_billing")
                .select(
                    "org_id,stripe_customer_id,stripe_subscription_id,billing_status"
                )
                .order("org_id")
                .range(offset, offset + 199)
                .execute()
                .data
                or []
            )
            for row in rows:
                customer_id = row.get("stripe_customer_id")
                if not customer_id:
                    continue
                org_id = str(row["org_id"])
                try:
                    customer = remote.v1.customers.retrieve(customer_id)
                    if (customer.get("metadata") or {}).get("org_id") != org_id:
                        raise ValueError("customer_org_mismatch")
                    subscription_id = row.get("stripe_subscription_id")
                    if subscription_id:
                        subscription = remote.v1.subscriptions.retrieve(subscription_id)
                        if subscription.get("customer") != customer_id:
                            raise ValueError("subscription_customer_mismatch")
                        actual = str(subscription.get("status") or "")
                        expected = "pending" if actual == "incomplete" else actual
                        if row.get("billing_status") != expected:
                            summary["mismatches"] += 1
                            record_billing_alert(
                                client,
                                kind="stripe_subscription_drift",
                                key=f"stripe-drift:{org_id}",
                                org_id=org_id,
                                details={
                                    "local": row.get("billing_status"),
                                    "stripe": actual,
                                    "subscription_id": subscription_id,
                                },
                            )
                    paid = {}
                    for invoice in remote.v1.invoices.list(
                        {"customer": customer_id, "status": "paid", "limit": 100}
                    ).auto_paging_iter():
                        currency = invoice.get("currency") or "unknown"
                        paid[currency] = paid.get(currency, 0) + int(
                            invoice.get("amount_paid") or 0
                        )
                    summary["paid_invoice_amounts"][org_id] = paid
                    summary["checked"] += 1
                except Exception as exc:
                    summary["errors"] += 1
                    record_billing_alert(
                        client,
                        kind="stripe_reconciliation_failed",
                        key=f"stripe-reconcile:{org_id}",
                        org_id=org_id,
                        details={"error_class": type(exc).__name__},
                    )
            if len(rows) < 200:
                break
            offset += 200
        state = "completed" if not summary["errors"] else "failed"
        client.table("billing_reconciliation_runs").update(
            {
                "status": state,
                "summary": summary,
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }
        ).eq("run_key", key).execute()
        return {"status": state, "run_key": key, **summary}
    except Exception:
        client.table("billing_reconciliation_runs").update(
            {"status": "failed", "summary": summary}
        ).eq("run_key", key).execute()
        raise
