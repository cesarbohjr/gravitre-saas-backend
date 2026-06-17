"""MT-00: Metrics endpoints. Org-scoped, no PII."""
from __future__ import annotations

import csv
import io
import time
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse, Response
from supabase import Client, create_client

from app.auth.dependencies import get_current_user, get_org_context
from app.config import Settings, get_settings
from app.core.logging import get_logger, request_id_ctx
from app.metrics.service import (
    connector_metrics,
    overview_metrics,
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


def _build_dashboard_overview(client: Client, org_id: str, settings: Settings, rng: str) -> dict[str, Any]:
    """Flatten service metrics plus connector/run aggregates for the dashboard cards."""
    data = overview_metrics(settings, org_id, rng)
    wf_rows = client.table("workflow_defs").select("id, status").eq("org_id", org_id).execute().data or []
    runs_rows = (
        client.table("workflow_runs")
        .select("id, status, duration_ms")
        .eq("org_id", org_id)
        .execute()
        .data
        or []
    )
    connector_rows = (
        client.table("connectors").select("id, status").eq("org_id", org_id).execute().data or []
    )

    total_runs = len(runs_rows)
    completed = len([r for r in runs_rows if r.get("status") == "completed"])
    failed = len([r for r in runs_rows if r.get("status") == "failed"])
    success_rate = round((completed / (completed + failed)) * 100, 2) if (completed + failed) > 0 else 0
    durations = [float(r.get("duration_ms") or 0) for r in runs_rows if r.get("duration_ms") is not None]
    avg_duration = round(sum(durations) / len(durations), 2) if durations else 0

    ingestion = data.get("ingestion") if isinstance(data.get("ingestion"), dict) else {}
    rag = data.get("rag") if isinstance(data.get("rag"), dict) else {}
    records_processed = int(ingestion.get("chunks_embedded_total") or 0)
    rag_total = int(rag.get("retrieval_requests_total") or 0)
    avg_latency = round(float(rag.get("avg_latency_ms") or 0), 2) if rag_total > 0 else avg_duration

    active_connectors = len([c for c in connector_rows if (c.get("status") or "") == "active"])
    data.update(
        {
            "totalWorkflows": len(wf_rows),
            "activeWorkflows": len([w for w in wf_rows if w.get("status") == "active"]),
            "totalRuns": total_runs,
            "successRate": success_rate,
            "avgDuration": avg_duration,
            "recordsProcessed": records_processed,
            "avgLatency": avg_latency,
            "activeConnectors": active_connectors,
            "totalConnectors": len(connector_rows),
        }
    )
    return data


@router.get("/overview")
async def overview(
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
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
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


@router.get("/workflows")
async def workflows(
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
async def rag(
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
async def timeseries(
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
async def metrics_insights(
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
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
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
async def weekly_throughput(
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
async def runs(
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
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    from app.metrics.service import parse_range
    _, start_at, _ = parse_range(rng)
    rows = (
        client.table("workflow_runs")
        .select("created_at, status")
        .eq("org_id", org_id)
        .gte("created_at", start_at.isoformat())
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
    latency_ms = int((time.perf_counter() - start) * 1000)
    logger.info(
        "metrics_runs request_id=%s org_id=%s range=%s latency_ms=%s",
        request_id_ctx.get(),
        org_id,
        rng,
        latency_ms,
    )
    return data
