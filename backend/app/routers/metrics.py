"""MT-00: Metrics endpoints. Org-scoped, no PII."""
from __future__ import annotations

import csv
import io
import time
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse, Response
from supabase import Client, create_client
from app.core.db import shared_service_client

from app.auth.dependencies import get_current_user, get_org_context
from app.config import Settings, get_settings
from app.core.logging import get_logger, request_id_ctx
from app.core.sql_aggregates import (
    UnexpectedRpcPayload,
    fetch_all_rows,
    is_missing_function_error,
    log_fallback_once,
    rpc_object,
)
from app.metrics.service import (
    connector_health_latency,
    connector_metrics,
    dashboard_run_stats,
    latency_distribution_series,
    overview_metrics,
    parse_range,
    rag_metrics,
    timeseries_metrics,
    weekly_throughput_metrics,
    workflow_metrics,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/api/metrics", tags=["metrics"])


def _validate_range(range_str: str | None) -> str:
    r = (range_str or "7d").strip().lower()
    if r not in {"7d", "30d", "90d"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid range")
    return r


_OVERVIEW_COUNTS_RPC = "metrics_overview_counts"
_OVERVIEW_COUNT_KEYS = (
    "total_workflows",
    "active_workflows",
    "total_runs",
    "completed_runs",
    "failed_runs",
    "duration_count",
    "duration_sum_ms",
    "total_connectors",
    "active_connectors",
)


def _overview_counts_python(client: Client, org_id: str, start_at: Any, end_at: Any) -> dict[str, Any]:
    """Fallback when the SQL function is not deployed: page every row (no 1000 cap)."""
    wf_rows = fetch_all_rows(
        lambda: client.table("workflow_defs").select("id, status").eq("org_id", org_id).order("id")
    )
    runs_rows = fetch_all_rows(
        lambda: client.table("workflow_runs")
        .select("id, status, duration_ms")
        .eq("org_id", org_id)
        .gte("created_at", start_at.isoformat())
        .lt("created_at", end_at.isoformat())
        .order("id")
    )
    connector_rows = fetch_all_rows(
        lambda: client.table("connectors").select("id, status").eq("org_id", org_id).order("id")
    )
    durations = [float(r.get("duration_ms") or 0) for r in runs_rows if r.get("duration_ms") is not None]
    return {
        "total_workflows": len(wf_rows),
        "active_workflows": len([w for w in wf_rows if w.get("status") == "active"]),
        "total_runs": len(runs_rows),
        "completed_runs": len([r for r in runs_rows if r.get("status") == "completed"]),
        "failed_runs": len([r for r in runs_rows if r.get("status") == "failed"]),
        "duration_count": len(durations),
        "duration_sum_ms": sum(durations),
        "total_connectors": len(connector_rows),
        "active_connectors": len([c for c in connector_rows if (c.get("status") or "") == "active"]),
    }


def _overview_counts(client: Client, org_id: str, start_at: Any, end_at: Any) -> dict[str, Any]:
    """Workflow/run/connector aggregates, computed in SQL when the RPC exists."""
    try:
        data = rpc_object(
            client,
            _OVERVIEW_COUNTS_RPC,
            {"p_org_id": org_id, "p_start_at": start_at.isoformat(), "p_end_at": end_at.isoformat()},
        )
        counts: dict[str, Any] = {}
        for key in _OVERVIEW_COUNT_KEYS:
            raw = data.get(key)
            if not isinstance(raw, (int, float)) or isinstance(raw, bool):
                raise UnexpectedRpcPayload(f"{_OVERVIEW_COUNTS_RPC}.{key}={raw!r}")
            counts[key] = raw
        return counts
    except UnexpectedRpcPayload as exc:
        log_fallback_once(_OVERVIEW_COUNTS_RPC, f"unexpected_payload: {exc}")
    except Exception as exc:
        if not is_missing_function_error(exc):
            raise
        log_fallback_once(_OVERVIEW_COUNTS_RPC, "function_not_found")
    return _overview_counts_python(client, org_id, start_at, end_at)


def _build_dashboard_overview(client: Client, org_id: str, settings: Settings, rng: str) -> dict[str, Any]:
    """Flatten service metrics plus connector/run aggregates for the dashboard cards."""
    _, start_at, end_at = parse_range(rng)
    data = overview_metrics(settings, org_id, rng)
    counts = _overview_counts(client, org_id, start_at, end_at)

    total_runs = int(counts["total_runs"])
    completed = int(counts["completed_runs"])
    failed = int(counts["failed_runs"])
    success_rate = round((completed / (completed + failed)) * 100, 2) if (completed + failed) > 0 else None
    duration_count = int(counts["duration_count"])
    avg_duration = round(float(counts["duration_sum_ms"]) / duration_count, 2) if duration_count else 0

    ingestion = data.get("ingestion") if isinstance(data.get("ingestion"), dict) else {}
    rag = data.get("rag") if isinstance(data.get("rag"), dict) else {}
    records_processed = int(ingestion.get("chunks_embedded_total") or 0)
    rag_total = int(rag.get("retrieval_requests_total") or 0)
    avg_latency = round(float(rag.get("avg_latency_ms") or 0), 2) if rag_total > 0 else avg_duration

    active_connectors = int(counts["active_connectors"])
    health_latency = connector_health_latency(client, org_id)
    dashboard = dashboard_run_stats(
        client,
        org_id,
        start_at,
        end_at,
        records_processed=records_processed,
    )
    from app.services.reporting_honesty import assess_metric_series

    trend_rates: list[float] = []
    trends = dashboard.get("trends") if isinstance(dashboard.get("trends"), dict) else {}
    for key in ("successRate", "success_rate", "dailySuccessRates"):
        series = trends.get(key)
        if isinstance(series, list):
            for item in series:
                if isinstance(item, (int, float)):
                    trend_rates.append(float(item))
                elif isinstance(item, dict) and item.get("value") is not None:
                    try:
                        trend_rates.append(float(item["value"]))
                    except (TypeError, ValueError):
                        pass
    series_assessment = assess_metric_series(
        trend_rates or ([success_rate] if success_rate is not None else []),
        metric_name="ops_success_rate",
        min_periods=3 if len(trend_rates) >= 3 else 1,
    )

    data.update(
        {
            "totalWorkflows": int(counts["total_workflows"]),
            "activeWorkflows": int(counts["active_workflows"]),
            "totalRuns": total_runs,
            "successRate": success_rate,
            "avgDuration": avg_duration,
            "recordsProcessed": records_processed,
            "avgLatency": avg_latency,
            "activeConnectors": active_connectors,
            "totalConnectors": int(counts["total_connectors"]),
            "changes": dashboard.get("changes", {}),
            "trends": dashboard.get("trends", {}),
            "connectorHealthLatencyMs": health_latency.get("avg_latency_ms", 0.0),
            "connectorHealthLatencyP95Ms": health_latency.get("p95_latency_ms", 0.0),
            # Phase 5 honesty: provenance so UI never paints this as intelligence outcomes.
            "honesty": {
                "successRateProvenance": "live_runs",
                "source": "workflow_runs.status completed/(completed+failed)",
                "range": rng,
                "seriesAssessment": series_assessment,
            },
        }
    )
    return data


@router.get("/overview")
def overview(
    *,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
    range: Annotated[str | None, Query()] = "7d",
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    start = time.perf_counter()
    rng = _validate_range(range)
    client = shared_service_client(settings, create_client)
    data = _build_dashboard_overview(client, org_id, settings, rng)
    latency_ms = int((time.perf_counter() - start) * 1000)
    logger.info(
        "metrics_overview request_id=%s org_id=%s range=%s latency_ms=%s",
        request_id_ctx.get(),
        org_id,
        rng,
        latency_ms,
    )
    return data


_OVERVIEW_EXPORT_FIELDS: tuple[tuple[str, str], ...] = (
    ("totalRuns", "Total Runs"),
    ("successRate", "Success Rate (%)"),
    ("recordsProcessed", "Records Processed"),
    ("avgLatency", "Avg Latency (ms)"),
    ("activeConnectors", "Active Connectors"),
    ("totalConnectors", "Total Connectors"),
    ("totalWorkflows", "Total Workflows"),
    ("activeWorkflows", "Active Workflows"),
)


@router.get("/export")
def export_metrics(
    *,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
    range: Annotated[str | None, Query()] = "7d",
    format: Annotated[str, Query(pattern="^(csv|json)$")] = "csv",
) -> Response:
    """Export dashboard overview metrics as CSV or JSON."""
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    rng = _validate_range(range)
    client = shared_service_client(settings, create_client)
    data = _build_dashboard_overview(client, org_id, settings, rng)

    if format == "json":
        return JSONResponse(content={"range": rng, "metrics": data})

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["metric", "value"])
    writer.writerow(["range", rng])
    for key, label in _OVERVIEW_EXPORT_FIELDS:
        writer.writerow([label, data.get(key, "")])
    return Response(
        content=output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="gravitre-metrics.csv"'},
    )


@router.get("/workflows")
def workflows(
    *,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
    range: Annotated[str | None, Query()] = "7d",
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    start = time.perf_counter()
    rng = _validate_range(range)
    data = workflow_metrics(settings, org_id, rng)
    latency_ms = int((time.perf_counter() - start) * 1000)
    logger.info(
        "metrics_workflows request_id=%s org_id=%s range=%s latency_ms=%s",
        request_id_ctx.get(),
        org_id,
        rng,
        latency_ms,
    )
    return data


@router.get("/rag")
def rag(
    *,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
    range: Annotated[str | None, Query()] = "7d",
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    start = time.perf_counter()
    rng = _validate_range(range)
    data = rag_metrics(settings, org_id, rng)
    latency_ms = int((time.perf_counter() - start) * 1000)
    logger.info(
        "metrics_rag request_id=%s org_id=%s range=%s latency_ms=%s",
        request_id_ctx.get(),
        org_id,
        rng,
        latency_ms,
    )
    return data


@router.get("/connectors")
async def connectors(
    *,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
    range: Annotated[str | None, Query()] = "7d",
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    start = time.perf_counter()
    rng = _validate_range(range)
    data = connector_metrics(settings, org_id, rng)
    latency_ms = int((time.perf_counter() - start) * 1000)
    logger.info(
        "metrics_connectors request_id=%s org_id=%s range=%s latency_ms=%s",
        request_id_ctx.get(),
        org_id,
        rng,
        latency_ms,
    )
    return data


@router.get("/integrations")
async def integrations(
    *,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
    range: Annotated[str | None, Query()] = "7d",
) -> dict:
    return await connectors(_user=_user, org_id=org_id, settings=settings, range=range)


@router.get("/timeseries")
def timeseries(
    *,
    metric: str,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
    range: Annotated[str | None, Query()] = "30d",
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    start = time.perf_counter()
    rng = _validate_range(range)
    try:
        data = timeseries_metrics(settings, org_id, rng, metric)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    latency_ms = int((time.perf_counter() - start) * 1000)
    logger.info(
        "metrics_timeseries request_id=%s org_id=%s range=%s metric=%s latency_ms=%s",
        request_id_ctx.get(),
        org_id,
        rng,
        metric,
        latency_ms,
    )
    return data


@router.get("/insights")
def metrics_insights(
    *,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
    range: Annotated[str | None, Query()] = "7d",
) -> dict:
    """Lightweight operational insights from real run + connector metrics (no hardcoded copy)."""
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    from datetime import datetime, timedelta, timezone

    rng = _validate_range(range)
    client = shared_service_client(settings, create_client)
    from app.metrics.service import parse_range

    _, start_at, _ = parse_range(rng)
    runs = (
        client.table("workflow_runs")
        .select("id, status, created_at, error_message, workflow_id")
        .eq("org_id", org_id)
        .gte("created_at", start_at.isoformat())
        .execute()
        .data
        or []
    )
    connectors = (
        client.table("connectors")
        .select("id, type, status")
        .eq("org_id", org_id)
        .execute()
        .data
        or []
    )
    insights: list[dict] = []
    failed = [r for r in runs if r.get("status") == "failed"]
    if failed:
        insights.append(
            {
                "id": "failed-runs",
                "type": "anomaly",
                "severity": "warning",
                "title": f"{len(failed)} failed run(s) in range",
                "description": "Review failed workflow runs and connector auth health.",
                "actionUrl": "/tasks",
            }
        )
    disconnected = [c for c in connectors if (c.get("status") or "") != "active"]
    if disconnected:
        insights.append(
            {
                "id": "connectors-offline",
                "type": "optimization",
                "severity": "info",
                "title": f"{len(disconnected)} connector(s) not active",
                "description": "Complete OAuth or reconnect integrations to restore automations.",
                "actionUrl": "/connectors",
            }
        )
    if not runs:
        insights.append(
            {
                "id": "no-runs",
                "type": "trend",
                "severity": "info",
                "title": "No workflow runs in selected period",
                "description": "Execute or schedule a workflow to populate execution metrics.",
                "actionUrl": "/automations",
            }
        )
    return {"insights": insights, "generatedAt": datetime.now(timezone.utc).isoformat()}


@router.get("/weekly-throughput")
def weekly_throughput(
    *,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """Day-of-week throughput for the current calendar week (records/chunks/runs)."""
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    start = time.perf_counter()
    data = weekly_throughput_metrics(settings, org_id)
    latency_ms = int((time.perf_counter() - start) * 1000)
    logger.info(
        "metrics_weekly_throughput request_id=%s org_id=%s latency_ms=%s",
        request_id_ctx.get(),
        org_id,
        latency_ms,
    )
    return data


@router.get("/runs")
def runs(
    *,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
    range: Annotated[str | None, Query()] = "30d",
    period: Annotated[str | None, Query()] = None,
) -> dict:
    """Alias for run time series metrics."""
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    start = time.perf_counter()
    period_map = {"24h": "7d", "7d": "7d", "30d": "30d"}
    rng = _validate_range(period_map.get(period or "", range or "30d"))
    client = shared_service_client(settings, create_client)
    _, start_at, end_at = parse_range(rng)
    rows = (
        client.table("workflow_runs")
        .select("created_at, status")
        .eq("org_id", org_id)
        .gte("created_at", start_at.isoformat())
        .lt("created_at", end_at.isoformat())
        .execute()
        .data
        or []
    )
    buckets: dict[str, dict[str, int]] = {}
    for row in rows:
        created_at = row.get("created_at")
        if not created_at:
            continue
        day = str(created_at)[:10]
        buckets.setdefault(day, {"completed": 0, "failed": 0, "pending": 0})
        status = row.get("status")
        if status == "completed":
            buckets[day]["completed"] += 1
        elif status == "failed":
            buckets[day]["failed"] += 1
        else:
            buckets[day]["pending"] += 1
    data = {
        "series": [
            {"timestamp": day, **counts} for day, counts in sorted(buckets.items(), key=lambda x: x[0])
        ]
    }
    data["runVolume"] = [
        {
            "time": entry["timestamp"],
            "completed": entry.get("completed", 0),
            "failed": entry.get("failed", 0),
            "pending": entry.get("pending", 0),
        }
        for entry in data["series"]
    ]
    latency_distribution, spike_time = latency_distribution_series(client, org_id, start_at, end_at)
    data["latencyDistribution"] = latency_distribution
    if spike_time:
        data["latencySpikeTime"] = spike_time
    latency_ms = int((time.perf_counter() - start) * 1000)
    logger.info(
        "metrics_runs request_id=%s org_id=%s range=%s latency_ms=%s",
        request_id_ctx.get(),
        org_id,
        rng,
        latency_ms,
    )
    return data
