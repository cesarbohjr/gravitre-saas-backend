#!/usr/bin/env python3
"""Milestone 2 — live performance audit on prod (internal-only queries).

Measures latency, SSE proxies, Research Manager stop-early signals, internet/connector
guardrails, and compares model_calls aggregates before vs after Research Manager deploy.

The binding latency guardrail is **before/after delta** on the same 5 internal queries,
not an absolute ceiling. Run `scripts/smoke-milestone2-latency-ab.py --full-ab` for that
evidence (brief pre-RM prod rollback per OIL/claim3 playbook).

Usage:
  python scripts/smoke-milestone2-performance-audit.py
  python scripts/smoke-milestone2-performance-audit.py --latency-baseline docs/delivery/m2-pre-rm-latency.json
  python scripts/smoke-milestone2-performance-audit.py --json docs/delivery/milestone2-performance-audit-latest.json
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import jwt
from dotenv import dotenv_values

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(REPO))

from scripts.milestone2_perf_common import (  # noqa: E402
    INTERNAL_QUERIES,
    MODEL_CALL_TASK_TYPES,
    ORG_DEFAULT,
    PRE_RM_SHA,
    PROD_DEFAULT,
    RM_MERGE_COMMIT,
    analyze_events,
    chat_timed,
    compare_latency,
    fetch_health,
    latency_summary,
)

RM_MERGE_AT = datetime(2026, 7, 18, 5, 5, 29, tzinfo=timezone.utc)


def _load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for path in (BACKEND / ".env", BACKEND / ".env.operator.local", REPO / ".env"):
        if not path.is_file():
            continue
        try:
            merged.update({k: v for k, v in dotenv_values(path).items() if v})
        except UnicodeDecodeError:
            pass
    merged.update({k: v for k, v in __import__("os").environ.items() if v})
    return merged


def _mint_token(env: dict[str, str], user_id: str, email: str) -> str:
    url = env["SUPABASE_URL"].rstrip("/")
    secret = env["SUPABASE_JWT_SECRET"]
    now = int(time.time())
    return jwt.encode(
        {
            "sub": user_id,
            "email": email,
            "aud": "authenticated",
            "iss": f"{url}/auth/v1",
            "iat": now,
            "exp": now + 3600,
            "role": "authenticated",
        },
        secret,
        algorithm="HS256",
    )


def _aggregate_model_calls(client: Any, org_id: str, since: datetime, until: datetime) -> dict[str, Any]:
    """Aggregate model_calls for assistant-path task types in a time window."""
    rows: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    task_types_found: set[str] = set()

    for task_type in MODEL_CALL_TASK_TYPES:
        try:
            resp = (
                client.table("model_calls")
                .select("id,input_tokens,output_tokens,latency_ms,cache_hit,task_type,created_at")
                .eq("org_id", org_id)
                .eq("task_type", task_type)
                .gte("created_at", since.isoformat())
                .lt("created_at", until.isoformat())
                .limit(500)
                .execute()
            )
            for row in resp.data or []:
                rid = str(row.get("id") or "")
                if rid and rid in seen_ids:
                    continue
                if rid:
                    seen_ids.add(rid)
                rows.append(row)
                if row.get("task_type"):
                    task_types_found.add(str(row["task_type"]))
        except Exception:
            continue

    if not rows:
        return {
            "count": 0,
            "task_types_queried": list(MODEL_CALL_TASK_TYPES),
            "task_types_with_rows": sorted(task_types_found),
            "note": "no model_calls rows in window for known TaskType values",
        }

    input_tokens = [int(r.get("input_tokens") or 0) for r in rows]
    output_tokens = [int(r.get("output_tokens") or 0) for r in rows]
    latencies = [int(r.get("latency_ms") or 0) for r in rows if r.get("latency_ms")]
    cache_hits = sum(1 for r in rows if r.get("cache_hit"))
    by_type: dict[str, int] = {}
    for r in rows:
        tt = str(r.get("task_type") or "unknown")
        by_type[tt] = by_type.get(tt, 0) + 1

    return {
        "count": len(rows),
        "task_types_queried": list(MODEL_CALL_TASK_TYPES),
        "task_types_with_rows": sorted(by_type.keys()),
        "rows_by_task_type": by_type,
        "input_tokens_sum": sum(input_tokens),
        "output_tokens_sum": sum(output_tokens),
        "latency_ms_avg": round(statistics.mean(latencies), 1) if latencies else None,
        "latency_ms_p95": sorted(latencies)[int(len(latencies) * 0.95)] if len(latencies) >= 2 else (latencies[0] if latencies else None),
        "cache_hit_count": cache_hits,
        "cache_hit_rate": round(cache_hits / len(rows), 4) if rows else None,
    }


def _count_connector_invokes(client: Any, org_id: str, since: datetime, until: datetime) -> int:
    try:
        resp = (
            client.table("audit_events")
            .select("id")
            .eq("org_id", org_id)
            .eq("action", "tool.invoke.completed")
            .gte("created_at", since.isoformat())
            .lt("created_at", until.isoformat())
            .limit(500)
            .execute()
        )
        return len(resp.data or [])
    except Exception:
        return -1


def run_audit(args: argparse.Namespace) -> dict[str, Any]:
    env = _load_env()
    for key in ("SUPABASE_URL", "SUPABASE_JWT_SECRET", "SUPABASE_SERVICE_ROLE_KEY"):
        if not env.get(key):
            raise SystemExit(f"Missing {key}")

    from supabase import create_client
    from scripts.smoke_auth import resolve_smoke_actor_and_email

    client = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
    org_id = (args.org_id or env.get("OAUTH_SMOKE_ORG_ID") or ORG_DEFAULT).strip()
    actor, email = resolve_smoke_actor_and_email(client, org_id=org_id, env=env)
    token = _mint_token(env, actor, email)
    base_url = (args.base_url or PROD_DEFAULT).rstrip("/")
    tag = datetime.now(timezone.utc).strftime("%Y%m%d%H%M")

    audit_started = datetime.now(timezone.utc)
    report: dict[str, Any] = {
        "probe": "milestone2_performance_audit",
        "started_at": audit_started.isoformat(),
        "base_url": base_url,
        "org_id": org_id,
        "actor_id": actor,
        "research_manager_merge_at": RM_MERGE_AT.isoformat(),
        "pre_rm_sha": PRE_RM_SHA,
        "rm_merge_commit": RM_MERGE_COMMIT,
        "queries": {},
        "guardrails": {},
        "pass": False,
    }

    report["health"] = fetch_health(base_url)

    latencies: list[int] = []
    internet_violations: list[str] = []
    stop_early_hits: list[str] = []

    for spec in INTERNAL_QUERIES:
        qid = spec["id"]
        message = spec["message"].format(tag=tag)
        http, events, latency_ms = chat_timed(
            base_url=base_url,
            org_id=org_id,
            token=token,
            message=message,
            mode=str(spec.get("mode") or "fast"),
        )
        metrics = analyze_events(events)
        latencies.append(latency_ms)

        checks: dict[str, Any] = {"http": http, "latency_ms": latency_ms}
        if spec.get("expect_no_internet") and metrics.get("internet_ran"):
            checks["internet_guardrail"] = "FAIL"
            internet_violations.append(qid)
        else:
            checks["internet_guardrail"] = "PASS"

        if spec.get("expect_suggest_broaden"):
            checks["suggest_broaden"] = bool(metrics.get("suggest_broaden"))

        if spec.get("expect_stop_early_signal"):
            stopped = metrics.get("skip_external") or metrics.get("confidence_sufficient")
            checks["stop_early_signal"] = bool(stopped)
            if stopped:
                stop_early_hits.append(qid)

        checks["finish_step_count_ok"] = metrics.get("finish_step_count", 99) <= 6
        checks["no_write_tools"] = not any(
            "create" in t.lower() or "write" in t.lower() for t in metrics.get("tool_names") or []
        )

        report["queries"][qid] = {
            "message": message,
            "metrics": metrics,
            "checks": checks,
            "pass": http == 200
            and checks.get("internet_guardrail") == "PASS"
            and checks.get("finish_step_count_ok", True)
            and checks.get("no_write_tools", True),
        }

    audit_finished = datetime.now(timezone.utc)
    report["finished_at"] = audit_finished.isoformat()

    before_start = RM_MERGE_AT - timedelta(days=7)
    after_start = RM_MERGE_AT
    report["model_calls_before_rm"] = _aggregate_model_calls(client, org_id, before_start, RM_MERGE_AT)
    report["model_calls_after_rm"] = _aggregate_model_calls(client, org_id, after_start, audit_finished)
    report["connector_invokes_before_rm"] = _count_connector_invokes(client, org_id, before_start, RM_MERGE_AT)
    report["connector_invokes_after_rm"] = _count_connector_invokes(client, org_id, after_start, audit_finished)
    report["model_calls_during_audit"] = _aggregate_model_calls(client, org_id, audit_started, audit_finished)
    report["connector_invokes_during_audit"] = _count_connector_invokes(
        client, org_id, audit_started, audit_finished
    )

    post_summary = latency_summary(latencies)
    report["latency_summary"] = post_summary

    # Latency guardrail: requires before/after delta (same 5 queries on pre-RM prod tip).
    latency_delta: dict[str, Any] | None = None
    if args.latency_baseline:
        baseline_path = Path(args.latency_baseline)
        if baseline_path.is_file():
            baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
            before_summary = baseline.get("latency_summary") or baseline
            latency_delta = compare_latency(before_summary, post_summary)
            report["latency_baseline_file"] = str(baseline_path)
            report["latency_baseline_git_sha"] = baseline.get("health_git_sha")
            report["latency_delta"] = latency_delta
        else:
            report["latency_delta"] = {
                "direction": "INCONCLUSIVE",
                "latency_guardrail_pass": False,
                "note": f"baseline file not found: {baseline_path}",
            }
    else:
        report["latency_delta"] = {
            "direction": "INCONCLUSIVE",
            "latency_guardrail_pass": False,
            "note": (
                "No pre-RM latency baseline attached. Run "
                "scripts/smoke-milestone2-latency-ab.py --full-ab (or --probe-only on pre-RM tip) "
                "and pass --latency-baseline."
            ),
        }

    ld = report["latency_delta"]
    latency_guardrail_pass = bool(ld.get("latency_guardrail_pass"))

    report["guardrails"] = {
        "no_internet_on_internal_queries": len(internet_violations) == 0,
        "internet_violations": internet_violations,
        "stop_early_observed_on_kb_query": "refund_kb" in stop_early_hits,
        "stop_early_hits": stop_early_hits,
        "stop_early_sse_gap": "refund_kb" not in stop_early_hits,
        "latency_delta_verified": latency_guardrail_pass,
        "latency_delta_direction": ld.get("direction"),
        "availability_p95_under_120s": (post_summary.get("p95_ms") or 0) < 120_000,
        "all_queries_http_200": all(q["checks"]["http"] == 200 for q in report["queries"].values()),
    }

    before_tokens = (report["model_calls_before_rm"].get("input_tokens_sum") or 0) + (
        report["model_calls_before_rm"].get("output_tokens_sum") or 0
    )
    after_tokens = (report["model_calls_after_rm"].get("input_tokens_sum") or 0) + (
        report["model_calls_after_rm"].get("output_tokens_sum") or 0
    )
    token_measured = report["model_calls_before_rm"].get("count", 0) > 0 or report["model_calls_after_rm"].get("count", 0) > 0
    report["token_comparison"] = {
        "before_rm_total_tokens": before_tokens,
        "after_rm_total_tokens": after_tokens,
        "before_rm_window": f"{before_start.isoformat()} .. {RM_MERGE_AT.isoformat()}",
        "after_rm_window": f"{after_start.isoformat()} .. {audit_finished.isoformat()}",
        "measured": token_measured,
        "status": "MEASURED" if token_measured else "INCONCLUSIVE",
        "note": (
            "Org-wide aggregates by TaskType enum — not isolated to audit queries. "
            "Requires model_calls rows in both windows."
        ),
    }

    cache_before = report["model_calls_before_rm"].get("cache_hit_rate")
    cache_after = report["model_calls_after_rm"].get("cache_hit_rate")
    report["cache_comparison"] = {
        "before_rm_cache_hit_rate": cache_before,
        "after_rm_cache_hit_rate": cache_after,
        "status": "MEASURED" if token_measured else "INCONCLUSIVE",
    }

    query_pass = all(q.get("pass") for q in report["queries"].values())
    guard_pass = all(
        [
            report["guardrails"]["no_internet_on_internal_queries"],
            report["guardrails"]["all_queries_http_200"],
            latency_guardrail_pass,
        ]
    )
    report["pass"] = query_pass and guard_pass
    direction = ld.get("direction") or "INCONCLUSIVE"
    if report["pass"]:
        report["verdict"] = f"PASS — latency {direction}"
    elif not latency_guardrail_pass and direction == "INCONCLUSIVE":
        report["verdict"] = "INCONCLUSIVE — latency before/after not verified"
    elif direction == "REGRESSION":
        report["verdict"] = "FAIL — latency regression vs pre-RM baseline"
    else:
        report["verdict"] = "FAIL"
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Milestone 2 prod performance audit")
    parser.add_argument("--base-url", default=PROD_DEFAULT)
    parser.add_argument("--org-id", default=None)
    parser.add_argument(
        "--latency-baseline",
        default=None,
        help="JSON from smoke-milestone2-latency-ab probe on pre-RM prod tip",
    )
    parser.add_argument(
        "--json",
        dest="json_path",
        default=str(REPO / "docs/delivery/milestone2-performance-audit-latest.json"),
    )
    args = parser.parse_args()
    report = run_audit(args)
    text = json.dumps(report, indent=2, default=str)
    print(text)
    if args.json_path:
        out = Path(args.json_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
    print(f"\nVERDICT: {report.get('verdict')}")
    return 0 if report.get("pass") else 1


if __name__ == "__main__":
    raise SystemExit(main())
