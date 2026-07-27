#!/usr/bin/env python3
"""Baseline: unified-turn LIVE fallthrough rate from production audit_events.

Counts unified_turn.live.completed vs unified_turn.live.fallthrough and
breaks fallthrough down by metadata.fallthrough_reason (existing audit payload).

Capstone instrumentation: pending_family_classical_resume and live_disabled are
named fallthrough reasons. R2 (≤1% for 7 days) must use this complete set —
expect the rate to rise when previously silent paths become counted.
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx
from dotenv import dotenv_values
from supabase import create_client

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
OUT = ROOT / "docs" / "delivery" / "unified-turn-fallthrough-baseline.json"
BASE = os.environ.get("LIVE_API_BASE", "https://api.gravitre.app").rstrip("/")
WINDOW_HOURS = int(os.environ.get("FALLTHROUGH_WINDOW_HOURS", "168"))


def load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for p in (BACKEND / ".env", ROOT / ".env", BACKEND / ".env.operator.local"):
        if not p.is_file():
            continue
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                loaded = dotenv_values(p, encoding=enc)
                merged.update({k: v for k, v in loaded.items() if v})
                break
            except UnicodeDecodeError:
                continue
    merged.update({k: v for k, v in os.environ.items() if v})
    return merged


def _meta(row: dict[str, Any]) -> dict[str, Any]:
    meta = row.get("metadata") or {}
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except json.JSONDecodeError:
            meta = {}
    return meta if isinstance(meta, dict) else {}


def _bucket_reason(raw: str | None) -> str:
    reason = str(raw or "").strip() or "unknown"
    if reason.startswith("outcome_"):
        return "unified_outcome_skip"
    if reason == "defer_connector_tool_proposal":
        return "connector_tool_proposal_deferral"
    if reason == "defer_classical_tool_sse":
        return "classical_tool_sse_deferral"
    if reason == "violates_no_pending_hold":
        return "guard_violation"
    if reason == "pending_family_classical_resume":
        return "pending_family_classical_resume"
    if reason == "live_disabled":
        return "live_disabled"
    if reason in {"write_plan_unavailable", "read_tool_classical"}:
        return reason
    if reason.startswith("unhandled_kind_"):
        return "unhandled_outcome_kind"
    return reason


def _fetch_action_rows(
    sb: Any,
    *,
    action: str,
    since_iso: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    offset = 0
    page = 1000
    while True:
        batch = (
            sb.table("audit_events")
            .select("action,created_at,metadata,resource_id,org_id")
            .eq("action", action)
            .gte("created_at", since_iso)
            .order("created_at", desc=False)
            .range(offset, offset + page - 1)
            .execute()
        )
        data = batch.data or []
        if not data:
            break
        rows.extend(data)
        if len(data) < page:
            break
        offset += page
    return rows


def main() -> int:
    env = load_env()
    for key in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"):
        if not env.get(key):
            raise SystemExit(f"missing {key}")

    since = datetime.now(timezone.utc) - timedelta(hours=WINDOW_HOURS)
    since_iso = since.isoformat()
    sb = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])

    health: dict[str, Any] = {}
    try:
        health = httpx.get(f"{BASE}/health", timeout=30).json()
    except Exception as exc:  # noqa: BLE001
        health = {"error": str(exc)}

    completed = _fetch_action_rows(sb, action="unified_turn.live.completed", since_iso=since_iso)
    fallthrough = _fetch_action_rows(sb, action="unified_turn.live.fallthrough", since_iso=since_iso)

    raw_reasons = Counter()
    bucket_reasons = Counter()
    outcome_kinds = Counter()
    for row in fallthrough:
        meta = _meta(row)
        raw = str(meta.get("fallthrough_reason") or "unknown")
        raw_reasons[raw] += 1
        bucket_reasons[_bucket_reason(raw)] += 1
        outcome_kinds[str(meta.get("outcome_kind") or "unknown")] += 1

    live_total = len(completed) + len(fallthrough)
    fallthrough_pct = round(100.0 * len(fallthrough) / live_total, 2) if live_total else 0.0

    report: dict[str, Any] = {
        "feature": "unified_turn_live_fallthrough_baseline",
        "window_hours": WINDOW_HOURS,
        "since": since_iso,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "health": {
            k: health.get(k)
            for k in ("git_sha", "unified_turn_live_enabled", "timestamp")
        },
        "totals": {
            "live_completed": len(completed),
            "live_fallthrough": len(fallthrough),
            "live_turns_with_audit": live_total,
            "fallthrough_pct_of_audited_live_turns": fallthrough_pct,
        },
        "fallthrough_by_raw_reason": dict(raw_reasons.most_common()),
        "fallthrough_by_bucket": dict(bucket_reasons.most_common()),
        "fallthrough_outcome_kinds": dict(outcome_kinds.most_common()),
        "notes": {
            "pending_family_silent_fallthrough": (
                "Instrumented: has_pending_family now emits "
                "unified_turn.live.fallthrough with "
                "fallthrough_reason=pending_family_classical_resume."
            ),
            "live_disabled_silent_fallthrough": (
                "Instrumented: flag-off early return emits "
                "fallthrough_reason=live_disabled when a client is present."
            ),
            "r2_gate_baseline_note": (
                "R2 (≤1% fallthrough for 7 days) must use this complete "
                "reason set including pending_family_classical_resume; "
                "rate may rise when newly instrumented paths appear."
            ),
            "bucket_mapping": {
                "unified_outcome_skip": "outcome_skipped / outcome_error",
                "connector_tool_proposal_deferral": "defer_connector_tool_proposal",
                "classical_tool_sse_deferral": "defer_classical_tool_sse",
                "guard_violation": "violates_no_pending_hold",
                "pending_family_classical_resume": "pending_family_classical_resume",
                "live_disabled": "live_disabled",
            },
        },
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
