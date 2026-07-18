"""Shared helpers for Milestone 2 performance / latency probes on prod."""
from __future__ import annotations

import json
import re
import statistics
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from typing import Any

PROD_DEFAULT = "https://gravitre-saas-backend-production.up.railway.app"
ORG_DEFAULT = "cbbf993b-b22f-41ce-964b-1fc25e0dd9ea"

# Research Manager landed on main @ 2026-07-18T05:05:29Z (PR #165, commit 4eb6adbe).
RM_MERGE_COMMIT = "4eb6adbe"
PRE_RM_SHA = "09e57595"  # parent of RM merge — last prod tip without Research Manager

INTERNAL_QUERIES: list[dict[str, Any]] = [
    {
        "id": "connectors_fast",
        "message": "What connectors are connected? (perf-audit {tag})",
        "mode": "fast",
        "expect_no_internet": True,
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

# Values written by ModelRouter._log_model_call (TaskType enum + embedding rows).
MODEL_CALL_TASK_TYPES: tuple[str, ...] = (
    "classification",
    "intent_detection",
    "workflow_planning",
    "decision_reasoning",
    "agent_debate",
    "summarization",
    "content_generation",
    "rag_answering",
    "optimization_analysis",
    "embedding",
)


def parse_sse(raw: str) -> list[dict[str, Any]]:
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


def latest_cascade(events: list[dict[str, Any]]) -> dict[str, Any]:
    for ev in reversed(events):
        for container in (ev, ev.get("data") if isinstance(ev.get("data"), dict) else {}):
            if not isinstance(container, dict):
                continue
            cascade = container.get("researchCascade") or container.get("research_cascade")
            if isinstance(cascade, dict) and cascade:
                return cascade
    return {}


def analyze_events(events: list[dict[str, Any]]) -> dict[str, Any]:
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

    cascade = latest_cascade(events)
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
        "research_manager": cascade.get("research_manager"),
    }


def chat_timed(
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
            return int(resp.status), parse_sse(raw), latency_ms
    except urllib.error.HTTPError as exc:
        latency_ms = int((time.perf_counter() - started) * 1000)
        return exc.code, parse_sse(exc.read().decode("utf-8", errors="replace")), latency_ms


def fetch_health(base_url: str) -> dict[str, Any]:
    req = urllib.request.Request(f"{base_url.rstrip('/')}/health", method="GET")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def latency_summary(samples: list[int]) -> dict[str, Any]:
    if not samples:
        return {"samples": [], "p50_ms": None, "p95_ms": None, "max_ms": None, "mean_ms": None}
    ordered = sorted(samples)
    p95_idx = min(len(ordered) - 1, int(len(ordered) * 0.95))
    return {
        "samples": samples,
        "p50_ms": int(statistics.median(ordered)),
        "p95_ms": ordered[p95_idx],
        "max_ms": max(ordered),
        "mean_ms": round(statistics.mean(ordered), 1),
    }


def compare_latency(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    """Compare pre/post latency summaries; classify delta for Milestone 2 guardrail."""
    b50 = before.get("p50_ms")
    b95 = before.get("p95_ms")
    a50 = after.get("p50_ms")
    a95 = after.get("p95_ms")

    def _delta(b: int | None, a: int | None) -> dict[str, Any]:
        if b is None or a is None:
            return {"before_ms": b, "after_ms": a, "delta_ms": None, "delta_pct": None}
        delta = a - b
        pct = round((delta / b) * 100, 2) if b else None
        return {"before_ms": b, "after_ms": a, "delta_ms": delta, "delta_pct": pct}

    p50 = _delta(b50, a50)
    p95 = _delta(b95, a95)

    # Jitter band: allow up to 10% or 2s (p95) / 1.5s (p50), whichever is larger in absolute terms.
    def _within_band(b: int | None, a: int | None, abs_floor: int) -> bool | None:
        if b is None or a is None:
            return None
        allowed = max(int(b * 0.10), abs_floor)
        return (a - b) <= allowed

    p50_flat = _within_band(b50, a50, 1500)
    p95_flat = _within_band(b95, a95, 2000)

    if p50_flat is None or p95_flat is None:
        direction = "INCONCLUSIVE"
        guardrail_pass = False
    elif (a50 or 0) < (b50 or 0) and (a95 or 0) < (b95 or 0):
        direction = "IMPROVED"
        guardrail_pass = True
    elif p50_flat and p95_flat:
        direction = "FLAT"
        guardrail_pass = True
    else:
        direction = "REGRESSION"
        guardrail_pass = False

    return {
        "p50": p50,
        "p95": p95,
        "direction": direction,
        "latency_guardrail_pass": guardrail_pass,
        "jitter_band_note": "FLAT if p50 within +max(10%, 1500ms) and p95 within +max(10%, 2000ms)",
    }


def run_latency_probe(
    *,
    base_url: str,
    org_id: str,
    token: str,
    tag: str | None = None,
    include_metrics: bool = False,
) -> dict[str, Any]:
    stamp = tag or datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    health = fetch_health(base_url)
    started_at = datetime.now(timezone.utc).isoformat()
    per_query: dict[str, Any] = {}
    latencies: list[int] = []

    for spec in INTERNAL_QUERIES:
        qid = spec["id"]
        message = spec["message"].format(tag=stamp)
        http, events, latency_ms = chat_timed(
            base_url=base_url,
            org_id=org_id,
            token=token,
            message=message,
            mode=str(spec.get("mode") or "fast"),
        )
        latencies.append(latency_ms)
        entry: dict[str, Any] = {"message": message, "http": http, "latency_ms": latency_ms}
        if include_metrics:
            entry["metrics"] = analyze_events(events)
        per_query[qid] = entry

    summary = latency_summary(latencies)
    return {
        "probe": "milestone2_latency_probe",
        "started_at": started_at,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "base_url": base_url,
        "org_id": org_id,
        "tag": stamp,
        "health_git_sha": health.get("git_sha"),
        "queries": per_query,
        "latency_summary": summary,
    }
