#!/usr/bin/env python3
"""Milestone 2 — live performance audit on prod (internal-only queries).

Measures latency, SSE proxies, Research Manager stop-early signals, internet/connector
guardrails, and compares model_calls aggregates before vs after Research Manager deploy.

Usage:
  python scripts/smoke-milestone2-performance-audit.py
  python scripts/smoke-milestone2-performance-audit.py --json docs/delivery/milestone2-performance-audit-latest.json
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import jwt
from dotenv import dotenv_values

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(REPO))

PROD_DEFAULT = "https://gravitre-saas-backend-production.up.railway.app"
ORG_DEFAULT = "cbbf993b-b22f-41ce-964b-1fc25e0dd9ea"
# Research Manager merged to main @ 2026-07-18T05:05:29Z (PR #165)
RM_MERGE_AT = datetime(2026, 7, 18, 5, 5, 29, tzinfo=timezone.utc)

INTERNAL_QUERIES: list[dict[str, Any]] = [
    {
        "id": "connectors_fast",
        "message": "What connectors are connected? (perf-audit {tag})",
        "mode": "fast",
        "expect_no_internet": True,
        "expect_no_external_scope": True,
    },
    {
        "id": "refund_kb",
        "message": "What is our refund policy? Use internal knowledge only. (perf-audit {tag})",
        "mode": "fast",
        "expect_no_internet": True,
        "expect_stop_early_signal": True,
    },
    {
        "id": "thin_internal",
        "message": (
            "What is the Q3 2027 revenue for fictional subsidiary Zephyr Dynamics in Antarctica? "
            "Internal org knowledge only. (perf-audit {tag})"
        ),
        "mode": "fast",
        "expect_no_internet": True,
        "expect_suggest_broaden": True,
    },
    {
        "id": "fast_one_liner",
        "message": "Reply in one sentence: what mode are you in? (perf-audit {tag})",
        "mode": "fast",
        "expect_no_internet": True,
    },
    {
        "id": "connector_status_only",
        "message": "List connected integrations and their health. No writes. (perf-audit {tag})",
        "mode": "fast",
        "expect_no_internet": True,
    },
]


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


def _parse_sse(raw: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for block in re.split(r"\n\n+", raw):
        data_lines = [ln[5:].lstrip() for ln in block.splitlines() if ln.startswith("data:")]
        if not data_lines:
            continue
        payload = "\n".join(data_lines).strip()
        if payload in ("", "[DONE]"):
            continue
        try:
            events.append(json.loads(payload))
        except json.JSONDecodeError:
            events.append({"_raw": payload[:300]})
    return events


def _latest_cascade(events: list[dict[str, Any]]) -> dict[str, Any]:
    for ev in reversed(events):
        for container in (ev, ev.get("data") if isinstance(ev.get("data"), dict) else {}):
            if not isinstance(container, dict):
                continue
            cascade = container.get("researchCascade") or container.get("research_cascade")
            if isinstance(cascade, dict) and cascade:
                return cascade
    return {}


def _analyze_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    tool_names: list[str] = []
    finish_steps = 0
    text_len = 0
    intel_count = 0
    context_chars = 0
    usage_tokens: list[int] = []

    for ev in events:
        et = str(ev.get("type") or "")
        if et == "finish-step":
            finish_steps += 1
        if et == "text-delta":
            text_len += len(str(ev.get("delta") or ""))
        if et in {"tool-input-available", "tool-input-start"}:
            name = str(ev.get("toolName") or ev.get("name") or "")
            if name:
                tool_names.append(name)
        if et == "data-intelligence":
            intel_count += 1
            data = ev.get("data") if isinstance(ev.get("data"), dict) else {}
            ctx = data.get("contextProfile") if isinstance(data.get("contextProfile"), dict) else {}
            if ctx:
                context_chars = max(context_chars, len(json.dumps(ctx, default=str)))
            usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
            total = usage.get("total_tokens") or usage.get("totalTokens")
            if total is not None:
                usage_tokens.append(int(total))

    cascade = _latest_cascade(events)
    rm_meta = {
        "skip_external": cascade.get("skip_external"),
        "cascade_stopped_at": cascade.get("cascade_stopped_at"),
        "confidence_sufficient": cascade.get("confidence_sufficient"),
        "research_manager": cascade.get("research_manager"),
    }

    internet = cascade.get("internet_research") if isinstance(cascade.get("internet_research"), dict) else {}

    return {
        "sse_event_count": len(events),
        "finish_step_count": finish_steps,
        "data_intelligence_count": intel_count,
        "tool_names": tool_names,
        "tool_call_count": len(tool_names),
        "response_text_chars": text_len,
        "context_profile_chars": context_chars,
        "usage_tokens_reported": usage_tokens,
        "usage_tokens_max": max(usage_tokens) if usage_tokens else None,
        "research_cascade": cascade,
        "internet_ran": bool(internet.get("ran")),
        "skip_external": cascade.get("skip_external"),
        "cascade_stopped_at": cascade.get("cascade_stopped_at"),
        "confidence_sufficient": cascade.get("confidence_sufficient"),
        "suggest_broaden": cascade.get("suggest_broaden"),
        "research_manager_meta": rm_meta,
    }


def _chat_timed(
    *,
    base_url: str,
    org_id: str,
    token: str,
    message: str,
    mode: str,
) -> tuple[int, list[dict[str, Any]], int]:
    body = {
        "messages": [{"role": "user", "content": message}],
        "org_id": org_id,
        "tools": ["knowledge_base", "agent_status", "connector_status"],
        "mode": mode,
        "conversation_id": str(uuid.uuid4()),
    }
    url = f"{base_url.rstrip('/')}/api/assistant/chat"
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("X-Org-Id", org_id)
    req.add_header("X-Environment", "production")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "text/event-stream")
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            latency_ms = int((time.perf_counter() - started) * 1000)
            return int(resp.status), _parse_sse(raw), latency_ms
    except urllib.error.HTTPError as exc:
        latency_ms = int((time.perf_counter() - started) * 1000)
        return exc.code, _parse_sse(exc.read().decode("utf-8", errors="replace")), latency_ms


def _aggregate_model_calls(client: Any, org_id: str, since: datetime, until: datetime) -> dict[str, Any]:
    """Aggregate model_calls for assistant-ish task types in a time window."""
    task_types = ("assistant", "chat", "agent", "react")
    rows: list[dict[str, Any]] = []
    for task_type in task_types:
        try:
            resp = (
                client.table("model_calls")
                .select("input_tokens,output_tokens,latency_ms,cache_hit,task_type,created_at")
                .eq("org_id", org_id)
                .eq("task_type", task_type)
                .gte("created_at", since.isoformat())
                .lt("created_at", until.isoformat())
                .limit(500)
                .execute()
            )
            rows.extend(resp.data or [])
        except Exception:
            continue
    if not rows:
        return {"count": 0, "note": "no model_calls rows in window (may be task_type naming)"}

    input_tokens = [int(r.get("input_tokens") or 0) for r in rows]
    output_tokens = [int(r.get("output_tokens") or 0) for r in rows]
    latencies = [int(r.get("latency_ms") or 0) for r in rows if r.get("latency_ms")]
    cache_hits = sum(1 for r in rows if r.get("cache_hit"))

    return {
        "count": len(rows),
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
        "queries": {},
        "guardrails": {},
        "pass": False,
    }

    req = urllib.request.Request(f"{base_url}/health", method="GET")
    with urllib.request.urlopen(req, timeout=30) as resp:
        report["health"] = json.loads(resp.read().decode("utf-8"))

    latencies: list[int] = []
    internet_violations: list[str] = []
    stop_early_hits: list[str] = []

    for spec in INTERNAL_QUERIES:
        qid = spec["id"]
        message = spec["message"].format(tag=tag)
        http, events, latency_ms = _chat_timed(
            base_url=base_url,
            org_id=org_id,
            token=token,
            message=message,
            mode=str(spec.get("mode") or "fast"),
        )
        metrics = _analyze_events(events)
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
            "conversation_id": None,
            "metrics": metrics,
            "checks": checks,
            "pass": http == 200
            and checks.get("internet_guardrail") == "PASS"
            and checks.get("finish_step_count_ok", True)
            and checks.get("no_write_tools", True),
        }

    audit_finished = datetime.now(timezone.utc)
    report["finished_at"] = audit_finished.isoformat()

    # Historical before/after from model_calls (prod DB, same org)
    before_start = RM_MERGE_AT - timedelta(days=7)
    after_start = RM_MERGE_AT
    report["model_calls_before_rm"] = _aggregate_model_calls(client, org_id, before_start, RM_MERGE_AT)
    report["model_calls_after_rm"] = _aggregate_model_calls(client, org_id, after_start, audit_finished)
    report["connector_invokes_before_rm"] = _count_connector_invokes(client, org_id, before_start, RM_MERGE_AT)
    report["connector_invokes_after_rm"] = _count_connector_invokes(
        client, org_id, after_start, audit_finished
    )

    # Live audit window (this run only)
    report["model_calls_during_audit"] = _aggregate_model_calls(
        client, org_id, audit_started, audit_finished
    )
    report["connector_invokes_during_audit"] = _count_connector_invokes(
        client, org_id, audit_started, audit_finished
    )

    p50 = int(statistics.median(latencies)) if latencies else None
    p95 = sorted(latencies)[int(len(latencies) * 0.95)] if len(latencies) >= 2 else (latencies[0] if latencies else None)

    report["latency_summary"] = {
        "samples": latencies,
        "p50_ms": p50,
        "p95_ms": p95,
        "max_ms": max(latencies) if latencies else None,
    }

    report["guardrails"] = {
        "no_internet_on_internal_queries": len(internet_violations) == 0,
        "internet_violations": internet_violations,
        "stop_early_observed_on_kb_query": "refund_kb" in stop_early_hits,
        "stop_early_hits": stop_early_hits,
        "latency_p95_under_120s": (p95 or 0) < 120_000,
        "all_queries_http_200": all(q["checks"]["http"] == 200 for q in report["queries"].values()),
    }

    before_tokens = (report["model_calls_before_rm"].get("input_tokens_sum") or 0) + (
        report["model_calls_before_rm"].get("output_tokens_sum") or 0
    )
    after_tokens = (report["model_calls_after_rm"].get("input_tokens_sum") or 0) + (
        report["model_calls_after_rm"].get("output_tokens_sum") or 0
    )
    report["token_comparison"] = {
        "before_rm_total_tokens": before_tokens,
        "after_rm_total_tokens": after_tokens,
        "before_rm_window": f"{before_start.isoformat()} .. {RM_MERGE_AT.isoformat()}",
        "after_rm_window": f"{after_start.isoformat()} .. {audit_finished.isoformat()}",
        "note": (
            "Org-wide aggregates — not isolated to audit queries. "
            "Use for trend only; live query latencies are the primary guardrail signal."
        ),
    }

    query_pass = all(q.get("pass") for q in report["queries"].values())
    guard_pass = all(
        [
            report["guardrails"]["no_internet_on_internal_queries"],
            report["guardrails"]["latency_p95_under_120s"],
            report["guardrails"]["all_queries_http_200"],
        ]
    )
    report["pass"] = query_pass and guard_pass
    report["verdict"] = "PASS" if report["pass"] else "FAIL"
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Milestone 2 prod performance audit")
    parser.add_argument("--base-url", default=PROD_DEFAULT)
    parser.add_argument("--org-id", default=None)
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
