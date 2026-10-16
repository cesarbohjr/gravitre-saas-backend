#!/usr/bin/env python3
"""Read-only, aggregate Stripe outbox reconciliation across billing surfaces.

Never prints customer IDs, organization IDs, model calls, source rows or tokens.
Return code 2 means unresolved billing exceptions. No charge or mutation occurs.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

PAGE_SIZE = 500
METRICS = ("ai_credits", "research_lookups", "voice_minutes")
STATUSES = ("pending", "sending", "delivered", "ambiguous", "zero")


def _pages(query: Any):
    offset = 0
    while True:
        rows = query.range(offset, offset + PAGE_SIZE - 1).execute().data or []
        for row in rows:
            yield row
        if len(rows) < PAGE_SIZE:
            break
        offset += PAGE_SIZE


def report(client: Any, *, period_start: date) -> dict[str, Any]:
    counts: Counter[str] = Counter()
    outbox: dict[tuple[str, str, str], dict[str, Any]] = {}
    rows = _pages(client.table("stripe_meter_outbox").select(
        "org_id,source_id,metric_type,status,quantity,included_snapshot,period_start"
    ).eq("period_start", period_start.isoformat()).order("id"))
    for row in rows:
        metric = str(row["metric_type"])
        if metric not in METRICS:
            counts["unknown_metric"] += 1
            continue
        status = str(row["status"])
        counts[f"{metric}_{status}"] += 1
        if status not in STATUSES:
            counts["invalid_status"] += 1
        outbox[(str(row["org_id"]), metric, str(row["source_id"]))] = row
        if status in ("sending", "ambiguous"):
            counts["requires_stripe_reconciliation"] += 1

    # Ledger is canonical: every production AI-credit row in the period needs
    # a corresponding outbox intent. The report does not infer acceptance from
    # a missing Stripe event; reconciliation must inspect the persisted intent.
    settled_source_ids: set[tuple[str, str]] = set()
    ledger = _pages(client.table("usage_tracking").select(
        "id,org_id,quantity,source_id,stripe_reported_at"
    ).eq("metric_type", "ai_credits").eq("environment", "production")
        .eq("period_start", period_start.isoformat()).order("id"))
    for row in ledger:
        counts["ai_credits_ledger_rows"] += 1
        if row.get("source_id"):
            settled_source_ids.add((str(row["org_id"]), str(row["source_id"])))
        match = outbox.get((str(row["org_id"]), "ai_credits", str(row["id"])))
        if match is None:
            counts["ai_credits_missing_intents"] += 1
        elif match["status"] in ("delivered", "zero") and not row.get("stripe_reported_at"):
            counts["delivered_missing_source_ack"] += 1
        elif match["status"] in ("pending", "sending", "ambiguous") and row.get("stripe_reported_at"):
            counts["source_reported_without_intent_ack"] += 1
    # Research and voice share usage_records but are different meter/allowance
    # buckets. Include the final UTC day by querying up to next-month midnight.
    next_month = date(period_start.year + (period_start.month == 12),
                      period_start.month % 12 + 1, 1)
    lower = datetime(period_start.year, period_start.month, period_start.day,
                     tzinfo=timezone.utc).isoformat()
    upper = datetime(next_month.year, next_month.month, 1,
                     tzinfo=timezone.utc).isoformat()
    for metric in ("research_lookups", "voice_minutes"):
        source_rows = _pages(client.table("usage_records").select(
            "id,org_id,stripe_reported_at"
        ).eq("metric_type", metric).gte("recorded_at", lower)
            .lt("recorded_at", upper).order("id"))
        for row in source_rows:
            counts[f"{metric}_ledger_rows"] += 1
            match = outbox.get((str(row["org_id"]), metric, str(row["id"])))
            if match is None:
                counts[f"{metric}_missing_intents"] += 1
            elif match["status"] in ("delivered", "zero") and not row.get("stripe_reported_at"):
                counts["delivered_missing_source_ack"] += 1
            elif match["status"] in ("pending", "sending", "ambiguous") and row.get("stripe_reported_at"):
                counts["source_reported_without_intent_ack"] += 1
    # Model-call evidence joins to the canonical AI ledger through source_id.
    # This distinguishes assistant turns, attributed workflow/agent runs and
    # other metered model calls without exposing tenant or call identifiers.
    calls = _pages(client.table("model_calls").select(
        "id,org_id,run_id,turn_id,billing_credits,billing_settled_at"
    ).gte("created_at", lower).lt("created_at", upper).order("id"))
    for row in calls:
        credits = row.get("billing_credits")
        if credits is None or int(credits) <= 0:
            continue
        turn_id = str(row.get("turn_id") or "")
        source = ("workflow_agent" if row.get("run_id")
                  else "assistant" if turn_id.startswith("assistant:")
                  else "other_model")
        counts[f"{source}_billable_model_calls"] += 1
        if not row.get("billing_settled_at"):
            counts[f"{source}_model_calls_unsettled"] += 1
        elif (str(row["org_id"]), str(row["id"])) not in settled_source_ids:
            counts["settled_model_calls_missing_ledger"] += 1
    counts["outbox_total_rows"] = len(outbox)
    counts["unresolved_errors"] = sum(counts[key] for key in (
        "unknown_metric", "invalid_status", "requires_stripe_reconciliation",
        "ai_credits_missing_intents", "research_lookups_missing_intents",
        "voice_minutes_missing_intents", "delivered_missing_source_ack",
        "assistant_model_calls_unsettled", "workflow_agent_model_calls_unsettled",
        "other_model_model_calls_unsettled", "settled_model_calls_missing_ledger",
        "source_reported_without_intent_ack",
    ))
    return {"period_start": period_start.isoformat(), **dict(sorted(counts.items()))}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--period-start", required=True, help="First UTC date of billing period (YYYY-MM-DD)")
    args = parser.parse_args()
    start = date.fromisoformat(args.period_start)
    from app.config import get_settings
    from app.core.db import get_supabase_client
    output = report(get_supabase_client(get_settings()), period_start=start)
    print(json.dumps(output, sort_keys=True))
    return 2 if output["unresolved_errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
