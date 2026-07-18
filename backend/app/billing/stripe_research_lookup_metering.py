"""Stripe usage reporting for Research Lookup overage (separate from ai_credits_used)."""
from __future__ import annotations

import hashlib
import time
from datetime import date, datetime, timezone
from typing import Any

import stripe

from app.billing.research_lookup_plan_rates import (
    included_research_lookups_for_plan,
)
from app.billing.service import get_plan_for_org, get_supabase_client
from app.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def research_lookup_meter_event_name(settings: Settings) -> str:
    return (
        getattr(settings, "stripe_research_lookup_meter_event_name", None) or "research_lookups_used"
    ).strip()


def research_lookup_metered_price_id(settings: Settings) -> str:
    return (getattr(settings, "stripe_research_lookup_metered_price_id", None) or "").strip()


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


def _unreported_research_lookup_rows(
    client: Any,
    org_id: str,
    period_start: date,
    period_end: date,
) -> list[dict[str, Any]]:
    start_iso, end_iso = _month_bounds(period_start, period_end)
    try:
        return (
            client.table("usage_records")
            .select("id, quantity, recorded_at")
            .eq("org_id", org_id)
            .eq("metric_type", "research_lookups")
            .gte("recorded_at", start_iso)
            .lt("recorded_at", end_iso)
            .is_("stripe_reported_at", "null")
            .execute()
            .data
            or []
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("research lookup usage query failed org_id=%s error=%s", org_id, str(exc))
        return []


def report_research_lookup_overage_to_stripe(
    org_id: str,
    period_start: date,
    period_end: date,
    settings: Settings,
    *,
    client: Any | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Report unreported research lookup OVERAGE units to Stripe Billing Meter."""
    client = client or get_supabase_client(settings)
    result: dict[str, Any] = {
        "org_id": org_id,
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "dry_run": dry_run,
        "metric": "research_lookups",
        "total_lookups": 0,
        "included_lookups": 0,
        "overage_lookups": 0,
        "unreported_rows": 0,
        "reported": False,
    }

    rows = _unreported_research_lookup_rows(client, org_id, period_start, period_end)
    row_ids = [r["id"] for r in rows if r.get("id")]
    total_lookups = sum(int(r.get("quantity") or 0) for r in rows)
    result["unreported_rows"] = len(row_ids)
    result["total_lookups"] = total_lookups

    if not row_ids or total_lookups <= 0:
        return result

    plan = get_plan_for_org(client, org_id)
    included = included_research_lookups_for_plan(plan)
    result["included_lookups"] = included

    # Report only overage portion for this batch relative to period total unreported.
    # Conservative: if period total (all rows, reported or not) exceeds included, report min(batch, overage).
    start_iso, end_iso = _month_bounds(period_start, period_end)
    try:
        all_rows = (
            client.table("usage_records")
            .select("quantity")
            .eq("org_id", org_id)
            .eq("metric_type", "research_lookups")
            .gte("recorded_at", start_iso)
            .lt("recorded_at", end_iso)
            .execute()
            .data
            or []
        )
        period_total = sum(int(r.get("quantity") or 0) for r in all_rows)
    except Exception:  # noqa: BLE001
        period_total = total_lookups

    overage_total = max(period_total - included, 0)
    result["overage_lookups"] = overage_total
    if overage_total <= 0:
        return result

    report_qty = min(total_lookups, overage_total)
    result["report_quantity"] = report_qty

    if not (settings.stripe_secret_key or "").strip():
        result["error"] = "stripe_not_configured"
        return result
    if not research_lookup_metered_price_id(settings):
        result["error"] = "research_lookup_metered_price_not_configured"
        return result

    customer_id = _get_customer_id(client, org_id)
    if not customer_id:
        result["error"] = "no_customer"
        return result
    result["customer_id"] = customer_id

    if dry_run:
        return result

    event_name = research_lookup_meter_event_name(settings)
    batch = ",".join(sorted(str(i) for i in row_ids))
    identifier = hashlib.sha256(
        f"research_lookups:{org_id}:{period_start}:{period_end}:{batch}".encode()
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
        logger.error("research lookup meter event failed org_id=%s error=%s", org_id, str(exc))
        result["error"] = f"stripe_error: {exc}"
        return result

    try:
        client.table("usage_records").update(
            {"stripe_reported_at": datetime.now(timezone.utc).isoformat()}
        ).in_("id", row_ids).execute()
    except Exception as exc:  # noqa: BLE001
        logger.error("research lookup mark-reported failed org_id=%s error=%s", org_id, str(exc))
        result["error"] = "mark_reported_failed"

    result["reported"] = True
    result["event_name"] = event_name
    result["identifier"] = identifier
    return result


def report_research_lookup_overage_for_active_orgs(
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
        res = report_research_lookup_overage_to_stripe(
            org_id, period_start, period_end, settings, client=client
        )
        if res.get("reported"):
            reported += 1
        results.append(res)
    return {"orgs": len(org_ids), "reported_orgs": reported, "results": results}
