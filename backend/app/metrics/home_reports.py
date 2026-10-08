"""Home dashboard "Reports" view: run analytics stacked by agent.

Sources of record (no sample data):
- ``agent_jobs``: agent assignments; the agent is ``payload.agent_id`` (agent tasks)
  or ``payload.operator_id`` (operator tasks). Duration is ``finished_at - started_at``.
- ``workflow_runs``: workflow executions. They carry no agent, so they form their
  own "Workflows" series. Duration is ``completed_at - created_at``.
- ``model_calls.cost_usd``: model spend.
- ``run_approvals`` + ``approvals.reviewed_at``: decisions resolved.
- ``intelligence_outcome_events``: the lead funnel (Growth pack outcome events).

Aggregation is pure (``aggregate_home_reports``) so it is testable without a database.
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from statistics import median
from typing import Any

from app.core.sql_aggregates import fetch_all_rows
from app.core.ttl_cache import TTLCache, ttl_from_env

RANGES: dict[str, int] = {"7d": 7, "30d": 30, "90d": 90}
WORKFLOWS_KEY = "workflows"
# Same assumption the design states on the card: a completed task saves ~4 minutes.
MINUTES_SAVED_PER_TASK = 4
SPARK_POINTS = 12
_DOW = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
_MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# Growth pack outcome events that make up the lead pipeline, in funnel order.
FUNNEL_STAGES: tuple[tuple[str, str], ...] = (
    ("outreach_enrolled", "Enrolled in sequence"),
    ("meeting_follow_up_prepared", "Engaged"),
    ("lead_qualified", "Qualified"),
    ("opportunity_created", "Meeting booked"),
)

home_reports_cache = TTLCache(ttl_from_env("HOME_REPORTS_CACHE_TTL_SECONDS", 30.0), max_entries=2048)


def _parse_ts(value: Any) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        ts = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)


def _seconds_between(start: Any, end: Any) -> float | None:
    a, b = _parse_ts(start), _parse_ts(end)
    if a is None or b is None:
        return None
    secs = (b - a).total_seconds()
    return secs if secs >= 0 else None


def _rate(completed: int, failed: int) -> float | None:
    done = completed + failed
    return round(completed / done * 100, 1) if done else None


def _norm_status(status: Any) -> str:
    s = str(status or "").lower()
    if s in {"completed", "succeeded", "success", "done"}:
        return "completed"
    if s in {"failed", "error", "cancelled", "canceled", "timed_out"}:
        return "failed" if s != "cancelled" and s != "canceled" else "cancelled"
    if s in {"running", "processing", "claimed"}:
        return "running"
    return s or "queued"


def normalize_runs(jobs: list[dict[str, Any]], workflow_runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One row per run: series key, status, created_at, duration seconds."""
    out: list[dict[str, Any]] = []
    for job in jobs:
        agent_id = str(job.get("agent_id") or job.get("operator_id") or "").strip()
        out.append(
            {
                "key": agent_id or WORKFLOWS_KEY,
                "status": _norm_status(job.get("status")),
                "created_at": _parse_ts(job.get("created_at")),
                "duration": _seconds_between(job.get("started_at"), job.get("finished_at")),
            }
        )
    for run in workflow_runs:
        out.append(
            {
                "key": WORKFLOWS_KEY,
                "status": _norm_status(run.get("status")),
                "created_at": _parse_ts(run.get("created_at")),
                "duration": _seconds_between(run.get("created_at"), run.get("completed_at")),
            }
        )
    return [r for r in out if r["created_at"] is not None]


def _summary(runs: list[dict[str, Any]], spend: float, decisions: int) -> dict[str, Any]:
    completed = sum(1 for r in runs if r["status"] == "completed")
    failed = sum(1 for r in runs if r["status"] == "failed")
    durations = [r["duration"] for r in runs if r["duration"] is not None and r["status"] == "completed"]
    return {
        "runs": len(runs),
        "completed": completed,
        "failed": failed,
        "successRate": _rate(completed, failed),
        "medianDurationSec": round(median(durations), 2) if durations else None,
        "hoursSaved": round(completed * MINUTES_SAVED_PER_TASK / 60, 1),
        "modelSpendUsd": round(spend, 2),
        "decisionsResolved": decisions,
    }


def _delta(cur: float | None, prev: float | None, *, relative: bool = True) -> float | None:
    if cur is None or prev is None:
        return None
    if not relative:
        return round(cur - prev, 1)
    if prev == 0:
        return None
    return round((cur - prev) / prev * 100, 1)


def aggregate_home_reports(
    *,
    range_key: str,
    now: datetime,
    tz_offset_min: int,
    runs: list[dict[str, Any]],
    prev_runs: list[dict[str, Any]],
    agent_names: dict[str, dict[str, Any]],
    agent_count: int,
    spend: float,
    prev_spend: float,
    model_count: int,
    decisions: int,
    prev_decisions: int,
    funnel_counts: dict[str, int],
) -> dict[str, Any]:
    days = RANGES[range_key]
    tz = timezone(timedelta(minutes=tz_offset_min))
    local_now = now.astimezone(tz)
    weekly = range_key == "90d"
    n = 13 if weekly else days
    step = 7 if weekly else 1
    today = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    first = today - timedelta(days=(n - 1) * step)

    keys_by_volume: dict[str, int] = {}
    for r in runs:
        keys_by_volume[r["key"]] = keys_by_volume.get(r["key"], 0) + 1
    ordered = sorted(keys_by_volume, key=lambda k: (k == WORKFLOWS_KEY, -keys_by_volume[k]))

    buckets: list[dict[str, Any]] = []
    for i in range(n):
        start = first + timedelta(days=i * step)
        label = _DOW[start.weekday()] if n == 7 else f"{_MON[start.month - 1]} {start.day}"
        show_axis = n == 7 or ((n - 1 - i) % 5 == 0 if n == 30 else i % 3 == 0)
        buckets.append(
            {"start": start.isoformat(), "label": label, "axis": label if show_axis else "",
             "bySeries": {}, "total": 0, "completed": 0, "failed": 0, "_durations": []}
        )

    heat = [[0] * 12 for _ in range(7)]
    per_key: dict[str, dict[str, Any]] = {
        k: {"runs": 0, "completed": 0, "failed": 0, "durations": [], "last": None, "spark": [0] * SPARK_POINTS}
        for k in ordered
    }
    span_start = first
    span_secs = max((today + timedelta(days=step) - span_start).total_seconds(), 1.0)
    exec_secs = 0.0
    for r in runs:
        local = r["created_at"].astimezone(tz)
        idx = int((local.replace(hour=0, minute=0, second=0, microsecond=0) - first).days // step)
        if 0 <= idx < n:
            b = buckets[idx]
            b["bySeries"][r["key"]] = b["bySeries"].get(r["key"], 0) + 1
            b["total"] += 1
            if r["status"] == "completed":
                b["completed"] += 1
                if r["duration"] is not None:
                    b["_durations"].append(r["duration"])
            elif r["status"] == "failed":
                b["failed"] += 1
        heat[local.weekday()][local.hour // 2] += 1
        s = per_key[r["key"]]
        s["runs"] += 1
        if r["status"] == "completed":
            s["completed"] += 1
        elif r["status"] == "failed":
            s["failed"] += 1
        if r["duration"] is not None:
            s["durations"].append(r["duration"])
            if r["key"] != WORKFLOWS_KEY:
                exec_secs += r["duration"]
        if s["last"] is None or r["created_at"] > s["last"]:
            s["last"] = r["created_at"]
        pos = int((local - span_start).total_seconds() / span_secs * SPARK_POINTS)
        s["spark"][min(max(pos, 0), SPARK_POINTS - 1)] += 1

    for b in buckets:
        b["successRate"] = _rate(b["completed"], b["failed"])
        durations = b.pop("_durations")
        b["medianDurationSec"] = round(median(durations), 2) if durations else None

    series = []
    for k in ordered:
        s = per_key[k]
        meta = agent_names.get(k) or {}
        series.append(
            {
                "key": k,
                "agentId": None if k == WORKFLOWS_KEY else k,
                "name": "Workflows" if k == WORKFLOWS_KEY else (meta.get("name") or "Agent"),
                "model": None if k == WORKFLOWS_KEY else meta.get("model"),
                "runs": s["runs"],
                "completed": s["completed"],
                "failed": s["failed"],
                "successRate": _rate(s["completed"], s["failed"]),
                "latencyP50Sec": round(median(s["durations"]), 2) if s["durations"] else None,
                "lastRunAt": s["last"].isoformat() if s["last"] else None,
                "spark": s["spark"],
            }
        )

    cur = _summary(runs, spend, decisions)
    prev = _summary(prev_runs, prev_spend, prev_decisions)
    capacity_secs = agent_count * days * 86400
    util = round(min(exec_secs / capacity_secs, 1.0) * 100, 1) if capacity_secs else None

    funnel = [{"key": key, "name": name, "value": int(funnel_counts.get(key, 0))} for key, name in FUNNEL_STAGES]

    return {
        "range": range_key,
        "generatedAt": now.isoformat(),
        "weekly": weekly,
        "totals": {**cur, "modelCount": model_count, "agentCount": agent_count},
        "deltas": {
            "runs": _delta(cur["runs"], prev["runs"]),
            "successRate": _delta(cur["successRate"], prev["successRate"], relative=False),
            "medianDurationSec": _delta(cur["medianDurationSec"], prev["medianDurationSec"]),
            "hoursSaved": _delta(cur["hoursSaved"], prev["hoursSaved"]),
            "modelSpendUsd": _delta(cur["modelSpendUsd"], prev["modelSpendUsd"]),
            "decisionsResolved": _delta(cur["decisionsResolved"], prev["decisionsResolved"]),
        },
        "series": series,
        "buckets": buckets,
        "heat": [{"day": _DOW[d], "cells": heat[d]} for d in range(7)],
        "utilization": {
            "percent": util,
            "executingHours": round(exec_secs / 3600, 1),
            "idleHours": round(max(capacity_secs - exec_secs, 0) / 3600, 1) if capacity_secs else None,
            "agentCount": agent_count,
        },
        "funnel": funnel,
    }


def _rows(build: Callable[[], Any]) -> list[dict[str, Any]]:
    try:
        return fetch_all_rows(build)
    except Exception:  # noqa: BLE001 — a missing optional table must not break the dashboard
        return []


def build_home_reports(client: Any, org_id: str, range_key: str, tz_offset_min: int = 0) -> dict[str, Any]:
    if range_key not in RANGES:
        raise ValueError("Invalid range")
    tz_offset_min = max(-840, min(840, int(tz_offset_min)))
    cache_key = (org_id, range_key, tz_offset_min)
    cached = home_reports_cache.get(cache_key)
    if cached is not None:
        return cached
    token = home_reports_cache.token()

    now = datetime.now(timezone.utc)
    days = RANGES[range_key]
    start = now - timedelta(days=days)
    prev_start = start - timedelta(days=days)
    lo, mid, hi = prev_start.isoformat(), start.isoformat(), now.isoformat()

    jobs = _rows(
        lambda: client.table("agent_jobs")
        .select("id,status,created_at,started_at,finished_at,agent_id:payload->>agent_id,operator_id:payload->>operator_id")
        .eq("org_id", org_id).gte("created_at", lo).lt("created_at", hi).order("id")
    )
    wf_runs = _rows(
        lambda: client.table("workflow_runs")
        .select("id,status,created_at,completed_at")
        .eq("org_id", org_id).gte("created_at", lo).lt("created_at", hi).order("id")
    )
    all_runs = normalize_runs(jobs, wf_runs)
    runs = [r for r in all_runs if r["created_at"] >= start]
    prev_runs = [r for r in all_runs if r["created_at"] < start]

    calls = _rows(
        lambda: client.table("model_calls")
        .select("id,cost_usd,model_name,created_at")
        .eq("org_id", org_id).gte("created_at", lo).lt("created_at", hi).order("id")
    )
    spend = prev_spend = 0.0
    models: set[str] = set()
    for c in calls:
        cost = float(c.get("cost_usd") or 0)
        if (c.get("created_at") or "") >= mid:
            spend += cost
            if c.get("model_name"):
                models.add(str(c["model_name"]))
        else:
            prev_spend += cost

    run_approvals = _rows(
        lambda: client.table("run_approvals").select("id,created_at")
        .eq("org_id", org_id).gte("created_at", lo).lt("created_at", hi).order("id")
    )
    approvals = _rows(
        lambda: client.table("approvals").select("id,reviewed_at")
        .eq("org_id", org_id).gte("reviewed_at", lo).lt("reviewed_at", hi).order("id")
    )
    decision_ts = [str(r.get("created_at") or "") for r in run_approvals] + [
        str(r.get("reviewed_at") or "") for r in approvals
    ]
    decisions = sum(1 for ts in decision_ts if ts >= mid)
    prev_decisions = len(decision_ts) - decisions

    outcome_rows = _rows(
        lambda: client.table("intelligence_outcome_events").select("id,outcome_event")
        .eq("org_id", org_id).in_("outcome_event", [k for k, _ in FUNNEL_STAGES])
        .gte("created_at", mid).lt("created_at", hi).order("id")
    )
    funnel_counts: dict[str, int] = {}
    for row in outcome_rows:
        ev = str(row.get("outcome_event") or "")
        funnel_counts[ev] = funnel_counts.get(ev, 0) + 1

    agent_rows = _rows(lambda: client.table("agents").select("id,name,model").eq("org_id", org_id).order("id"))
    operator_rows = _rows(
        lambda: client.table("operators").select("id,name,deleted_at").eq("org_id", org_id).order("id")
    )
    names: dict[str, dict[str, Any]] = {}
    for op in operator_rows:
        if op.get("deleted_at"):
            continue
        names[str(op["id"])] = {"name": op.get("name"), "model": None}
    for ag in agent_rows:
        names[str(ag["id"])] = {"name": ag.get("name"), "model": ag.get("model")}

    data = aggregate_home_reports(
        range_key=range_key,
        now=now,
        tz_offset_min=tz_offset_min,
        runs=runs,
        prev_runs=prev_runs,
        agent_names=names,
        agent_count=len(names),
        spend=spend,
        prev_spend=prev_spend,
        model_count=len(models),
        decisions=decisions,
        prev_decisions=prev_decisions,
        funnel_counts=funnel_counts,
    )
    home_reports_cache.set(cache_key, data, tags=(("org", org_id),), token=token)
    return data
