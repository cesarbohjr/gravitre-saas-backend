#!/usr/bin/env python3
"""Publish 3.0-A text/work latency baselines from critical-path audit events.

Reads audit_events.action = runtime.turn_latency.critical_path and writes
p50/p95 by turn total, dominant stage, and per-stage deltas. Does not claim
Metric A/B PASS — voice SLO rows are included separately when present.

Usage:
  python scripts/aggregate-3.0-a-latency-baseline.py
  python scripts/aggregate-3.0-a-latency-baseline.py --hours 168 --json docs/delivery/3.0-a-latency-baseline-latest.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(ROOT))

from app.services.turn_latency_baseline import (  # noqa: E402
    aggregate_critical_path_rows,
    aggregate_slo_metric_rows,
    split_cohorts,
)
from app.services.turn_latency_trace import AUDIT_ACTION  # noqa: E402
from app.services.voice_slo import (  # noqa: E402
    AUDIT_METRIC_A,
    AUDIT_METRIC_B,
    METRIC_A_P50_MS,
    METRIC_A_P95_MS,
    METRIC_B_P50_MS,
    METRIC_B_P95_MS,
)
from app.workflows.repository import get_supabase_client  # noqa: E402


DEFAULT_ORG = "f07e57c0-1501-4000-8000-c04e57a00001"
DEFAULT_OUT = ROOT / "docs" / "delivery" / "3.0-a-latency-baseline-latest.json"
LIVE_API = os.environ.get("LIVE_API_BASE", "https://api.gravitre.app").rstrip("/")


def load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for path in (BACKEND / ".env", ROOT / ".env", BACKEND / ".env.operator.local"):
        if not path.is_file():
            continue
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                merged.update({k: v for k, v in dotenv_values(path, encoding=enc).items() if v})
                break
            except UnicodeDecodeError:
                continue
    for key, value in os.environ.items():
        if value and key not in merged:
            merged[key] = value
    for key in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_JWT_SECRET"):
        if merged.get(key):
            os.environ[key] = merged[key]
    return merged


def fetch_health() -> dict[str, Any]:
    try:
        resp = httpx.get(f"{LIVE_API}/health", timeout=20.0)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "error": str(exc)}


def fetch_audit_rows(
    client: Any,
    *,
    action: str,
    since_iso: str,
    org_id: str | None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    offset = 0
    page = 500
    while True:
        q = (
            client.table("audit_events")
            .select("id,created_at,action,resource_id,metadata,org_id")
            .eq("action", action)
            .gte("created_at", since_iso)
            .order("created_at", desc=True)
        )
        if org_id:
            q = q.eq("org_id", org_id)
        batch = q.range(offset, offset + page - 1).execute()
        data = batch.data or []
        if not data:
            break
        rows.extend(data)
        if len(data) < page:
            break
        offset += page
    return rows


def build_report(*, hours: int, org_id: str | None, all_orgs: bool) -> dict[str, Any]:
    load_env()
    since_iso = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    health = fetch_health()
    settings = type("Settings", (), {"supabase_url": os.environ.get("SUPABASE_URL"), "supabase_service_role_key": os.environ.get("SUPABASE_SERVICE_ROLE_KEY")})()
    client = get_supabase_client(settings)

    scope_org = None if all_orgs else org_id
    critical_rows = fetch_audit_rows(client, action=AUDIT_ACTION, since_iso=since_iso, org_id=scope_org)
    metric_a_rows = fetch_audit_rows(client, action=AUDIT_METRIC_A, since_iso=since_iso, org_id=scope_org)
    metric_b_rows = fetch_audit_rows(client, action=AUDIT_METRIC_B, since_iso=since_iso, org_id=scope_org)

    cohorts = split_cohorts(critical_rows)
    cohort_stats = {
        name: aggregate_critical_path_rows(rows) for name, rows in cohorts.items() if name != "unknown_spoken_mode"
    }
    if cohorts["unknown_spoken_mode"]:
        cohort_stats["unknown_spoken_mode"] = aggregate_critical_path_rows(cohorts["unknown_spoken_mode"])

    return {
        "probe": "3.0_a_latency_baseline",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "window_hours": hours,
        "window_since": since_iso,
        "org_scope": "all_orgs" if all_orgs else org_id,
        "health": {
            "git_sha": health.get("git_sha"),
            "status": health.get("status"),
            "timestamp": health.get("timestamp"),
        },
        "audit_action": AUDIT_ACTION,
        "critical_path_rows_fetched": len(critical_rows),
        "cohorts": cohort_stats,
        "voice_slo_reference_targets": {
            "metric_a": {"p50_ms": METRIC_A_P50_MS, "p95_ms": METRIC_A_P95_MS},
            "metric_b": {"p50_ms": METRIC_B_P50_MS, "p95_ms": METRIC_B_P95_MS},
        },
        "voice_slo_audit_rows": {
            AUDIT_METRIC_A: len(metric_a_rows),
            AUDIT_METRIC_B: len(metric_b_rows),
        },
        "voice_slo_measured": {
            "metric_a": aggregate_slo_metric_rows(metric_a_rows),
            "metric_b": aggregate_slo_metric_rows(metric_b_rows),
        },
        "note": (
            "Baselines are measured p50/p95 from runtime.turn_latency.critical_path only. "
            "Dominant stage = largest checkpoint delta per turn, not average stage time. "
            "No PASS/FAIL claimed until compared to published 3.0 budgets."
        ),
        "evidence_sample": [
            {
                "id": row.get("id"),
                "created_at": row.get("created_at"),
                "resource_id": row.get("resource_id"),
            }
            for row in critical_rows[:5]
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Aggregate 3.0-A critical-path latency baseline")
    parser.add_argument("--hours", type=int, default=24, help="Lookback window (default 24)")
    parser.add_argument("--org-id", default=DEFAULT_ORG, help="Isolated org id (ignored with --all-orgs)")
    parser.add_argument("--all-orgs", action="store_true", help="Include all orgs")
    parser.add_argument("--json", type=Path, default=DEFAULT_OUT, help="Output JSON path")
    args = parser.parse_args()

    report = build_report(hours=args.hours, org_id=args.org_id, all_orgs=args.all_orgs)
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"out": str(args.json), "rows": report["critical_path_rows_fetched"], "sha": report["health"].get("git_sha")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
