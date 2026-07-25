"""Per-node reliability signals on the canvas (Phase 5.2) + cross-workflow patterns (5.3).

Reuses Module A ``intelligence_outcome_events`` — no parallel tracking store.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


def node_reliability_for_workflow(
    client: Any,
    *,
    org_id: str,
    workflow_id: str,
    limit_runs: int = 25,
) -> dict[str, Any]:
    """Return per-step failure rates from recent run steps for one workflow."""
    signals: list[dict[str, Any]] = []
    try:
        runs = (
            client.table("workflow_runs")
            .select("id, status, created_at")
            .eq("org_id", org_id)
            .eq("workflow_id", workflow_id)
            .order("created_at", desc=True)
            .limit(limit_runs)
            .execute()
        )
        run_ids = [str(r["id"]) for r in (runs.data or []) if r.get("id")]
    except Exception as exc:  # noqa: BLE001
        logger.debug("node_reliability_runs_skipped workflow_id=%s error=%s", workflow_id, exc)
        return {"workflowId": workflow_id, "nodes": [], "crossWorkflow": []}

    if not run_ids:
        return {"workflowId": workflow_id, "nodes": [], "crossWorkflow": []}

    # workflow_steps table (legacy) — step_key / name / status
    tallies: dict[str, dict[str, int]] = defaultdict(lambda: {"ok": 0, "fail": 0})
    labels: dict[str, str] = {}
    try:
        for rid in run_ids[:limit_runs]:
            steps = (
                client.table("workflow_steps")
                .select("id, step_key, name, status, error")
                .eq("run_id", rid)
                .execute()
            )
            for step in steps.data or []:
                key = str(step.get("step_key") or step.get("id") or "")
                if not key:
                    continue
                labels[key] = str(step.get("name") or key)
                status = str(step.get("status") or "").lower()
                if status in {"failed", "error"}:
                    tallies[key]["fail"] += 1
                elif status in {"completed", "success", "succeeded"}:
                    tallies[key]["ok"] += 1
    except Exception as exc:  # noqa: BLE001
        logger.debug("node_reliability_steps_skipped workflow_id=%s error=%s", workflow_id, exc)

    for key, counts in tallies.items():
        total = counts["ok"] + counts["fail"]
        if total < 2 or counts["fail"] == 0:
            continue
        signals.append(
            {
                "nodeKey": key,
                "label": labels.get(key, key),
                "failed": counts["fail"],
                "total": total,
                "message": f"{counts['fail']} of last {total} runs failed here",
            }
        )
    signals.sort(key=lambda s: s["failed"] / max(1, s["total"]), reverse=True)
    return {
        "workflowId": workflow_id,
        "nodes": signals[:12],
        "crossWorkflow": cross_workflow_failure_patterns(client, org_id=org_id),
    }


def cross_workflow_failure_patterns(
    client: Any,
    *,
    org_id: str,
    limit: int = 80,
) -> list[dict[str, Any]]:
    """Aggregate recurring failure reasons across multiple workflows (Phase 5.3)."""
    try:
        resp = (
            client.table("intelligence_outcome_events")
            .select("outcome_event, workflow_id, metadata, created_at")
            .eq("org_id", org_id)
            .in_("outcome_event", ["workflow_failed", "run_failed", "execution_failed"])
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        rows = list(resp.data or [])
    except Exception as exc:  # noqa: BLE001
        logger.debug("cross_workflow_patterns_skipped org_id=%s error=%s", org_id, exc)
        return []

    by_reason: dict[str, dict[str, Any]] = {}
    for row in rows:
        meta = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        err = str(meta.get("error") or meta.get("error_summary") or "").strip()
        if not err:
            continue
        # Normalize rate-limit / auth classes lightly
        reason = err[:160]
        lowered = reason.lower()
        if "rate limit" in lowered or "429" in lowered:
            reason = "Connector rate limit"
        elif "auth" in lowered or "401" in lowered or "403" in lowered:
            reason = "Connector auth / permission error"
        bucket = by_reason.setdefault(
            reason,
            {"reason": reason, "count": 0, "workflowIds": set()},
        )
        bucket["count"] += 1
        wf = row.get("workflow_id")
        if wf:
            bucket["workflowIds"].add(str(wf))

    out: list[dict[str, Any]] = []
    for bucket in by_reason.values():
        wfs = list(bucket["workflowIds"])
        if len(wfs) < 2 or bucket["count"] < 3:
            continue
        out.append(
            {
                "reason": bucket["reason"],
                "count": bucket["count"],
                "workflowCount": len(wfs),
                "workflowIds": wfs[:8],
                "message": (
                    f"{bucket['reason']} recurred {bucket['count']} times "
                    f"across {len(wfs)} workflows"
                ),
            }
        )
    out.sort(key=lambda r: r["count"], reverse=True)
    return out[:5]
