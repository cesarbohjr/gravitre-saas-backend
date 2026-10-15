#!/usr/bin/env python3
"""Bounded recovery of persisted assistant model calls missing usage rows.

Read-only unless --apply is explicitly provided. Requires an explicit UTC
window within one CURRENT billing month. The atomic RPC is the only write path;
replay is safe after a timeout. An operator must review any plan changes in the
window before applying, because historical plan snapshots do not exist yet.
Never use this for the pre-rollout unattributed model_calls history.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.billing.service import (  # noqa: E402
    compute_ai_credits, get_plan_for_org, record_assistant_model_usage_atomic,
)
from app.config import get_settings  # noqa: E402
from app.core.db import get_supabase_client  # noqa: E402

PAGE_SIZE = 200


def _existing_usage(client, rows: list[dict], period_start: str) -> dict[tuple[str, str], dict]:
    """Fetch the exact per-call ledger anchors in bounded, org-scoped batches."""
    by_org: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        org_id = str(row["org_id"])
        call_id = str(row["id"])
        by_org[org_id].append(f"{org_id}:assistant:{call_id}:{period_start}")
    found: dict[tuple[str, str], dict] = {}
    for org_id, keys in by_org.items():
        ledger_rows = (client.table("usage_tracking")
                       .select("id,org_id,idempotency_key,quantity,source,source_id,model_name,input_tokens,output_tokens")
                       .eq("org_id", org_id).in_("idempotency_key", keys)
                       .range(0, len(keys) - 1).execute().data or [])
        if len(ledger_rows) >= len(keys):
            # The unique key permits at most one row per call. Hitting the
            # expected cap is safe only when every requested key is present.
            if {r.get("idempotency_key") for r in ledger_rows} != set(keys):
                raise ValueError("Assistant usage lookup may be truncated")
        for item in ledger_rows:
            found[(org_id, str(item["idempotency_key"]))] = item
    return found


def reconcile(client, since: datetime, before: datetime, *, apply: bool,
              max_calls: int = 1000, _preflighted: bool = False) -> dict[str, int | bool]:
    if since.tzinfo is None or before.tzinfo is None or since >= before:
        raise ValueError("A valid timezone-aware window is required")
    since = since.astimezone(timezone.utc)
    before = before.astimezone(timezone.utc)
    now = datetime.now(timezone.utc)
    if ((since.year, since.month) != (now.year, now.month)
            or (before.year, before.month) != (now.year, now.month)):
        raise ValueError("Recovery is restricted to the current UTC billing month")
    if before > now - timedelta(minutes=10):
        raise ValueError("Recent calls may still be in-flight; end at least 10 minutes ago")
    if max_calls <= 0 or max_calls > 10000:
        raise ValueError("max_calls must be between 1 and 10000")
    if apply and not _preflighted:
        preflight = reconcile(client, since, before, apply=False, max_calls=max_calls)
        if preflight["errors"] or preflight["truncated"]:
            raise ValueError("Recovery preflight found mismatched or truncated usage; no writes were made")
        return reconcile(client, since, before, apply=True, max_calls=max_calls, _preflighted=True)

    result: dict[str, int | bool] = {
        "scanned": 0, "zero_tokens": 0, "candidates": 0,
        "already_billed": 0, "mismatched": 0,
        "inserted": 0, "duplicate": 0, "errors": 0,
        "dry_run": not apply, "truncated": False,
    }
    included_by_org: dict[str, int] = {}
    offset = 0
    while True:
        rows = (client.table("model_calls")
                .select("id,org_id,model_name,input_tokens,output_tokens,created_at")
                .like("turn_id", "assistant:%")
                .gte("created_at", since.isoformat())
                .lt("created_at", before.isoformat())
                .order("id").range(offset, offset + PAGE_SIZE - 1)
                .execute().data or [])
        remaining = max_calls - int(result["scanned"])
        if not remaining:
            result["truncated"] = bool(rows)
            return result
        if len(rows) > remaining:
            result["truncated"] = True
            rows = rows[:remaining]
        usage = _existing_usage(client, rows, since.date().replace(day=1).isoformat()) if rows else {}
        for row in rows:
            result["scanned"] += 1
            input_tokens = int(row.get("input_tokens") or 0)
            output_tokens = int(row.get("output_tokens") or 0)
            if input_tokens + output_tokens <= 0:
                result["zero_tokens"] += 1
                continue
            org_id = str(row["org_id"])
            call_id = str(row["id"])
            key = f"{org_id}:assistant:{call_id}:{since.date().replace(day=1).isoformat()}"
            existing = usage.get((org_id, key))
            if existing:
                credits = compute_ai_credits(input_tokens, output_tokens, row.get("model_name"))
                if (existing.get("source") != "assistant"
                    or str(existing.get("source_id")) != call_id
                    or int(existing.get("quantity") or 0) != credits
                    or int(existing.get("input_tokens") or 0) != input_tokens
                    or int(existing.get("output_tokens") or 0) != output_tokens
                    or existing.get("model_name") != row.get("model_name")):
                    result["mismatched"] += 1
                    result["errors"] += 1
                    if apply:
                        raise ValueError("Assistant usage changed after preflight; stop recovery")
                else:
                    result["already_billed"] += 1
                continue
            result["candidates"] += 1
            if not apply:
                continue
            try:
                if org_id not in included_by_org:
                    included_by_org[org_id] = int(get_plan_for_org(client, org_id).get("ai_credits_included") or 0)
                credits = compute_ai_credits(input_tokens, output_tokens, row.get("model_name"))
                status = record_assistant_model_usage_atomic(
                    client, org_id, call_id, credits,
                    included_by_org[org_id],
                )
                if status in {"inserted", "duplicate"}:
                    result[status] += 1
            except Exception:  # noqa: BLE001 - aggregate only; no tenant details in output
                result["errors"] += 1
        if len(rows) < PAGE_SIZE:
            return result
        offset += PAGE_SIZE


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--since", required=True, help="UTC ISO timestamp after rollout")
    parser.add_argument("--before", required=True, help="UTC ISO timestamp >=10 minutes ago")
    parser.add_argument("--max-calls", type=int, default=1000)
    parser.add_argument("--apply", action="store_true", help="Write via the atomic service-role-only RPC")
    args = parser.parse_args()
    try:
        since = datetime.fromisoformat(args.since.replace("Z", "+00:00"))
        before = datetime.fromisoformat(args.before.replace("Z", "+00:00"))
        settings = get_settings()
        if args.apply and settings.assistant_billing_atomic_enabled is not True:
            parser.error("Apply requires ASSISTANT_BILLING_ATOMIC_ENABLED=true and reviewed migration")
        client = get_supabase_client(settings)
        summary = reconcile(client, since, before, apply=args.apply, max_calls=args.max_calls)
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps(summary, sort_keys=True))
    return 1 if summary["errors"] or summary["truncated"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
