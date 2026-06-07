"""Per-agent LLM and connector cost attribution (STA-92)."""
from __future__ import annotations

from collections import defaultdict
from typing import Any


def aggregate_agent_costs(
    *,
    usage_rows: list[dict[str, Any]],
    default_agent_label: str = "unassigned",
) -> dict[str, Any]:
    by_agent: dict[str, dict[str, float]] = defaultdict(lambda: {"llmCostUsd": 0.0, "connectorCostUsd": 0.0, "totalCostUsd": 0.0, "events": 0})
    by_department: dict[str, float] = defaultdict(float)
    by_workflow: dict[str, float] = defaultdict(float)

    for row in usage_rows:
        metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        agent_id = str(metadata.get("agent_id") or metadata.get("agentId") or default_agent_label)
        department = str(metadata.get("department") or metadata.get("department_id") or "general")
        workflow_id = str(metadata.get("workflow_id") or metadata.get("workflowId") or "none")
        amount = float(row.get("cost_usd") or row.get("amount_usd") or 0.0)
        category = str(row.get("category") or metadata.get("category") or "llm")
        bucket = by_agent[agent_id]
        bucket["events"] += 1
        if category == "connector":
            bucket["connectorCostUsd"] += amount
        else:
            bucket["llmCostUsd"] += amount
        bucket["totalCostUsd"] = round(bucket["llmCostUsd"] + bucket["connectorCostUsd"], 4)
        by_department[department] += amount
        by_workflow[workflow_id] += amount

    return {
        "byAgent": by_agent,
        "byDepartment": dict(by_department),
        "byWorkflow": dict(by_workflow),
        "totalCostUsd": round(sum(item["totalCostUsd"] for item in by_agent.values()), 4),
    }
