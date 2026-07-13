"""Connector write/ops metrics from audit_events tool.invoke* rows.

Aggregates requested / completed / failed by vendor + action for admin ops
observability. Spikes when failedRate > 0.10 and sample size n >= 10.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from app.config import Settings, get_settings
from app.workflows.repository import get_supabase_client

SPIKE_FAILED_RATE = 0.10
SPIKE_MIN_N = 10
_EVENT_LIMIT = 5000


def _event_metadata(row: dict[str, Any]) -> dict[str, Any]:
    meta = row.get("metadata")
    if isinstance(meta, dict):
        return meta
    details = row.get("details")
    if isinstance(details, dict):
        return details
    return {}


def _tool_action(row: dict[str, Any]) -> str | None:
    audit_action = str(row.get("action") or "")
    if not audit_action.startswith("tool.invoke"):
        return None
    meta = _event_metadata(row)
    tool_action = str(meta.get("action") or "").strip()
    return tool_action or None


def _vendor_from_action(tool_action: str) -> str:
    if "." not in tool_action:
        return tool_action or "unknown"
    return tool_action.split(".", 1)[0]


def _fetch_tool_invoke_events(
    client: Any,
    org_id: str,
    *,
    since_iso: str,
    limit: int = _EVENT_LIMIT,
) -> list[dict[str, Any]]:
    result = (
        client.table("audit_events")
        .select("id,action,metadata,created_at")
        .eq("org_id", org_id)
        .gte("created_at", since_iso)
        .like("action", "tool.invoke%")
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return list(result.data or [])


def aggregate_connector_ops_events(
    events: list[dict[str, Any]],
    *,
    period_days: int,
    since_iso: str,
    org_id: str | None = None,
) -> dict[str, Any]:
    """Pure aggregation of tool.invoke* audit rows into per-vendor/action stats."""
    buckets: dict[tuple[str, str], dict[str, Any]] = defaultdict(
        lambda: {
            "requested": 0,
            "completed": 0,
            "failed": 0,
            "error_codes": Counter(),
        }
    )

    for row in events:
        tool_action = _tool_action(row)
        if not tool_action:
            continue
        vendor = _vendor_from_action(tool_action)
        key = (vendor, tool_action)
        audit_action = str(row.get("action") or "")
        bucket = buckets[key]
        if audit_action == "tool.invoke.requested":
            bucket["requested"] += 1
        elif audit_action == "tool.invoke.completed":
            bucket["completed"] += 1
        elif audit_action == "tool.invoke.failed":
            bucket["failed"] += 1
            meta = _event_metadata(row)
            code = str(meta.get("error_code") or meta.get("errorCode") or "unknown").strip() or "unknown"
            bucket["error_codes"][code] += 1

    rows: list[dict[str, Any]] = []
    spikes: list[dict[str, Any]] = []

    for (vendor, action), counts in buckets.items():
        requested = int(counts["requested"])
        completed = int(counts["completed"])
        failed = int(counts["failed"])
        # Prefer requested as n when present; otherwise terminal outcomes.
        n = requested if requested > 0 else completed + failed
        denom = max(n, 1)
        success_rate = round(completed / denom, 4)
        failed_rate = round(failed / denom, 4)
        top_errors = [
            {"code": code, "count": count}
            for code, count in counts["error_codes"].most_common(5)
        ]
        row = {
            "vendor": vendor,
            "action": action,
            "requested": requested,
            "completed": completed,
            "failed": failed,
            "n": n,
            "successRate": success_rate,
            "failedRate": failed_rate,
            "topErrorCodes": top_errors,
            "spike": bool(failed_rate > SPIKE_FAILED_RATE and n >= SPIKE_MIN_N),
        }
        rows.append(row)
        if row["spike"]:
            spikes.append(
                {
                    "vendor": vendor,
                    "action": action,
                    "n": n,
                    "failed": failed,
                    "failedRate": failed_rate,
                    "topErrorCodes": top_errors,
                }
            )

    rows.sort(key=lambda r: (r["failed"], r["requested"]), reverse=True)
    spikes.sort(key=lambda s: s["failedRate"], reverse=True)

    return {
        "orgId": org_id,
        "periodDays": period_days,
        "since": since_iso,
        "spikeThreshold": {"failedRate": SPIKE_FAILED_RATE, "minN": SPIKE_MIN_N},
        "totalEvents": len(events),
        "rowCount": len(rows),
        "spikeCount": len(spikes),
        "hasSpike": len(spikes) > 0,
        "spikes": spikes,
        "rows": rows,
    }


async def load_connector_ops_metrics(
    org_id: str,
    *,
    period_days: int = 7,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Load org-scoped connector invoke ops metrics for the admin dashboard."""
    active = settings or get_settings()
    days = max(1, min(int(period_days or 7), 90))
    since = datetime.now(timezone.utc) - timedelta(days=days)
    since_iso = since.isoformat()
    client = get_supabase_client(active)
    try:
        events = _fetch_tool_invoke_events(client, org_id, since_iso=since_iso)
    except Exception:
        events = []
    return aggregate_connector_ops_events(
        events,
        period_days=days,
        since_iso=since_iso,
        org_id=org_id,
    )
