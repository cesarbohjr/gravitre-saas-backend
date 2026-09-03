"""Per-agent ROI from measured spend + operational counts + labeled estimates.

Honesty (STA-286 / Module C):
- Measured: model_calls.cost_usd, completed jobs, tool/outcome action counts.
- Estimate: hours saved and labor value (task-type / duration heuristics).
- not_configured: revenue influenced unless a real monetary outcome field exists.

Never invent customer prices or present estimates as measured facts.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

# Manual-equivalent minutes by agent_jobs.kind when wall-clock duration is missing.
# These are ESTIMATES of human effort replaced by automation — not measured time-on-task.
DEFAULT_MANUAL_MINUTES_BY_KIND: dict[str, float] = {
    "operator_task": 20.0,
    "agent_task": 20.0,
    "chat": 10.0,
    "research": 25.0,
    "default": 15.0,
}

# When a job has started_at/finished_at, estimate human minutes as
# max(kind_default, wall_clock_minutes * factor). Factor is an ESTIMATE heuristic.
HUMAN_DURATION_MULTIPLIER = 5.0

# Default fully-loaded labor rate used ONLY when org.settings.roi_labor_usd_per_hour
# is unset. Always labeled as an estimate default — not a billed SKU.
DEFAULT_LABOR_USD_PER_HOUR = 45.0

METHODOLOGY = (
    "Tasks completed and actions executed are operational counts from agent_jobs / "
    "outcome events. Agent cost is measured SUM(model_calls.cost_usd) for the period. "
    "Hours saved and labor value are ESTIMATES from task-type defaults and (when present) "
    "job wall-clock × a human-overhead multiplier — not ground-truth time-on-task (STA-289). "
    "Revenue influenced is shown only when outcome metadata carries a real monetary amount; "
    "otherwise not_configured. ROI multiple = estimated labor value ÷ measured cost."
)


def _parse_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def period_window(period_days: int, *, now: datetime | None = None) -> tuple[datetime, datetime]:
    days = max(1, min(int(period_days or 30), 366))
    end = now or datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    return start, end


def resolve_labor_usd_per_hour(org_settings: dict[str, Any] | None) -> tuple[float, str]:
    settings = org_settings if isinstance(org_settings, dict) else {}
    raw = settings.get("roi_labor_usd_per_hour")
    if raw is None:
        raw = settings.get("labor_usd_per_hour")
    try:
        rate = float(raw) if raw is not None else None
    except (TypeError, ValueError):
        rate = None
    if rate is not None and rate > 0:
        return round(rate, 4), "org_settings"
    return DEFAULT_LABOR_USD_PER_HOUR, "default_estimate"


def _agent_id_from_job(row: dict[str, Any]) -> str:
    payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
    for key in ("agent_id", "agentId", "operator_id", "operatorId"):
        value = payload.get(key)
        if value:
            return str(value)
    return "unassigned"


def estimate_hours_for_job(row: dict[str, Any]) -> dict[str, Any]:
    """Estimate human hours replaced by one completed job (honestly labeled)."""
    kind = str(row.get("kind") or "default").strip() or "default"
    base_minutes = DEFAULT_MANUAL_MINUTES_BY_KIND.get(kind, DEFAULT_MANUAL_MINUTES_BY_KIND["default"])
    started = _parse_dt(row.get("started_at"))
    finished = _parse_dt(row.get("finished_at")) or _parse_dt(row.get("updated_at"))
    wall_minutes: float | None = None
    method = "task_type_default"
    if started and finished and finished >= started:
        wall_minutes = max((finished - started).total_seconds() / 60.0, 0.0)
        estimated_minutes = max(base_minutes, wall_minutes * HUMAN_DURATION_MULTIPLIER)
        method = "wall_clock_x_human_multiplier"
    else:
        estimated_minutes = base_minutes
    return {
        "estimatedMinutes": round(estimated_minutes, 2),
        "estimatedHours": round(estimated_minutes / 60.0, 4),
        "method": method,
        "kind": kind,
        "wallClockMinutes": round(wall_minutes, 2) if wall_minutes is not None else None,
        "taskTypeDefaultMinutes": base_minutes,
        "humanDurationMultiplier": HUMAN_DURATION_MULTIPLIER,
        "provenance": "estimate",
    }


def extract_revenue_amount(metadata: Any) -> float | None:
    """Return a real monetary amount from outcome metadata, else None (never invent)."""
    if not isinstance(metadata, dict):
        return None
    for key in (
        "amount_usd",
        "revenue_usd",
        "deal_value_usd",
        "influenced_revenue_usd",
        "revenueInfluencedUsd",
        "amountUsd",
        "dealValueUsd",
    ):
        raw = metadata.get(key)
        try:
            value = float(raw)
        except (TypeError, ValueError):
            continue
        if value > 0:
            return round(value, 4)
    return None


def _metric(
    *,
    value: Any,
    provenance: str,
    label: str,
    unit: str | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    return {
        "label": label,
        "value": value,
        "unit": unit,
        "provenance": provenance,
        "honesty_ok": True,
        "note": note,
    }


def build_agent_roi_report(
    *,
    org_id: str,
    agents: list[dict[str, Any]],
    model_call_rows: list[dict[str, Any]],
    job_rows: list[dict[str, Any]],
    outcome_rows: list[dict[str, Any]],
    org_settings: dict[str, Any] | None,
    period_days: int,
    period_start: datetime,
    period_end: datetime,
) -> dict[str, Any]:
    labor_rate, labor_source = resolve_labor_usd_per_hour(org_settings)
    agent_names = {
        str(a.get("id")): str(a.get("name") or a.get("title") or a.get("id") or "Agent")
        for a in agents
        if a.get("id")
    }

    cost_by_agent: dict[str, float] = defaultdict(float)
    calls_by_agent: dict[str, int] = defaultdict(int)
    for row in model_call_rows:
        aid = str(row.get("agent_id") or "unassigned")
        try:
            cost = float(row.get("cost_usd") or 0.0)
        except (TypeError, ValueError):
            cost = 0.0
        cost_by_agent[aid] += cost
        calls_by_agent[aid] += 1

    jobs_by_agent: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in job_rows:
        if str(row.get("status") or "") != "completed":
            continue
        jobs_by_agent[_agent_id_from_job(row)].append(row)

    actions_by_agent: dict[str, int] = defaultdict(int)
    revenue_by_agent: dict[str, float] = defaultdict(float)
    revenue_events_by_agent: dict[str, int] = defaultdict(int)
    for row in outcome_rows:
        aid = str(row.get("agent_id") or "unassigned")
        event_type = str(row.get("outcome_event") or row.get("event_type") or "")
        if event_type in {
            "connector_action_executed",
            "workflow_executed",
            "tool_invoked",
            "action_executed",
        }:
            actions_by_agent[aid] += 1
        amount = extract_revenue_amount(row.get("metadata") or row.get("payload"))
        if amount is not None:
            revenue_by_agent[aid] += amount
            revenue_events_by_agent[aid] += 1

    agent_ids = set(agent_names) | set(cost_by_agent) | set(jobs_by_agent) | set(actions_by_agent) | set(
        revenue_by_agent
    )
    # Prefer known agents first, then activity-only ids.
    ordered_ids = [str(a.get("id")) for a in agents if a.get("id")]
    for aid in sorted(agent_ids):
        if aid not in ordered_ids:
            ordered_ids.append(aid)

    per_agent: list[dict[str, Any]] = []
    org_tasks = 0
    org_actions = 0
    org_cost = 0.0
    org_hours = 0.0
    org_labor = 0.0
    org_revenue = 0.0
    org_revenue_events = 0

    for aid in ordered_ids:
        if aid == "unassigned" and not (
            cost_by_agent.get(aid) or jobs_by_agent.get(aid) or actions_by_agent.get(aid)
        ):
            continue
        jobs = jobs_by_agent.get(aid, [])
        hours = 0.0
        hour_methods: dict[str, int] = defaultdict(int)
        for job in jobs:
            est = estimate_hours_for_job(job)
            hours += float(est["estimatedHours"])
            hour_methods[str(est["method"])] += 1
        tasks = len(jobs)
        actions = int(actions_by_agent.get(aid, 0))
        # Prefer outcome action counts; fall back to completed jobs as actions when sparse.
        if actions == 0 and tasks > 0:
            actions = tasks
        cost = round(float(cost_by_agent.get(aid, 0.0)), 6)
        labor = round(hours * labor_rate, 4)
        revenue = round(float(revenue_by_agent.get(aid, 0.0)), 4)
        revenue_events = int(revenue_events_by_agent.get(aid, 0))
        roi_multiple = round(labor / cost, 4) if cost > 0 and labor > 0 else None

        org_tasks += tasks
        org_actions += actions
        org_cost += cost
        org_hours += hours
        org_labor += labor
        org_revenue += revenue
        org_revenue_events += revenue_events

        per_agent.append(
            {
                "agentId": aid,
                "agentName": agent_names.get(aid, aid if aid != "unassigned" else "Unassigned"),
                "tasksCompleted": _metric(
                    value=tasks,
                    provenance="operational",
                    label="Tasks completed (operational)",
                    unit="count",
                    note="Completed agent_jobs in period.",
                ),
                "actionsExecuted": _metric(
                    value=actions,
                    provenance="operational",
                    label="Actions executed (operational)",
                    unit="count",
                    note="Outcome/action events; falls back to completed jobs when outcome rows are sparse.",
                ),
                "agentCostUsd": _metric(
                    value=cost,
                    provenance="measured",
                    label="Agent cost (measured)",
                    unit="usd",
                    note="SUM(model_calls.cost_usd) for this agent_id in period.",
                ),
                "modelCallCount": calls_by_agent.get(aid, 0),
                "estimatedHoursSaved": _metric(
                    value=round(hours, 4),
                    provenance="estimate",
                    label="Estimated hours saved",
                    unit="hours",
                    note=(
                        f"Heuristic from job kind defaults and optional wall-clock × "
                        f"{HUMAN_DURATION_MULTIPLIER}x. Methods={dict(hour_methods)}. Not STA-289 ground truth."
                    ),
                ),
                "estimatedLaborValueUsd": _metric(
                    value=labor,
                    provenance="estimate",
                    label="Estimated labor value",
                    unit="usd",
                    note=(
                        f"estimatedHoursSaved × labor rate ${labor_rate}/hr "
                        f"(source={labor_source}). Estimate — not billed SKU."
                    ),
                ),
                "revenueInfluencedUsd": _metric(
                    value=revenue if revenue_events > 0 else None,
                    provenance="measured" if revenue_events > 0 else "not_configured",
                    label="Revenue influenced",
                    unit="usd",
                    note=(
                        f"Sum of outcome metadata monetary fields ({revenue_events} events)."
                        if revenue_events > 0
                        else "No verified monetary amount on outcome events — not fabricated."
                    ),
                ),
                "roiMultiple": _metric(
                    value=roi_multiple,
                    provenance="estimate" if roi_multiple is not None else "insufficient_data",
                    label="ROI multiple (est. labor ÷ measured cost)",
                    unit="x",
                    note=(
                        "Numerator is estimated labor value; denominator is measured model_calls cost."
                        if roi_multiple is not None
                        else "Requires measured cost > 0 and estimated labor value > 0."
                    ),
                ),
            }
        )

    org_roi = round(org_labor / org_cost, 4) if org_cost > 0 and org_labor > 0 else None
    return {
        "orgId": org_id,
        "periodDays": period_days,
        "periodStart": period_start.isoformat(),
        "periodEnd": period_end.isoformat(),
        "methodology": METHODOLOGY,
        "laborUsdPerHour": {
            "value": labor_rate,
            "source": labor_source,
            "provenance": "estimate" if labor_source == "default_estimate" else "org_settings",
            "note": (
                "Org settings.roi_labor_usd_per_hour"
                if labor_source == "org_settings"
                else f"Default estimate ${DEFAULT_LABOR_USD_PER_HOUR}/hr — not a product price SKU."
            ),
        },
        "orgTotals": {
            "tasksCompleted": _metric(
                value=org_tasks,
                provenance="operational",
                label="Tasks completed (operational)",
                unit="count",
            ),
            "actionsExecuted": _metric(
                value=org_actions,
                provenance="operational",
                label="Actions executed (operational)",
                unit="count",
            ),
            "agentCostUsd": _metric(
                value=round(org_cost, 6),
                provenance="measured",
                label="Agent cost (measured)",
                unit="usd",
            ),
            "estimatedHoursSaved": _metric(
                value=round(org_hours, 4),
                provenance="estimate",
                label="Estimated hours saved",
                unit="hours",
            ),
            "estimatedLaborValueUsd": _metric(
                value=round(org_labor, 4),
                provenance="estimate",
                label="Estimated labor value",
                unit="usd",
            ),
            "revenueInfluencedUsd": _metric(
                value=round(org_revenue, 4) if org_revenue_events > 0 else None,
                provenance="measured" if org_revenue_events > 0 else "not_configured",
                label="Revenue influenced",
                unit="usd",
                note=(
                    f"{org_revenue_events} outcome events with monetary metadata."
                    if org_revenue_events > 0
                    else "No verified monetary outcome amounts — not fabricated."
                ),
            ),
            "roiMultiple": _metric(
                value=org_roi,
                provenance="estimate" if org_roi is not None else "insufficient_data",
                label="ROI multiple (est. labor ÷ measured cost)",
                unit="x",
            ),
        },
        "agents": per_agent,
        "honesty": {
            "measuredFields": ["agentCostUsd"],
            "operationalFields": ["tasksCompleted", "actionsExecuted"],
            "estimateFields": ["estimatedHoursSaved", "estimatedLaborValueUsd", "roiMultiple"],
            "notConfiguredUnlessEvidence": ["revenueInfluencedUsd"],
            "moduleC": True,
            "sta286": True,
        },
    }


def fetch_agent_roi(
    client: Any,
    org_id: str,
    *,
    period_days: int = 30,
    agent_id: str | None = None,
) -> dict[str, Any]:
    start, end = period_window(period_days)
    start_iso = start.isoformat()
    end_iso = end.isoformat()

    org_row = (
        client.table("organizations")
        .select("id,settings")
        .eq("id", org_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    org_settings = (org_row[0].get("settings") if org_row else None) or {}

    agents_resp = (
        client.table("agents")
        .select("id,name")
        .eq("org_id", org_id)
        .execute()
    )
    agents = agents_resp.data or []
    # Also include operators as agent-like identities when present.
    try:
        ops = (
            client.table("operators")
            .select("id,name")
            .eq("org_id", org_id)
            .execute()
            .data
            or []
        )
        known = {str(a.get("id")) for a in agents}
        for op in ops:
            oid = str(op.get("id") or "")
            if oid and oid not in known:
                agents.append({"id": oid, "name": op.get("name") or oid})
    except Exception:
        pass

    if agent_id:
        agents = [a for a in agents if str(a.get("id")) == agent_id] or [
            {"id": agent_id, "name": agent_id}
        ]

    model_q = (
        client.table("model_calls")
        .select("id,agent_id,cost_usd,created_at")
        .eq("org_id", org_id)
        .gte("created_at", start_iso)
        .lt("created_at", end_iso)
    )
    if agent_id:
        model_q = model_q.eq("agent_id", agent_id)
    model_rows = model_q.limit(5000).execute().data or []

    jobs_q = (
        client.table("agent_jobs")
        .select("id,status,kind,payload,created_at,started_at,finished_at,updated_at")
        .eq("org_id", org_id)
        .gte("created_at", start_iso)
        .lt("created_at", end_iso)
    )
    job_rows = jobs_q.limit(5000).execute().data or []
    if agent_id:
        job_rows = [r for r in job_rows if _agent_id_from_job(r) == agent_id]

    outcome_rows: list[dict[str, Any]] = []
    try:
        out_q = (
            client.table("intelligence_outcome_events")
            .select("id,agent_id,outcome_event,event_type,metadata,payload,created_at")
            .eq("org_id", org_id)
            .gte("created_at", start_iso)
            .lt("created_at", end_iso)
        )
        if agent_id:
            out_q = out_q.eq("agent_id", agent_id)
        outcome_rows = out_q.limit(5000).execute().data or []
    except Exception:
        outcome_rows = []

    return build_agent_roi_report(
        org_id=org_id,
        agents=agents,
        model_call_rows=model_rows,
        job_rows=job_rows,
        outcome_rows=outcome_rows,
        org_settings=org_settings if isinstance(org_settings, dict) else {},
        period_days=period_days,
        period_start=start,
        period_end=end,
    )
