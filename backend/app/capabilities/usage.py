"""Usage observability for portable capabilities.

Stores identifiers and bounded metadata only. Prompt text, skill contents,
connector credentials, and tool arguments are never written here.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any


def record_reasoning_selection(
    client: Any,
    *,
    org_id: str,
    package_ids: list[str],
    user_id: str | None = None,
    conversation_id: str | None = None,
    surface: str | None = None,
) -> None:
    unique = [value for value in dict.fromkeys(str(v) for v in package_ids) if value]
    if not unique:
        return
    rows = [
        {
            "org_id": org_id,
            "package_id": package_id,
            "event_type": "selected_for_reasoning",
            "user_id": user_id or None,
            "conversation_id": conversation_id or None,
            "surface": surface or None,
            "metadata": {"contentStored": False},
        }
        for package_id in unique[:5]
    ]
    try:
        client.table("capability_usage_events").insert(rows).execute()
    except Exception:
        # Telemetry must never break the reasoning path during rolling deploys.
        return


def usage_summary(
    client: Any,
    *,
    org_id: str,
    days: int = 30,
) -> dict[str, Any]:
    window_days = max(1, min(int(days), 90))
    since = datetime.now(timezone.utc) - timedelta(days=window_days)
    try:
        response = (
            client.table("capability_usage_events")
            .select("package_id,event_type,surface,created_at")
            .eq("org_id", org_id)
            .gte("created_at", since.isoformat())
            .execute()
        )
        rows = list(response.data or [])
    except Exception:
        rows = []

    package_counts: Counter[str] = Counter()
    reasoning = 0
    executions = 0
    surfaces: Counter[str] = Counter()
    for row in rows:
        package_id = str(row.get("package_id") or "")
        if package_id:
            package_counts[package_id] += 1
        event_type = str(row.get("event_type") or "")
        if event_type == "selected_for_reasoning":
            reasoning += 1
        elif event_type == "mcp_tool_executed":
            executions += 1
        surface = str(row.get("surface") or "")
        if surface:
            surfaces[surface] += 1

    package_names: dict[str, str] = {}
    if package_counts:
        try:
            package_rows = (
                client.table("capability_packages")
                .select("id,name")
                .eq("org_id", org_id)
                .in_("id", list(package_counts))
                .execute()
            )
            package_names = {
                str(row.get("id")): str(row.get("name") or "Capability")
                for row in (package_rows.data or [])
            }
        except Exception:
            package_names = {}

    top = [
        {
            "packageId": package_id,
            "name": package_names.get(package_id, "Capability"),
            "events": count,
        }
        for package_id, count in package_counts.most_common(10)
    ]
    return {
        "windowDays": window_days,
        "totalEvents": len(rows),
        "reasoningSelections": reasoning,
        "mcpExecutions": executions,
        "topCapabilities": top,
        "surfaces": dict(surfaces),
        "contentStored": False,
    }
