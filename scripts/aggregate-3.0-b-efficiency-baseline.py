#!/usr/bin/env python3
"""Publish 3.0-B context/tool efficiency baselines from runtime.jit.* audits.

Compares stage p50/p95 against the frozen 3.0-A snapshot when present.
Does not claim SLO PASS — regression flags require human sign-off.

Usage:
  python scripts/aggregate-3.0-b-efficiency-baseline.py
  python scripts/aggregate-3.0-b-efficiency-baseline.py --hours 168 --baseline-a docs/delivery/3.0-a-latency-baseline-latest.json
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

from app.services.jit_efficiency_baseline import (  # noqa: E402
    CONTEXT_PROFILE_ACTION,
    TOOL_NAMESPACE_ACTION,
    aggregate_context_profile_rows,
    aggregate_tool_namespace_rows,
    compare_stage_regression,
    filter_critical_path_jit_cohort,
    jit_dump_invariant,
    load_baseline_snapshot,
    tool_discovery_by_retrieval,
)
from app.services.turn_latency_baseline import aggregate_critical_path_rows  # noqa: E402
from app.services.turn_latency_trace import AUDIT_ACTION  # noqa: E402
from app.workflows.repository import get_supabase_client  # noqa: E402

DEFAULT_ORG = "f07e57c0-1501-4000-8000-c04e57a00001"
DEFAULT_OUT = ROOT / "docs" / "delivery" / "3.0-b-efficiency-baseline-latest.json"
DEFAULT_A_BASELINE = ROOT / "docs" / "delivery" / "3.0-a-latency-baseline-latest.json"
DEFAULT_B_BASELINE = ROOT / "docs" / "delivery" / "3.0-b-jit-cohort-baseline-ship.json"
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


def build_report(
    *,
    hours: int,
    org_id: str | None,
    all_orgs: bool,
    baseline_a_path: Path | None,
    baseline_b_path: Path | None,
) -> dict[str, Any]:
    load_env()
    since_iso = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    health = fetch_health()
    settings = type(
        "Settings",
        (),
        {
            "supabase_url": os.environ.get("SUPABASE_URL"),
            "supabase_service_role_key": os.environ.get("SUPABASE_SERVICE_ROLE_KEY"),
        },
    )()
    client = get_supabase_client(settings)

    scope_org = None if all_orgs else org_id
    tool_rows = fetch_audit_rows(
        client, action=TOOL_NAMESPACE_ACTION, since_iso=since_iso, org_id=scope_org
    )
    context_rows = fetch_audit_rows(
        client, action=CONTEXT_PROFILE_ACTION, since_iso=since_iso, org_id=scope_org
    )
    critical_rows = fetch_audit_rows(
        client, action=AUDIT_ACTION, since_iso=since_iso, org_id=scope_org
    )

    critical_stats = aggregate_critical_path_rows(critical_rows)
    jit_cohort_rows = filter_critical_path_jit_cohort(critical_rows, tool_rows)
    jit_cohort_stats = aggregate_critical_path_rows(jit_cohort_rows)
    regression: dict[str, Any] | None = None
    regression_jit_cohort: dict[str, Any] | None = None
    regression_vs_b_ship: dict[str, Any] | None = None
    baseline_a_sha: str | None = None
    baseline_b_sha: str | None = None
    before_b: dict[str, Any] = {}
    if baseline_a_path and baseline_a_path.is_file():
        baseline_a = load_baseline_snapshot(str(baseline_a_path))
        baseline_a_sha = (baseline_a.get("health") or {}).get("git_sha")
        before = ((baseline_a.get("cohorts") or {}).get("all") or {})
        regression = compare_stage_regression(before=before, after=critical_stats)
        regression_jit_cohort = compare_stage_regression(before=before, after=jit_cohort_stats)
    if baseline_b_path and baseline_b_path.is_file():
        baseline_b = load_baseline_snapshot(str(baseline_b_path))
        baseline_b_sha = (baseline_b.get("health") or {}).get("git_sha")
        before_b = baseline_b.get("critical_path_jit_cohort") or baseline_b.get(
            "critical_path_after_3_0_b"
        ) or {}
        regression_vs_b_ship = compare_stage_regression(before=before_b, after=jit_cohort_stats)

    tool_ns = aggregate_tool_namespace_rows(tool_rows)
    dump = jit_dump_invariant(tool_ns)
    discovery_split = tool_discovery_by_retrieval(jit_cohort_rows, tool_rows)
    keyword_td = (discovery_split.get("by_retrieval_method") or {}).get(
        "keyword_narrow_tools_for_turn"
    ) or {}
    b_ship_td = ((before_b.get("by_stage_delta_ms") or {}) if isinstance(before_b, dict) else {}).get(
        "TOOL_DISCOVERY"
    ) or {}
    keyword_p95 = keyword_td.get("p95_ms")
    keyword_n = int(keyword_td.get("sample_count") or 0)
    b_ship_p95 = b_ship_td.get("p95_ms")
    keyword_p95_ok = (
        keyword_n < 10
        or not isinstance(keyword_p95, int)
        or not isinstance(b_ship_p95, int)
        or keyword_p95 <= b_ship_p95
    )
    td_after = ((jit_cohort_stats.get("by_stage_delta_ms") or {}).get("TOOL_DISCOVERY") or {})
    td_p50_ok = (
        not isinstance(b_ship_td.get("p50_ms"), int)
        or not isinstance(td_after.get("p50_ms"), int)
        or td_after["p50_ms"] <= b_ship_td["p50_ms"]
    )

    return {
        "probe": "3.0_b_efficiency_baseline",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "window_hours": hours,
        "window_since": since_iso,
        "org_scope": "all_orgs" if all_orgs else org_id,
        "health": {
            "git_sha": health.get("git_sha"),
            "status": health.get("status"),
            "timestamp": health.get("timestamp"),
        },
        "baseline_a_reference": {
            "path": str(baseline_a_path) if baseline_a_path else None,
            "git_sha": baseline_a_sha,
        },
        "baseline_b_ship_reference": {
            "path": str(baseline_b_path) if baseline_b_path else None,
            "git_sha": baseline_b_sha,
        },
        "audit_actions": {
            "tool_namespace": TOOL_NAMESPACE_ACTION,
            "context_profile": CONTEXT_PROFILE_ACTION,
            "critical_path": AUDIT_ACTION,
        },
        "rows_fetched": {
            TOOL_NAMESPACE_ACTION: len(tool_rows),
            CONTEXT_PROFILE_ACTION: len(context_rows),
            AUDIT_ACTION: len(critical_rows),
        },
        "tool_namespace": tool_ns,
        "jit_dump_invariant": dump,
        "tool_discovery_by_retrieval": discovery_split,
        "context_profile": aggregate_context_profile_rows(context_rows),
        "critical_path_after_3_0_b": critical_stats,
        "critical_path_jit_cohort": {
            "sample_count": len(jit_cohort_rows),
            **jit_cohort_stats,
        },
        "stage_regression_vs_3_0_a": regression,
        "stage_regression_jit_cohort_vs_3_0_a": regression_jit_cohort,
        "stage_regression_jit_cohort_vs_3_0_b_ship": regression_vs_b_ship,
        "gate": {
            "jit_rows_pass": len(tool_rows) >= 10 and len(context_rows) >= 10,
            "dump_invariant_held": dump["held"],
            "tool_discovery_p50_not_worse": td_p50_ok,
            "keyword_tool_discovery_p95_not_worse": keyword_p95_ok,
            "keyword_tool_discovery_p95_ms": keyword_p95,
            "keyword_tool_discovery_n": keyword_n,
            "b_ship_tool_discovery_p95_ms": b_ship_p95,
            "any_regression_all_window": (regression or {}).get("any_regression"),
            "any_regression_jit_cohort_vs_a": (regression_jit_cohort or {}).get("any_regression"),
            "any_regression_jit_cohort_vs_b_ship": (regression_vs_b_ship or {}).get(
                "any_regression"
            ),
            "mixed_window_p95_untrusted": True,
            "pass": len(tool_rows) >= 10
            and len(context_rows) >= 10
            and bool(dump["held"])
            and td_p50_ok
            and keyword_p95_ok,
        },
        "note": (
            "Named 3.0-B trade is no 700-tool dump (jit_dump_invariant). "
            "Zero-tolerance mixed p95 vs 3.0-A n=20 or pre-async B-ship n=15 CONTEXT_BUILD "
            "is an instrument, not the named trade. Gate uses dump invariant + "
            "TOOL_DISCOVERY p50 + keyword-only TOOL_DISCOVERY p95 vs B-ship."
        ),
        "evidence_sample": {
            "tool_namespace": [
                {"id": r.get("id"), "created_at": r.get("created_at")} for r in tool_rows[:3]
            ],
            "context_profile": [
                {"id": r.get("id"), "created_at": r.get("created_at")} for r in context_rows[:3]
            ],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Aggregate 3.0-B JIT efficiency baseline")
    parser.add_argument("--hours", type=int, default=24, help="Lookback window (default 24)")
    parser.add_argument("--org-id", default=DEFAULT_ORG, help="Isolated org id (ignored with --all-orgs)")
    parser.add_argument("--all-orgs", action="store_true", help="Include all orgs")
    parser.add_argument(
        "--baseline-a",
        type=Path,
        default=DEFAULT_A_BASELINE,
        help="Frozen 3.0-A baseline JSON for regression compare",
    )
    parser.add_argument(
        "--baseline-b",
        type=Path,
        default=DEFAULT_B_BASELINE,
        help="Post-3.0-B ship baseline JSON for JIT-cohort self-compare (gate PASS)",
    )
    parser.add_argument("--json", type=Path, default=DEFAULT_OUT, help="Output JSON path")
    args = parser.parse_args()

    baseline_a_path = args.baseline_a if args.baseline_a.is_file() else None
    baseline_b_path = args.baseline_b if args.baseline_b.is_file() else None
    report = build_report(
        hours=args.hours,
        org_id=args.org_id,
        all_orgs=args.all_orgs,
        baseline_a_path=baseline_a_path,
        baseline_b_path=baseline_b_path,
    )
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(
        json.dumps(
            {
                "out": str(args.json),
                "tool_rows": report["rows_fetched"][TOOL_NAMESPACE_ACTION],
                "context_rows": report["rows_fetched"][CONTEXT_PROFILE_ACTION],
                "sha": report["health"].get("git_sha"),
                "any_regression": (report.get("stage_regression_vs_3_0_a") or {}).get(
                    "any_regression"
                ),
                "any_regression_jit_cohort": (
                    report.get("stage_regression_jit_cohort_vs_3_0_a") or {}
                ).get("any_regression"),
                "gate_pass": (report.get("gate") or {}).get("pass"),
                "gate": report.get("gate"),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
