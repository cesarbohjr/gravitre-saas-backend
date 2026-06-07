"""Agent workforce analytics (STA-91)."""
from __future__ import annotations

from collections import Counter
from typing import Any


def build_workforce_analytics(
    *,
    agent_jobs: list[dict[str, Any]],
    audit_logs: list[dict[str, Any]],
    handoff_events: list[dict[str, Any]],
) -> dict[str, Any]:
    status_counts = Counter(str(row.get("status") or "unknown") for row in agent_jobs)
    tool_events = [row for row in audit_logs if str(row.get("action") or "").startswith("tool.invoke")]
    tool_success = len([row for row in tool_events if str(row.get("action") or "").endswith("completed")])
    tool_failed = len([row for row in tool_events if str(row.get("action") or "").endswith("failed")])
    approval_wait = [
        row
        for row in audit_logs
        if "approval" in str(row.get("action") or "").lower() or "interrupt" in str(row.get("action") or "").lower()
    ]
    sla_breaches = len([row for row in agent_jobs if str(row.get("status") or "") == "timeout"])
    return {
        "tasksCompleted": status_counts.get("completed", 0),
        "tasksFailed": status_counts.get("failed", 0),
        "tasksRunning": status_counts.get("running", 0),
        "handoffs": len(handoff_events),
        "toolSuccessRate": round(tool_success / max(tool_success + tool_failed, 1) * 100, 2),
        "approvalWaitEvents": len(approval_wait),
        "slaBreaches": sla_breaches,
    }
