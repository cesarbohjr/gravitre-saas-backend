"""MT-00: Metrics aggregation service. Org-scoped, no PII."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os
from typing import Any

from supabase import Client, create_client

from app.config import Settings
from app.core.logging import get_logger, request_id_ctx
logger = get_logger(__name__)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def parse_range(range_str: str | None) -> tuple[str, datetime, datetime]:
    r = (range_str or "7d").strip().lower()
    if r not in {"7d", "30d", "90d"}:
        raise ValueError("Invalid range")
    days = int(r.replace("d", ""))
    end = _now_utc()
    start = end - timedelta(days=days)
    return r, start, end


def _avg(values: list[float]) -> float:
    if not values:
        return 0.0
    return float(sum(values) / len(values))


def _client(settings: Settings) -> Client:
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


def _count_rows(r: Any) -> int:
    # Supabase may populate .count; fallback to len(data)
    if hasattr(r, "count") and isinstance(r.count, int):
        return r.count
    return len(r.data or [])


def _select_range(client: Client, table: str, org_id: str, start: datetime) -> Any:
    return (
        client.table(table)
        .select("*")
        .eq("org_id", org_id)
        .gte("created_at", start.isoformat())
    )


def _rpc_scalar(client: Client, fn_name: str, params: dict[str, Any]) -> float:
    """Call RPC function and return a float scalar (0.0 if null)."""
    try:
        r = client.rpc(fn_name, params).execute()
    except Exception:
        return 0.0
    data = r.data
    if data is None:
        return 0.0
    value: Any = None
    if isinstance(data, list):
        if data:
            row = data[0]
            value = next(iter(row.values()), None) if isinstance(row, dict) else row
    elif isinstance(data, dict):
        value = next(iter(data.values()), None)
    else:
        value = data
    try:
        return float(value) if value is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def _rollup_enabled() -> bool:
    return (os.environ.get("METRICS_ROLLUP_ENABLED") or "").strip().lower() in {"1", "true", "yes"}


def _rollup_range(start: datetime, end: datetime) -> tuple[str, str]:
    return start.date().isoformat(), end.date().isoformat()


def overview_metrics(settings: Settings, org_id: str, range_str: str) -> dict[str, Any]:
    r, start, end = parse_range(range_str)
    client = _client(settings)
    logger.info("metrics_overview request_id=%s org_id=%s range=%s rollup=%s", request_id_ctx.get(), org_id, r, _rollup_enabled())

    exec_runs = None
    dry_runs = None
    if _rollup_enabled():
        start_day, end_day = _rollup_range(start, end)
        exec_rows = (
            client.table("workflow_runs_daily")
            .select("count")
            .eq("org_id", org_id)
            .eq("run_type", "execute")
            .gte("day", start_day)
            .lte("day", end_day)
            .execute()
        )
        dry_rows = (
            client.table("workflow_runs_daily")
            .select("count")
            .eq("org_id", org_id)
            .eq("run_type", "dry_run")
            .gte("day", start_day)
            .lte("day", end_day)
            .execute()
        )
        exec_total = sum(int(x.get("count") or 0) for x in (exec_rows.data or []))
        dry_total = sum(int(x.get("count") or 0) for x in (dry_rows.data or []))
        exec_rows_full = (
            client.table("workflow_runs_daily")
            .select("status, count")
            .eq("org_id", org_id)
            .eq("run_type", "execute")
            .gte("day", start_day)
            .lte("day", end_day)
            .execute()
        )
        status_counts = {row["status"]: int(row.get("count") or 0) for row in (exec_rows_full.data or [])}
        completed = status_counts.get("completed", 0)
        failed = status_counts.get("failed", 0)
        pending = status_counts.get("pending_approval", 0)
    else:
        # workflow runs
        exec_runs = (
            client.table("workflow_runs")
            .select("id, status", count="exact")
            .eq("org_id", org_id)
            .eq("run_type", "execute")
            .gte("created_at", start.isoformat())
            .execute()
        )
        dry_runs = (
            client.table("workflow_runs")
            .select("id", count="exact")
            .eq("org_id", org_id)
            .eq("run_type", "dry_run")
            .gte("created_at", start.isoformat())
            .execute()
        )
        exec_rows = exec_runs.data or []
        completed = sum(1 for x in exec_rows if x.get("status") == "completed")
        failed = sum(1 for x in exec_rows if x.get("status") == "failed")
        pending = sum(1 for x in exec_rows if x.get("status") == "pending_approval")
        exec_total = _count_rows(exec_runs)
        dry_total = _count_rows(dry_runs)
    success_rate = (completed / (completed + failed)) if (completed + failed) > 0 else 0.0

    # rag retrieval logs
    rag_logs = None
    latencies = []
    result_counts: list[int] = []
    rag_total = 0
    if _rollup_enabled():
        start_day, end_day = _rollup_range(start, end)
        rag_rollups = (
            client.table("rag_retrieval_daily")
            .select("total, avg_latency_ms, p95_latency_ms, avg_result_count")
            .eq("org_id", org_id)
            .gte("day", start_day)
            .lte("day", end_day)
            .execute()
        )
        rows = rag_rollups.data or []
        rag_total = sum(int(r.get("total") or 0) for r in rows)
        avg_latency = (
            sum(float(r.get("avg_latency_ms") or 0) * int(r.get("total") or 0) for r in rows)
            / rag_total
        ) if rag_total > 0 else 0.0
        rag_p95 = max(float(r.get("p95_latency_ms") or 0) for r in rows) if rows else 0.0
        avg_result = (
            sum(float(r.get("avg_result_count") or 0) * int(r.get("total") or 0) for r in rows)
            / rag_total
        ) if rag_total > 0 else 0.0
    else:
        rag_logs = (
            client.table("rag_retrieval_logs")
            .select("latency_ms, result_count")
            .eq("org_id", org_id)
            .gte("created_at", start.isoformat())
            .execute()
        )
        latencies = [float(x.get("latency_ms") or 0) for x in (rag_logs.data or []) if x.get("latency_ms") is not None]
        result_counts = [int(x.get("result_count") or 0) for x in (rag_logs.data or [])]
        rag_p95 = _rpc_scalar(client, "metrics_rag_latency_p95", {"org_id": org_id, "start_at": start.isoformat()})
        rag_total = len(rag_logs.data or [])
        avg_latency = _avg(latencies)
        avg_result = _avg([float(x) for x in result_counts])

    # ingestion jobs
    ingest_jobs = (
        client.table("rag_ingest_jobs")
        .select("status, chunk_count")
        .eq("org_id", org_id)
        .gte("created_at", start.isoformat())
        .execute()
    )
    ingest_total = len(ingest_jobs.data or [])
    ingest_completed = sum(1 for x in (ingest_jobs.data or []) if x.get("status") == "completed")
    ingest_failed = sum(1 for x in (ingest_jobs.data or []) if x.get("status") == "failed")
    chunks_total = sum(int(x.get("chunk_count") or 0) for x in (ingest_jobs.data or []))
    ingest_success_rate = (ingest_completed / (ingest_completed + ingest_failed)) if (ingest_completed + ingest_failed) > 0 else 0.0

    # connectors (from audit_events)
    def count_action(action: str) -> int:
        r = (
            client.table("audit_events")
            .select("id", count="exact")
            .eq("org_id", org_id)
            .eq("action", action)
            .gte("created_at", start.isoformat())
            .execute()
        )
        return _count_rows(r)

    if _rollup_enabled():
        start_day, end_day = _rollup_range(start, end)
        conn_rollups = (
            client.table("connector_sends_daily")
            .select("connector_type, status, count")
            .eq("org_id", org_id)
            .gte("day", start_day)
            .lte("day", end_day)
            .execute()
        )
        def _sum(ct: str, st: str) -> int:
            return sum(int(r.get("count") or 0) for r in (conn_rollups.data or []) if r.get("connector_type") == ct and r.get("status") == st)
        slack_sent = _sum("slack", "sent")
        email_sent = _sum("email", "sent")
        webhook_sent = _sum("webhook", "sent")
        send_failures = _sum("slack", "failed") + _sum("email", "failed") + _sum("webhook", "failed")
    else:
        slack_sent = count_action("slack.send.sent")
        email_sent = count_action("email.send.sent")
        webhook_sent = count_action("webhook.send.sent")
        send_failures = (
            count_action("slack.send.failed")
            + count_action("email.send.failed")
            + count_action("webhook.send.failed")
        )

    return {
        "range": r,
        "workflows": {
            "dry_runs_total": dry_total,
            "exec_runs_total": exec_total,
            "exec_success_rate": round(success_rate, 4),
            "pending_approvals": pending,
        },
        "rag": {
            "retrieval_requests_total": rag_total,
            "avg_latency_ms": round(avg_latency, 2),
            "p95_latency_ms": round(rag_p95, 2),
            "avg_result_count": round(avg_result, 2),
            "insufficient_data": rag_total == 0,
        },
        "ingestion": {
            "ingest_jobs_total": ingest_total,
            "ingest_success_rate": round(ingest_success_rate, 4),
            "chunks_embedded_total": chunks_total,
        },
        "connectors": {
            "slack_sent": slack_sent,
            "email_sent": email_sent,
            "webhook_sent": webhook_sent,
            "send_failures_total": send_failures,
        },
    }


def workflow_metrics(settings: Settings, org_id: str, range_str: str) -> dict[str, Any]:
    r, start, end = parse_range(range_str)
    client = _client(settings)
    logger.info("metrics_workflows request_id=%s org_id=%s range=%s rollup=%s", request_id_ctx.get(), org_id, r, _rollup_enabled())

    runs = None
    exec_runs: list[dict] = []
    dry_runs: list[dict] = []
    dry_total = 0
    by_status = {"pending_approval": 0, "running": 0, "completed": 0, "failed": 0, "cancelled": 0}
    approval_funnel = {"created": 0, "approved": 0, "rejected": 0}
    avg_duration = 0.0
    p95_duration = 0.0

    if _rollup_enabled():
        start_day, end_day = _rollup_range(start, end)
        rows = (
            client.table("workflow_runs_daily")
            .select("run_type, status, count")
            .eq("org_id", org_id)
            .gte("day", start_day)
            .lte("day", end_day)
            .execute()
        )
        for row in (rows.data or []):
            if row.get("run_type") == "execute":
                status = row.get("status")
                by_status[status] = by_status.get(status, 0) + int(row.get("count") or 0)
            elif row.get("run_type") == "dry_run":
                dry_runs.append(row)
                dry_total += int(row.get("count") or 0)
        approval_funnel["created"] = sum(by_status.values())
        approval_funnel["approved"] = by_status.get("completed", 0)
        approval_funnel["rejected"] = by_status.get("cancelled", 0)
        p95_duration = _rpc_scalar(client, "metrics_exec_duration_p95", {"org_id": org_id, "start_at": start.isoformat()})
    else:
        runs = (
            client.table("workflow_runs")
            .select("id, status, run_type, created_at, completed_at, approval_status")
            .eq("org_id", org_id)
            .gte("created_at", start.isoformat())
            .execute()
        )
        exec_runs = [x for x in (runs.data or []) if x.get("run_type") == "execute"]
        dry_runs = [x for x in (runs.data or []) if x.get("run_type") == "dry_run"]
        dry_total = len(dry_runs)
        by_status = {
            "pending_approval": sum(1 for x in exec_runs if x.get("status") == "pending_approval"),
            "running": sum(1 for x in exec_runs if x.get("status") == "running"),
            "completed": sum(1 for x in exec_runs if x.get("status") == "completed"),
            "failed": sum(1 for x in exec_runs if x.get("status") == "failed"),
            "cancelled": sum(1 for x in exec_runs if x.get("status") == "cancelled"),
        }
        approval_funnel = {
            "created": len(exec_runs),
            "approved": sum(1 for x in exec_runs if x.get("approval_status") == "approved"),
            "rejected": sum(1 for x in exec_runs if x.get("approval_status") == "rejected"),
        }
        durations = []
        for x in exec_runs:
            if x.get("completed_at") and x.get("created_at"):
                try:
                    c_at = datetime.fromisoformat(str(x["created_at"]).replace("Z", "+00:00"))
                    done = datetime.fromisoformat(str(x["completed_at"]).replace("Z", "+00:00"))
                    durations.append((done - c_at).total_seconds() * 1000)
                except Exception:
                    pass
        avg_duration = _avg(durations)
        p95_duration = _rpc_scalar(client, "metrics_exec_duration_p95", {"org_id": org_id, "start_at": start.isoformat()})

    # Step failures by type (execute runs only)
    failures_by_type: dict[str, int] = {}
    dry_rag_failure_rate = 0.0
    if not _rollup_enabled():
        exec_run_ids = {x["id"] for x in exec_runs if x.get("id")}
        steps = (
            client.table("workflow_steps")
            .select("run_id, step_type, status")
            .eq("org_id", org_id)
            .gte("created_at", start.isoformat())
            .execute()
        )
        rag_failures = 0
        rag_total = 0
        for s in (steps.data or []):
            if s.get("run_id") not in exec_run_ids:
                continue
            stype = s.get("step_type") or "unknown"
            if s.get("status") == "failed":
                failures_by_type[stype] = failures_by_type.get(stype, 0) + 1
            if stype == "rag_retrieve":
                rag_total += 1
                if s.get("status") == "failed":
                    rag_failures += 1

        dry_run_steps = [s for s in (steps.data or []) if s.get("run_id") not in exec_run_ids]
        dry_rag_total = sum(1 for s in dry_run_steps if s.get("step_type") == "rag_retrieve")
        dry_rag_failed = sum(1 for s in dry_run_steps if s.get("step_type") == "rag_retrieve" and s.get("status") == "failed")
        dry_rag_failure_rate = (dry_rag_failed / dry_rag_total) if dry_rag_total > 0 else 0.0

    return {
        "range": r,
        "exec": {
            "by_status": by_status,
            "approval_funnel": approval_funnel,
            "avg_duration_ms": round(avg_duration, 2),
            "p95_duration_ms": round(p95_duration, 2),
            "step_failures_by_type": failures_by_type,
        },
        "dry_run": {
            "total": dry_total,
            "rag_step_failure_rate": round(dry_rag_failure_rate, 4),
        },
    }


def rag_metrics(settings: Settings, org_id: str, range_str: str) -> dict[str, Any]:
    r, start, end = parse_range(range_str)
    client = _client(settings)
    logger.info("metrics_rag request_id=%s org_id=%s range=%s rollup=%s", request_id_ctx.get(), org_id, r, _rollup_enabled())

    logs = None
    latencies: list[float] = []
    counts: list[int] = []
    rag_total = 0
    avg_latency = 0.0
    avg_result = 0.0
    rag_p95 = 0.0
    zero_results = 0
    if _rollup_enabled():
        start_day, end_day = _rollup_range(start, end)
        rag_rollups = (
            client.table("rag_retrieval_daily")
            .select("total, avg_latency_ms, p95_latency_ms, avg_result_count")
            .eq("org_id", org_id)
            .gte("day", start_day)
            .lte("day", end_day)
            .execute()
        )
        rows = rag_rollups.data or []
        rag_total = sum(int(r.get("total") or 0) for r in rows)
        avg_latency = (
            sum(float(r.get("avg_latency_ms") or 0) * int(r.get("total") or 0) for r in rows)
            / rag_total
        ) if rag_total > 0 else 0.0
        rag_p95 = max(float(r.get("p95_latency_ms") or 0) for r in rows) if rows else 0.0
        avg_result = (
            sum(float(r.get("avg_result_count") or 0) * int(r.get("total") or 0) for r in rows)
            / rag_total
        ) if rag_total > 0 else 0.0
    else:
        logs = (
            client.table("rag_retrieval_logs")
            .select("latency_ms, result_count")
            .eq("org_id", org_id)
            .gte("created_at", start.isoformat())
            .execute()
        )
        latencies = [float(x.get("latency_ms") or 0) for x in (logs.data or []) if x.get("latency_ms") is not None]
        counts = [int(x.get("result_count") or 0) for x in (logs.data or [])]
        zero_results = sum(1 for x in counts if x == 0)
        rag_p95 = _rpc_scalar(client, "metrics_rag_latency_p95", {"org_id": org_id, "start_at": start.isoformat()})
        rag_total = len(logs.data or [])
        avg_latency = _avg(latencies)
        avg_result = _avg([float(x) for x in counts])

    jobs = (
        client.table("rag_ingest_jobs")
        .select("status, chunk_count")
        .eq("org_id", org_id)
        .gte("created_at", start.isoformat())
        .execute()
    )
    by_status = {
        "queued": sum(1 for j in (jobs.data or []) if j.get("status") == "queued"),
        "running": sum(1 for j in (jobs.data or []) if j.get("status") == "running"),
        "completed": sum(1 for j in (jobs.data or []) if j.get("status") == "completed"),
        "failed": sum(1 for j in (jobs.data or []) if j.get("status") == "failed"),
    }
    chunk_counts = [int(j.get("chunk_count") or 0) for j in (jobs.data or [])]
    chunks_p95 = _rpc_scalar(client, "metrics_ingest_chunks_p95", {"org_id": org_id, "start_at": start.isoformat()})

    return {
        "range": r,
        "retrieval": {
            "total": rag_total,
            "avg_latency_ms": round(avg_latency, 2),
            "p95_latency_ms": round(rag_p95, 2),
            "avg_result_count": round(avg_result, 2),
            "zero_result_rate": round((zero_results / len(counts)) if counts else 0.0, 4),
            "insufficient_data": rag_total == 0,
        },
        "ingestion": {
            "jobs_total": len(jobs.data or []),
            "by_status": by_status,
            "avg_chunks_per_job": round(_avg([float(x) for x in chunk_counts]), 2),
            "p95_chunks_per_job": round(chunks_p95, 2),
        },
    }


def connector_metrics(settings: Settings, org_id: str, range_str: str) -> dict[str, Any]:
    r, start, end = parse_range(range_str)
    client = _client(settings)
    logger.info("metrics_connectors request_id=%s org_id=%s range=%s rollup=%s", request_id_ctx.get(), org_id, r, _rollup_enabled())

    def count_action(action: str) -> int:
        r = (
            client.table("audit_events")
            .select("id", count="exact")
            .eq("org_id", org_id)
            .eq("action", action)
            .gte("created_at", start.isoformat())
            .execute()
        )
        return _count_rows(r)

    if _rollup_enabled():
        start_day, end_day = _rollup_range(start, end)
        rollups = (
            client.table("connector_sends_daily")
            .select("connector_type, status, count")
            .eq("org_id", org_id)
            .gte("day", start_day)
            .lte("day", end_day)
            .execute()
        )
        def _sum(ct: str, st: str) -> int:
            return sum(
                int(r.get("count") or 0)
                for r in (rollups.data or [])
                if r.get("connector_type") == ct and r.get("status") == st
            )
        slack_sent = _sum("slack", "sent")
        slack_failed = _sum("slack", "failed")
        email_sent = _sum("email", "sent")
        email_failed = _sum("email", "failed")
        webhook_sent = _sum("webhook", "sent")
        webhook_failed = _sum("webhook", "failed")
    else:
        slack_sent = count_action("slack.send.sent")
        slack_failed = count_action("slack.send.failed")
        email_sent = count_action("email.send.sent")
        email_failed = count_action("email.send.failed")
        webhook_sent = count_action("webhook.send.sent")
        webhook_failed = count_action("webhook.send.failed")

    # Optional latency from connector OAuth health checks (config.health.latencyMs)
    health_latency = connector_health_latency(client, org_id)
    return {
        "range": r,
        "slack": {"sent": slack_sent, "failed": slack_failed},
        "email": {"sent": email_sent, "failed": email_failed},
        "webhook": {"sent": webhook_sent, "failed": webhook_failed},
        "health_latency_ms": health_latency.get("avg_latency_ms", 0.0),
        "health_latency_p95_ms": health_latency.get("p95_latency_ms", 0.0),
        "health_latency_samples": health_latency.get("samples", 0),
        "health_latency_by_type": health_latency.get("by_type", {}),
    }


def timeseries_metrics(settings: Settings, org_id: str, range_str: str, metric: str) -> dict[str, Any]:
    r, start, end = parse_range(range_str)
    client = _client(settings)
    logger.info("metrics_timeseries request_id=%s org_id=%s range=%s metric=%s rollup=%s", request_id_ctx.get(), org_id, r, metric, _rollup_enabled())
    supported = {
        "exec_runs_total",
        "exec_failures_total",
        "rag_retrieval_total",
        "ingest_jobs_total",
        "connector_sends_total",
    }
    if metric not in supported:
        raise ValueError("Invalid metric")

    points: dict[str, int] = {}

    def bucket_date(dt_str: str) -> str:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        return dt.date().isoformat()

    if _rollup_enabled() and metric in {"exec_runs_total", "exec_failures_total"}:
        start_day, end_day = _rollup_range(start, end)
        rows = (
            client.table("workflow_runs_daily")
            .select("day, status, count")
            .eq("org_id", org_id)
            .eq("run_type", "execute")
            .gte("day", start_day)
            .lte("day", end_day)
            .execute()
        )
        for row in (rows.data or []):
            if metric == "exec_failures_total" and row.get("status") != "failed":
                continue
            day = str(row["day"])
            points[day] = points.get(day, 0) + int(row.get("count") or 0)
    elif metric in {"exec_runs_total", "exec_failures_total"}:
        runs = (
            client.table("workflow_runs")
            .select("created_at, status, run_type")
            .eq("org_id", org_id)
            .eq("run_type", "execute")
            .gte("created_at", start.isoformat())
            .execute()
        )
        for rrow in (runs.data or []):
            if metric == "exec_failures_total" and rrow.get("status") != "failed":
                continue
            day = bucket_date(rrow["created_at"])
            points[day] = points.get(day, 0) + 1
    elif _rollup_enabled() and metric == "rag_retrieval_total":
        start_day, end_day = _rollup_range(start, end)
        rows = (
            client.table("rag_retrieval_daily")
            .select("day, total")
            .eq("org_id", org_id)
            .gte("day", start_day)
            .lte("day", end_day)
            .execute()
        )
        for row in (rows.data or []):
            day = str(row["day"])
            points[day] = points.get(day, 0) + int(row.get("total") or 0)
    elif metric == "rag_retrieval_total":
        logs = (
            client.table("rag_retrieval_logs")
            .select("created_at")
            .eq("org_id", org_id)
            .gte("created_at", start.isoformat())
            .execute()
        )
        for row in (logs.data or []):
            day = bucket_date(row["created_at"])
            points[day] = points.get(day, 0) + 1
    elif metric == "ingest_jobs_total":
        jobs = (
            client.table("rag_ingest_jobs")
            .select("created_at")
            .eq("org_id", org_id)
            .gte("created_at", start.isoformat())
            .execute()
        )
        for row in (jobs.data or []):
            day = bucket_date(row["created_at"])
            points[day] = points.get(day, 0) + 1
    elif _rollup_enabled() and metric == "connector_sends_total":
        start_day, end_day = _rollup_range(start, end)
        rows = (
            client.table("connector_sends_daily")
            .select("day, status, count")
            .eq("org_id", org_id)
            .eq("status", "sent")
            .gte("day", start_day)
            .lte("day", end_day)
            .execute()
        )
        for row in (rows.data or []):
            day = str(row["day"])
            points[day] = points.get(day, 0) + int(row.get("count") or 0)
    elif metric == "connector_sends_total":
        actions = ["slack.send.sent", "email.send.sent", "webhook.send.sent"]
        events = (
            client.table("audit_events")
            .select("created_at, action")
            .eq("org_id", org_id)
            .gte("created_at", start.isoformat())
            .in_("action", actions)
            .execute()
        )
        for row in (events.data or []):
            day = bucket_date(row["created_at"])
            points[day] = points.get(day, 0) + 1

    return {
        "range": r,
        "metric": metric,
        "points": [{"date": k, "value": points[k]} for k in sorted(points.keys())],
    }


_WEEKDAY_LABELS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def _parse_timestamp(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _extract_record_count(metadata: dict[str, Any]) -> int:
    for key in ("recordsProcessed", "records_processed", "records", "pages_synced", "chunk_count", "chunks"):
        raw = metadata.get(key)
        if raw is None:
            continue
        try:
            count = int(raw)
        except (TypeError, ValueError):
            continue
        if count > 0:
            return count
    return 0


def _start_of_week_utc(now: datetime | None = None) -> datetime:
    current = now or _now_utc()
    monday = current - timedelta(days=current.weekday())
    return monday.replace(hour=0, minute=0, second=0, microsecond=0)


def weekly_throughput_metrics(settings: Settings, org_id: str) -> dict[str, Any]:
    """Aggregate records processed by weekday for the current calendar week."""
    client = _client(settings)
    week_start = _start_of_week_utc()
    buckets = {label: 0 for label in _WEEKDAY_LABELS}

    ingest_jobs = (
        client.table("rag_ingest_jobs")
        .select("created_at, chunk_count, status")
        .eq("org_id", org_id)
        .gte("created_at", week_start.isoformat())
        .execute()
    )
    for row in ingest_jobs.data or []:
        if row.get("status") != "completed":
            continue
        created_at = _parse_timestamp(row.get("created_at"))
        if created_at is None:
            continue
        buckets[_WEEKDAY_LABELS[created_at.weekday()]] += int(row.get("chunk_count") or 0)

    audit_events = (
        client.table("audit_events")
        .select("created_at, metadata")
        .eq("org_id", org_id)
        .gte("created_at", week_start.isoformat())
        .execute()
    )
    for row in audit_events.data or []:
        metadata = row.get("metadata") or {}
        if not isinstance(metadata, dict):
            continue
        count = _extract_record_count(metadata)
        if count <= 0:
            continue
        created_at = _parse_timestamp(row.get("created_at"))
        if created_at is None:
            continue
        buckets[_WEEKDAY_LABELS[created_at.weekday()]] += count

    runs = (
        client.table("workflow_runs")
        .select("created_at, status, run_type")
        .eq("org_id", org_id)
        .eq("run_type", "execute")
        .eq("status", "completed")
        .gte("created_at", week_start.isoformat())
        .execute()
    )
    for row in runs.data or []:
        created_at = _parse_timestamp(row.get("created_at"))
        if created_at is None:
            continue
        buckets[_WEEKDAY_LABELS[created_at.weekday()]] += 1

    days = [{"day": label, "records": buckets[label]} for label in _WEEKDAY_LABELS]
    values = list(buckets.values())
    max_records = max(values) if values else 0
    avg_records = (sum(values) / len(values)) if values else 0.0
    target = int(round(max(avg_records * 1.1, max_records * 0.95))) if max_records > 0 else 0
    days_with_target = [{**entry, "target": target} for entry in days]

    return {
        "weekStart": week_start.date().isoformat(),
        "target": target,
        "days": days_with_target,
    }


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, int(round((pct / 100.0) * (len(ordered) - 1)))))
    return float(ordered[idx])


def _pct_change(current: float, previous: float) -> float:
    if previous == 0:
        return 0.0 if current == 0 else 100.0
    return round(((current - previous) / previous) * 100.0, 1)


def _run_window_stats(rows: list[dict[str, Any]]) -> dict[str, float]:
    total = len(rows)
    completed = sum(1 for row in rows if row.get("status") == "completed")
    failed = sum(1 for row in rows if row.get("status") == "failed")
    success_rate = round((completed / (completed + failed)) * 100.0, 2) if (completed + failed) > 0 else 0.0
    durations = [float(row.get("duration_ms") or 0) for row in rows if row.get("duration_ms") is not None]
    avg_latency = round(sum(durations) / len(durations), 2) if durations else 0.0
    return {
        "totalRuns": float(total),
        "successRate": success_rate,
        "avgLatency": avg_latency,
    }


def dashboard_run_stats(
    client: Client,
    org_id: str,
    start: datetime,
    end: datetime,
    *,
    records_processed: int = 0,
) -> dict[str, Any]:
    """Period stats + deltas + sparkline trends for dashboard cards."""
    period_seconds = max(int((end - start).total_seconds()), 1)
    prev_end = start
    prev_start = start - timedelta(seconds=period_seconds)

    current_rows = (
        client.table("workflow_runs")
        .select("status, duration_ms, created_at")
        .eq("org_id", org_id)
        .gte("created_at", start.isoformat())
        .lt("created_at", end.isoformat())
        .execute()
        .data
        or []
    )
    previous_rows = (
        client.table("workflow_runs")
        .select("status, duration_ms")
        .eq("org_id", org_id)
        .gte("created_at", prev_start.isoformat())
        .lt("created_at", prev_end.isoformat())
        .execute()
        .data
        or []
    )

    current = _run_window_stats(current_rows)
    previous = _run_window_stats(previous_rows)
    current["recordsProcessed"] = float(records_processed)

    day_buckets: dict[str, int] = {}
    success_buckets: dict[str, list[int]] = {}
    latency_buckets: dict[str, list[float]] = {}
    for row in current_rows:
        created_at = _parse_timestamp(row.get("created_at"))
        if created_at is None:
            continue
        day = created_at.date().isoformat()
        day_buckets[day] = day_buckets.get(day, 0) + 1
        success_buckets.setdefault(day, [0, 0])
        if row.get("status") == "completed":
            success_buckets[day][0] += 1
        elif row.get("status") == "failed":
            success_buckets[day][1] += 1
        if row.get("duration_ms") is not None:
            latency_buckets.setdefault(day, []).append(float(row.get("duration_ms") or 0))

    ordered_days = sorted(day_buckets.keys())
    run_trend = [day_buckets[day] for day in ordered_days]
    success_trend = [
        round((vals[0] / (vals[0] + vals[1])) * 100.0, 1) if (vals[0] + vals[1]) > 0 else 0.0
        for day in ordered_days
        for vals in [success_buckets.get(day, [0, 0])]
    ]
    latency_trend = [
        round(sum(values) / len(values), 1) if values else 0.0
        for day in ordered_days
        for values in [latency_buckets.get(day, [])]
    ]

    return {
        "changes": {
            "totalRuns": _pct_change(current["totalRuns"], previous["totalRuns"]),
            "successRate": _pct_change(current["successRate"], previous["successRate"]),
            "recordsProcessed": 0.0,
            "avgLatency": _pct_change(current["avgLatency"], previous["avgLatency"]),
        },
        "trends": {
            "totalRuns": run_trend,
            "successRate": success_trend,
            "recordsProcessed": run_trend,
            "avgLatency": latency_trend,
        },
    }


def connector_health_latency(client: Client, org_id: str) -> dict[str, Any]:
    """Aggregate OAuth health-check latency stored on connector config."""
    rows = (
        client.table("connectors")
        .select("type, vendor, config")
        .eq("org_id", org_id)
        .execute()
        .data
        or []
    )
    by_type: dict[str, list[float]] = {}
    all_values: list[float] = []
    for row in rows:
        config = row.get("config") or {}
        health = config.get("health") if isinstance(config, dict) else None
        if not isinstance(health, dict):
            continue
        raw = health.get("latencyMs")
        if raw is None:
            continue
        try:
            latency = float(raw)
        except (TypeError, ValueError):
            continue
        if latency < 0:
            continue
        connector_type = str(row.get("type") or row.get("vendor") or "unknown")
        by_type.setdefault(connector_type, []).append(latency)
        all_values.append(latency)

    def _summary(values: list[float]) -> dict[str, float]:
        if not values:
            return {"avg_ms": 0.0, "p95_ms": 0.0, "samples": 0.0}
        return {
            "avg_ms": round(_avg(values), 1),
            "p95_ms": round(_percentile(values, 95.0), 1),
            "samples": float(len(values)),
        }

    return {
        "avg_latency_ms": round(_avg(all_values), 1) if all_values else 0.0,
        "p95_latency_ms": round(_percentile(all_values, 95.0), 1) if all_values else 0.0,
        "samples": len(all_values),
        "by_type": {key: _summary(values) for key, values in sorted(by_type.items())},
    }


def latency_distribution_series(
    client: Client,
    org_id: str,
    start: datetime,
    end: datetime,
) -> tuple[list[dict[str, Any]], str | None]:
    """Hourly/daily latency percentiles from rag_retrieval_logs with optional spike marker."""
    rows = (
        client.table("rag_retrieval_logs")
        .select("created_at, latency_ms")
        .eq("org_id", org_id)
        .gte("created_at", start.isoformat())
        .lt("created_at", end.isoformat())
        .execute()
        .data
        or []
    )
    if not rows:
        run_rows = (
            client.table("workflow_runs")
            .select("created_at, duration_ms")
            .eq("org_id", org_id)
            .gte("created_at", start.isoformat())
            .lt("created_at", end.isoformat())
            .execute()
            .data
            or []
        )
        for row in run_rows:
            if row.get("duration_ms") is None:
                continue
            rows.append({"created_at": row.get("created_at"), "latency_ms": row.get("duration_ms")})

    use_hourly = (end - start) <= timedelta(days=2)
    buckets: dict[str, list[float]] = {}
    for row in rows:
        created_at = _parse_timestamp(row.get("created_at"))
        if created_at is None:
            continue
        if row.get("latency_ms") is None:
            continue
        try:
            latency = float(row.get("latency_ms") or 0)
        except (TypeError, ValueError):
            continue
        if use_hourly:
            label = created_at.strftime("%H:%M")
        else:
            label = created_at.date().isoformat()
        buckets.setdefault(label, []).append(latency)

    series: list[dict[str, Any]] = []
    spike_time: str | None = None
    max_p95 = 0.0
    p95_values: list[float] = []
    for label in sorted(buckets.keys()):
        values = buckets[label]
        p50 = round(_percentile(values, 50.0), 1)
        p95 = round(_percentile(values, 95.0), 1)
        p99 = round(_percentile(values, 99.0), 1)
        series.append({"time": label, "p50": p50, "p95": p95, "p99": p99})
        p95_values.append(p95)
        if p95 > max_p95:
            max_p95 = p95
            spike_time = label

    if series and p95_values:
        median_p95 = sorted(p95_values)[len(p95_values) // 2]
        if median_p95 <= 0 or max_p95 < median_p95 * 1.75:
            spike_time = None

    return series, spike_time

