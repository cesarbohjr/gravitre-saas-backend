"""Customer integration health score for CS dashboards (STA-124)."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from app.workflows.audit import write_audit_event

logger = logging.getLogger(__name__)

AUDIT_INTEGRATION_HEALTH_SNAPSHOT = "integration.health.snapshot"
RESOURCE_TYPE_INTEGRATION_HEALTH = "integration_health"

DEFAULT_LOOKBACK_DAYS = 30
DIMENSION_WEIGHTS = {
    "connectorsLive": 0.25,
    "workflowSuccessRate": 0.25,
    "agentUtilization": 0.25,
    "approvalLatency": 0.25,
}

GRADE_THRESHOLDS = (
    (85, "healthy"),
    (65, "at_risk"),
    (0, "critical"),
)


class IntegrationHealthError(Exception):
    code = "INTEGRATION_HEALTH_ERROR"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        if code:
            self.code = code


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


def _is_missing_table_error(error: Exception | None) -> bool:
    if error is None:
        return False
    message = str(error).lower()
    return "does not exist" in message or ("relation" in message and "does not exist" in message)


def _select_rows(client: Any, table: str, build_query) -> list[dict[str, Any]]:
    try:
        result = build_query(client.table(table)).execute()
    except Exception as exc:
        if _is_missing_table_error(exc):
            return []
        raise
    if _is_missing_table_error(getattr(result, "error", None)):
        return []
    return list(result.data or [])


def _parse_time(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def score_connectors_live(connectors: list[dict[str, Any]]) -> dict[str, Any]:
    """Score connector coverage and active status (0-100)."""
    total = len(connectors)
    if total == 0:
        return {
            "score": 50,
            "label": "connectorsLive",
            "activeConnectors": 0,
            "totalConnectors": 0,
            "activePct": 0.0,
            "summary": "No connectors configured yet",
        }
    active = sum(1 for row in connectors if str(row.get("status") or "").lower() == "active")
    unhealthy = sum(
        1
        for row in connectors
        if str(row.get("status") or "").lower() in {"unhealthy", "error", "auth_expired", "pending_auth"}
    )
    active_pct = active / total
    score = int(round(active_pct * 100))
    score = max(0, score - min(unhealthy * 10, 40))
    return {
        "score": score,
        "label": "connectorsLive",
        "activeConnectors": active,
        "totalConnectors": total,
        "unhealthyConnectors": unhealthy,
        "activePct": round(active_pct * 100, 1),
        "summary": f"{active}/{total} connectors active",
    }


def score_workflow_success(exec_runs: list[dict[str, Any]]) -> dict[str, Any]:
    """Score workflow execute success rate (0-100)."""
    completed = sum(1 for row in exec_runs if row.get("status") == "completed")
    failed = sum(1 for row in exec_runs if row.get("status") == "failed")
    total = completed + failed
    if total == 0:
        return {
            "score": 75,
            "label": "workflowSuccessRate",
            "completedRuns": 0,
            "failedRuns": 0,
            "successRate": None,
            "summary": "No completed workflow executions in window",
        }
    success_rate = completed / total
    if success_rate >= 0.95:
        score = 100
    elif success_rate >= 0.85:
        score = 85
    elif success_rate >= 0.7:
        score = 70
    elif success_rate >= 0.5:
        score = 50
    else:
        score = 30
    return {
        "score": score,
        "label": "workflowSuccessRate",
        "completedRuns": completed,
        "failedRuns": failed,
        "successRate": round(success_rate * 100, 1),
        "summary": f"{round(success_rate * 100, 1)}% workflow success rate",
    }


def score_agent_utilization(agent_jobs: list[dict[str, Any]]) -> dict[str, Any]:
    """Score agent task throughput vs failures/timeouts (0-100)."""
    if not agent_jobs:
        return {
            "score": 60,
            "label": "agentUtilization",
            "completedTasks": 0,
            "failedTasks": 0,
            "runningTasks": 0,
            "utilizationRate": None,
            "summary": "No agent jobs in window",
        }
    completed = sum(1 for row in agent_jobs if row.get("status") == "completed")
    failed = sum(1 for row in agent_jobs if row.get("status") == "failed")
    running = sum(1 for row in agent_jobs if row.get("status") == "running")
    timeouts = sum(1 for row in agent_jobs if row.get("status") == "timeout")
    denominator = completed + failed + running + timeouts
    utilization = completed / denominator if denominator else 0.0
    if utilization >= 0.75:
        score = 100
    elif utilization >= 0.55:
        score = 85
    elif utilization >= 0.35:
        score = 70
    elif utilization >= 0.2:
        score = 55
    else:
        score = 35
    score = max(0, score - min(timeouts * 5, 25))
    return {
        "score": score,
        "label": "agentUtilization",
        "completedTasks": completed,
        "failedTasks": failed,
        "runningTasks": running,
        "timeoutTasks": timeouts,
        "utilizationRate": round(utilization * 100, 1),
        "summary": f"{round(utilization * 100, 1)}% agent task completion rate",
    }


def score_approval_latency(
    exec_runs: list[dict[str, Any]],
    approvals: list[dict[str, Any]],
) -> dict[str, Any]:
    """Score approval responsiveness from run creation to first approval (0-100)."""
    approvals_by_run: dict[str, datetime] = {}
    for row in approvals:
        run_id = str(row.get("run_id") or "")
        created = _parse_time(row.get("created_at"))
        if run_id and created and run_id not in approvals_by_run:
            approvals_by_run[run_id] = created

    latencies_min: list[float] = []
    for run in exec_runs:
        run_id = str(run.get("id") or "")
        if run_id not in approvals_by_run:
            continue
        started = _parse_time(run.get("created_at"))
        approved = approvals_by_run[run_id]
        if started and approved and approved >= started:
            latencies_min.append((approved - started).total_seconds() / 60.0)

    if not latencies_min:
        pending = sum(1 for row in exec_runs if row.get("status") == "pending_approval")
        if pending:
            return {
                "score": 45,
                "label": "approvalLatency",
                "avgLatencyMinutes": None,
                "p95LatencyMinutes": None,
                "pendingApprovals": pending,
                "summary": f"{pending} runs awaiting approval",
            }
        return {
            "score": 100,
            "label": "approvalLatency",
            "avgLatencyMinutes": None,
            "p95LatencyMinutes": None,
            "pendingApprovals": 0,
            "summary": "No approval latency data in window",
        }

    latencies_min.sort()
    avg_min = sum(latencies_min) / len(latencies_min)
    p95_index = max(0, int(len(latencies_min) * 0.95) - 1)
    p95_min = latencies_min[p95_index]

    if p95_min <= 60:
        score = 100
    elif p95_min <= 240:
        score = 85
    elif p95_min <= 1440:
        score = 70
    elif p95_min <= 4320:
        score = 50
    else:
        score = 30

    return {
        "score": score,
        "label": "approvalLatency",
        "avgLatencyMinutes": round(avg_min, 1),
        "p95LatencyMinutes": round(p95_min, 1),
        "approvalSamples": len(latencies_min),
        "pendingApprovals": sum(1 for row in exec_runs if row.get("status") == "pending_approval"),
        "summary": f"p95 approval latency {round(p95_min, 1)} minutes",
    }


def grade_from_score(score: int) -> str:
    for threshold, grade in GRADE_THRESHOLDS:
        if score >= threshold:
            return grade
    return "critical"


def build_risks(dimensions: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    risks: list[dict[str, Any]] = []
    for key, dim in dimensions.items():
        dim_score = int(dim.get("score") or 0)
        if dim_score >= 70:
            continue
        risks.append(
            {
                "dimension": key,
                "score": dim_score,
                "summary": dim.get("summary"),
                "severity": "high" if dim_score < 50 else "medium",
            }
        )
    risks.sort(key=lambda item: item["score"])
    return risks


def compute_integration_health_score(
    *,
    connectors: list[dict[str, Any]],
    exec_runs: list[dict[str, Any]],
    agent_jobs: list[dict[str, Any]],
    approvals: list[dict[str, Any]],
) -> dict[str, Any]:
    """Compute weighted composite health score and dimension breakdown."""
    dimensions = {
        "connectorsLive": score_connectors_live(connectors),
        "workflowSuccessRate": score_workflow_success(exec_runs),
        "agentUtilization": score_agent_utilization(agent_jobs),
        "approvalLatency": score_approval_latency(exec_runs, approvals),
    }
    overall = 0.0
    for key, weight in DIMENSION_WEIGHTS.items():
        overall += float(dimensions[key]["score"]) * weight
    score = int(round(overall))
    grade = grade_from_score(score)
    risks = build_risks(dimensions)
    return {
        "score": score,
        "grade": grade,
        "dimensions": dimensions,
        "risks": risks,
        "weights": DIMENSION_WEIGHTS,
    }


def _serialize_snapshot(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row.get("id"),
        "orgId": row.get("org_id"),
        "score": row.get("score"),
        "grade": row.get("grade"),
        "dimensions": row.get("dimensions") or {},
        "risks": row.get("risks") or [],
        "lookbackDays": row.get("lookback_days"),
        "recordedAt": row.get("recorded_at"),
    }


def fetch_health_inputs(
    client: Any,
    org_id: str,
    *,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
) -> dict[str, Any]:
    since = (_now() - timedelta(days=lookback_days)).isoformat()
    connectors = _select_rows(
        client,
        "connectors",
        lambda table: table.select("id,type,status,vendor,environment").eq("org_id", org_id),
    )
    exec_runs = _select_rows(
        client,
        "workflow_runs",
        lambda table: table.select("id,status,run_type,created_at,completed_at,approval_status")
        .eq("org_id", org_id)
        .eq("run_type", "execute")
        .gte("created_at", since),
    )
    agent_jobs = _select_rows(
        client,
        "agent_jobs",
        lambda table: table.select("status,kind,created_at").eq("org_id", org_id).gte("created_at", since),
    )
    approvals = _select_rows(
        client,
        "run_approvals",
        lambda table: table.select("run_id,status,created_at").eq("org_id", org_id).gte("created_at", since),
    )
    return {
        "connectors": connectors,
        "execRuns": exec_runs,
        "agentJobs": agent_jobs,
        "approvals": approvals,
    }


def get_integration_health_score(
    client: Any,
    org_id: str,
    *,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
) -> dict[str, Any]:
    inputs = fetch_health_inputs(client, org_id, lookback_days=lookback_days)
    result = compute_integration_health_score(
        connectors=inputs["connectors"],
        exec_runs=inputs["execRuns"],
        agent_jobs=inputs["agentJobs"],
        approvals=inputs["approvals"],
    )
    return {
        **result,
        "lookbackDays": lookback_days,
        "computedAt": _now_iso(),
    }


def record_integration_health_snapshot(
    client: Any,
    org_id: str,
    *,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    actor_id: str | None = None,
) -> dict[str, Any]:
    """Compute and persist a health snapshot for CS trend charts."""
    health = get_integration_health_score(client, org_id, lookback_days=lookback_days)
    row = {
        "org_id": org_id,
        "score": health["score"],
        "grade": health["grade"],
        "dimensions": health["dimensions"],
        "risks": health["risks"],
        "lookback_days": lookback_days,
        "recorded_at": _now_iso(),
    }
    insert = client.table("integration_health_snapshots").insert(row)
    try:
        persisted_result = insert.execute()
    except Exception as exc:
        if _is_missing_table_error(exc):
            logger.warning("integration_health_snapshots table missing; returning computed health only")
            return {"snapshot": None, "health": health}
        raise
    if _is_missing_table_error(getattr(persisted_result, "error", None)):
        logger.warning("integration_health_snapshots table missing; returning computed health only")
        return {"snapshot": None, "health": health}
    persisted = (persisted_result.data or [row])[0]
    snapshot = _serialize_snapshot(persisted)

    if actor_id:
        write_audit_event(
            client,
            org_id,
            actor_id,
            AUDIT_INTEGRATION_HEALTH_SNAPSHOT,
            RESOURCE_TYPE_INTEGRATION_HEALTH,
            org_id,
            metadata={"score": health["score"], "grade": health["grade"], "lookbackDays": lookback_days},
        )

    logger.info(
        "integration_health_snapshot org_id=%s score=%s grade=%s",
        org_id,
        health["score"],
        health["grade"],
    )
    return {"snapshot": snapshot, "health": health}


def list_integration_health_history(
    client: Any,
    org_id: str,
    *,
    limit: int = 30,
) -> list[dict[str, Any]]:
    rows = _select_rows(
        client,
        "integration_health_snapshots",
        lambda table: table.select("*")
        .eq("org_id", org_id)
        .order("recorded_at", desc=True)
        .limit(limit),
    )
    return [_serialize_snapshot(row) for row in rows]


def org_ids_missing_health_snapshots(client: Any, *, limit: int = 100) -> list[str]:
    """Return org ids with no recorded integration health snapshot."""
    orgs = _select_rows(
        client,
        "organizations",
        lambda table: table.select("id").order("created_at", desc=True).limit(limit),
    )
    if not orgs:
        return []
    snapshots = _select_rows(
        client,
        "integration_health_snapshots",
        lambda table: table.select("org_id").order("recorded_at", desc=True).limit(max(limit * 4, 40)),
    )
    snapshot_org_ids = {str(row.get("org_id")) for row in snapshots if row.get("org_id")}
    missing: list[str] = []
    for row in orgs:
        org_id = str(row.get("id") or "")
        if org_id and org_id not in snapshot_org_ids:
            missing.append(org_id)
    return missing


def backfill_missing_integration_health_snapshots(
    client: Any,
    *,
    limit: int = 25,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    actor_id: str | None = None,
) -> dict[str, Any]:
    """Record first integration health snapshot for orgs that have none."""
    limit = max(1, min(limit, 100))
    missing_org_ids = org_ids_missing_health_snapshots(client, limit=limit * 2)[:limit]
    results: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for org_id in missing_org_ids:
        try:
            payload = record_integration_health_snapshot(
                client,
                org_id,
                lookback_days=lookback_days,
                actor_id=actor_id,
            )
            snapshot = payload.get("snapshot")
            health = payload.get("health") or {}
            results.append(
                {
                    "orgId": org_id,
                    "score": health.get("score"),
                    "grade": health.get("grade"),
                    "snapshotId": snapshot.get("id") if snapshot else None,
                }
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("integration_health_backfill_failed org_id=%s error=%s", org_id, str(exc))
            errors.append({"orgId": org_id, "message": str(exc)})

    logger.info(
        "integration_health_backfill completed=%s errors=%s",
        len(results),
        len(errors),
    )
    return {
        "requested": len(missing_org_ids),
        "backfilled": len(results),
        "errors": errors,
        "results": results,
        "lookbackDays": lookback_days,
    }
