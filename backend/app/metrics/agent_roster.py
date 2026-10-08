"""Agents roster: per-agent daily work, health and goal links for Team / List / Work map.

Sources of record (no sample data):
- ``agent_jobs``: agent assignments; the agent is ``payload.agent_id`` (agent tasks)
  or ``payload.operator_id`` (operator tasks). Same attribution as ``home_reports``.
- ``agent_identity_records``: trust level + approval overrides. An agent's writes
  pass an approval gate unless it is read only or explicitly allowed to auto-run
  writes (the same rule as ``deriveAutonomyLabel`` in the web app). A missing
  record fails closed to "needs approval".
- ``goals`` + ``goal_plans.required_agents``: which agents a goal depends on.

Aggregation is pure (``aggregate_agent_roster``) so it is testable without a database.
"""
from __future__ import annotations

import re
from collections.abc import Callable
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

from app.core.sql_aggregates import fetch_all_rows
from app.core.ttl_cache import TTLCache, ttl_from_env
from app.metrics.home_reports import _norm_status, _parse_ts, _rate

DAYS = 14
SUCCESS_WINDOW_DAYS = 7
BLOCKED_WINDOW_DAYS = 7
REASON_MAX = 110

agent_roster_cache = TTLCache(ttl_from_env("AGENT_ROSTER_CACHE_TTL_SECONDS", 30.0), max_entries=2048)

# Error text that is a trace or a payload, not a sentence a person can act on.
_TECHNICAL = re.compile(
    r"(traceback|exception|errno|\bstack\b|[{}\[\]<>]|https?://|\b[45]\d\d\b|_error\b|\w+Error\b|\w+\.\w+\()",
    re.IGNORECASE,
)


def blocked_reason(status: str, error: Any) -> str:
    """One plain sentence for why the agent's latest task stopped."""
    if status == "paused":
        return "Paused and waiting for you to continue it"
    text = str(error or "").strip().splitlines()[0].strip() if error else ""
    if not text or _TECHNICAL.search(text):
        return "Its last task did not finish"
    text = text.rstrip(".")
    if len(text) > REASON_MAX:
        text = text[: REASON_MAX - 1].rstrip() + "…"
    return text[0].upper() + text[1:]


def needs_approval_gate(identity: dict[str, Any] | None) -> bool:
    """True when the agent's writes wait for a person's OK (fails closed)."""
    if not identity:
        return True
    trust = str(identity.get("trust_level") or "write_with_approval")
    if trust == "read_only":
        return False
    kinds = identity.get("allowed_action_kinds")
    if isinstance(kinds, list) and kinds and not any(k in ("write", "delete") for k in kinds):
        return False
    overrides = identity.get("approval_rule_overrides") or {}
    auto_writes = isinstance(overrides, dict) and overrides.get("write") == "auto_run"
    return not (trust == "autonomous" and auto_writes)


def _agent_key(job: dict[str, Any]) -> str:
    return str(job.get("agent_id") or job.get("operator_id") or "").strip()


def aggregate_agent_roster(
    *,
    now: datetime,
    tz_offset_min: int,
    jobs: list[dict[str, Any]],
    identities: dict[str, dict[str, Any]],
    goals: list[dict[str, Any]],
    plans: list[dict[str, Any]],
) -> dict[str, Any]:
    tz = timezone(timedelta(minutes=tz_offset_min))
    today = now.astimezone(tz).replace(hour=0, minute=0, second=0, microsecond=0)
    first = today - timedelta(days=DAYS - 1)
    success_from = now - timedelta(days=SUCCESS_WINDOW_DAYS)
    blocked_from = now - timedelta(days=BLOCKED_WINDOW_DAYS)

    per: dict[str, dict[str, Any]] = {}

    def slot(key: str) -> dict[str, Any]:
        if key not in per:
            per[key] = {
                "tasksToday": 0,
                "failedToday": 0,
                "runningNow": 0,
                "completed7d": 0,
                "failed7d": 0,
                "lastActiveAt": None,
                "daily": [0] * DAYS,
                "_latest": None,
            }
        return per[key]

    for job in jobs:
        key = _agent_key(job)
        created = _parse_ts(job.get("created_at"))
        if not key or created is None:
            continue
        s = slot(key)
        status = _norm_status(job.get("status"))
        finished = _parse_ts(job.get("finished_at"))
        stamp = finished or created
        if status == "running":
            s["runningNow"] += 1
        if status in ("completed", "failed"):
            local_day = stamp.astimezone(tz).replace(hour=0, minute=0, second=0, microsecond=0)
            idx = (local_day - first).days
            if status == "completed" and 0 <= idx < DAYS:
                s["daily"][idx] += 1
            if idx == DAYS - 1:
                s["tasksToday" if status == "completed" else "failedToday"] += 1
            if stamp >= success_from:
                s["completed7d" if status == "completed" else "failed7d"] += 1
        active = _parse_ts(job.get("started_at")) or created
        last = finished or active
        if s["lastActiveAt"] is None or last > s["lastActiveAt"]:
            s["lastActiveAt"] = last
        latest = s["_latest"]
        if latest is None or created > latest[0]:
            s["_latest"] = (created, status, job.get("error"), str(job.get("id") or ""))

    agents: dict[str, Any] = {}
    for key, s in per.items():
        created, status, error, job_id = s.pop("_latest")
        blocked = None
        if status in ("failed", "paused") and created >= blocked_from:
            blocked = {
                "kind": status,
                "reason": blocked_reason(status, error),
                "jobId": job_id or None,
                "at": created.isoformat(),
            }
        agents[key] = {
            "tasksToday": s["tasksToday"],
            "failedToday": s["failedToday"],
            "runningNow": s["runningNow"],
            "successRateToday": _rate(s["tasksToday"], s["failedToday"]),
            "successRate7d": _rate(s["completed7d"], s["failed7d"]),
            "lastActiveAt": s["lastActiveAt"].isoformat() if s["lastActiveAt"] else None,
            "daily": s["daily"],
            "blocked": blocked,
        }

    latest_plan: dict[str, dict[str, Any]] = {}
    for plan in plans:
        goal_id = str(plan.get("goal_id") or "")
        if not goal_id:
            continue
        prev = latest_plan.get(goal_id)
        if prev is None or str(plan.get("created_at") or "") > str(prev.get("created_at") or ""):
            latest_plan[goal_id] = plan

    goal_rows = []
    for goal in goals:
        status = str(goal.get("status") or "draft")
        if status in ("cancelled", "completed"):
            continue
        plan = latest_plan.get(str(goal.get("id")))
        required = plan.get("required_agents") if plan else None
        goal_rows.append(
            {
                "id": str(goal.get("id")),
                "objective": str(goal.get("objective") or "").strip(),
                "status": status,
                "department": goal.get("department"),
                "priority": goal.get("priority"),
                "connectedSystems": [str(s) for s in (goal.get("connected_systems") or [])],
                "agentIds": [str(a) for a in (required or [])],
            }
        )

    return {
        "generatedAt": now.isoformat(),
        "days": [(first + timedelta(days=i)).isoformat() for i in range(DAYS)],
        "agents": agents,
        "approvalGate": {key: needs_approval_gate(row) for key, row in identities.items()},
        "goals": goal_rows,
    }


def _rows(build: Callable[[], Any]) -> list[dict[str, Any]]:
    try:
        return fetch_all_rows(build)
    except Exception:  # noqa: BLE001 — a missing optional table must not break the roster
        return []


def build_agent_roster(client: Any, org_id: str, tz_offset_min: int = 0) -> dict[str, Any]:
    tz_offset_min = max(-840, min(840, int(tz_offset_min)))
    cache_key = (org_id, tz_offset_min)
    cached = agent_roster_cache.get(cache_key)
    if cached is not None:
        return cached
    token = agent_roster_cache.token()

    now = datetime.now(UTC)
    lo = (now - timedelta(days=DAYS + 1)).isoformat()
    jobs = _rows(
        lambda: client.table("agent_jobs")
        .select(
            "id,status,error,created_at,started_at,finished_at,"
            "agent_id:payload->>agent_id,operator_id:payload->>operator_id"
        )
        .eq("org_id", org_id).gte("created_at", lo).order("id")
    )
    identity_rows = _rows(
        lambda: client.table("agent_identity_records")
        .select("id,agent_id,trust_level,allowed_action_kinds,approval_rule_overrides")
        .eq("org_id", org_id).order("id")
    )
    identities = {str(r["agent_id"]): r for r in identity_rows if r.get("agent_id")}
    goals = _rows(
        lambda: client.table("goals")
        .select("id,objective,status,department,priority,connected_systems,created_at")
        .eq("org_id", org_id).order("id")
    )
    plans = _rows(
        lambda: client.table("goal_plans")
        .select("id,goal_id,required_agents,created_at")
        .eq("org_id", org_id).order("id")
    )

    data = aggregate_agent_roster(
        now=now,
        tz_offset_min=tz_offset_min,
        jobs=jobs,
        identities=identities,
        goals=goals,
        plans=plans,
    )
    agent_roster_cache.set(cache_key, data, tags=(("org", org_id),), token=token)
    return data
