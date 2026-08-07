"""Phase 5 — reporting / insights honesty audit endpoint."""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from supabase import create_client

from app.auth.dependencies import get_current_user, get_org_context
from app.config import Settings, get_settings
from app.services.reporting_honesty import (
    REPORTING_SURFACES,
    assess_metric_series,
    label_placeholder_metric,
    normalize_agent_success_rate,
)

router = APIRouter(prefix="/api/reporting", tags=["reporting-honesty"])


@router.get("/honesty-audit")
async def reporting_honesty_audit(
    *,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    """Live inventory + correlation checks for reporting surfaces."""
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")

    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    findings: list[dict[str, Any]] = []

    # Agent hub: stored rates must not invent 100% with zero runs.
    invented_defaults = 0
    agent_rows: list[dict[str, Any]] = []
    try:
        agents = (
            client.table("agents")
            .select("id,name,stats")
            .eq("org_id", org_id)
            .limit(50)
            .execute()
        )
        agent_rows = list(getattr(agents, "data", None) or [])
        for row in agent_rows:
            stats = row.get("stats") if isinstance(row.get("stats"), dict) else {}
            tasks = int(stats.get("tasksToday") or stats.get("tasks_today") or 0)
            raw_rate = stats.get("successRate", stats.get("success_rate"))
            normalized = normalize_agent_success_rate(stored_rate=raw_rate, total_runs=tasks)
            if tasks <= 0 and raw_rate in (100, 100.0, "100"):
                invented_defaults += 1
                findings.append(
                    {
                        "surface": "agents_hub",
                        "severity": "error",
                        "agent_id": row.get("id"),
                        "detail": "Stored successRate=100 with zero tasks — treat as insufficient_data",
                        "normalized": normalized,
                    }
                )
    except Exception as exc:  # noqa: BLE001
        findings.append(
            {
                "surface": "agents_hub",
                "severity": "warning",
                "detail": f"agents table scan skipped: {str(exc)[:160]}",
            }
        )

    try:
        operators = (
            client.table("operators")
            .select("id,name,total_runs,success_rate")
            .eq("org_id", org_id)
            .limit(50)
            .execute()
        )
        for row in list(getattr(operators, "data", None) or []):
            runs = int(row.get("total_runs") or 0)
            rate = row.get("success_rate")
            normalized = normalize_agent_success_rate(stored_rate=rate, total_runs=runs)
            if runs <= 0 and rate in (100, 100.0, "100"):
                invented_defaults += 1
                findings.append(
                    {
                        "surface": "agents_hub",
                        "severity": "error",
                        "operator_id": row.get("id"),
                        "detail": "operators.success_rate=100 with total_runs=0",
                        "normalized": normalized,
                    }
                )
    except Exception as exc:  # noqa: BLE001
        findings.append(
            {
                "surface": "agents_hub",
                "severity": "warning",
                "detail": f"operators table scan skipped: {str(exc)[:160]}",
            }
        )

    # Metrics success-rate series across recent windows (static → Phase-4-class flag).
    series_rates: list[float] = []
    for rng, days in (("7d", 7), ("30d", 30), ("90d", 90)):
        from datetime import datetime, timedelta, timezone

        end = datetime.now(timezone.utc)
        start = end - timedelta(days=days)
        runs = (
            client.table("workflow_runs")
            .select("status")
            .eq("org_id", org_id)
            .gte("created_at", start.isoformat())
            .lt("created_at", end.isoformat())
            .limit(5000)
            .execute()
        )
        rows = list(getattr(runs, "data", None) or [])
        completed = len([r for r in rows if r.get("status") == "completed"])
        failed = len([r for r in rows if r.get("status") == "failed"])
        denom = completed + failed
        series_rates.append(round((completed / denom) * 100, 2) if denom else 0.0)

    static_check = assess_metric_series(series_rates, metric_name="ops_success_rate_7_30_90")
    if static_check.get("flagged") and any(v > 0 for v in series_rates):
        findings.append(
            {
                "surface": "metrics_ops",
                "severity": "warning",
                "detail": "Success rate suspiciously static across 7d/30d/90d",
                "assessment": static_check,
                "series": series_rates,
            }
        )

    # Outcome-correlated agent rates (live) when events exist.
    outcome_count = 0
    try:
        outcome_events = (
            client.table("intelligence_outcome_events")
            .select("id")
            .eq("org_id", org_id)
            .limit(500)
            .execute()
        )
        outcome_count = len(list(getattr(outcome_events, "data", None) or []))
    except Exception as exc:  # noqa: BLE001
        findings.append(
            {
                "surface": "intelligence_reports",
                "severity": "warning",
                "detail": f"intelligence_outcome_events unavailable: {str(exc)[:160]}",
            }
        )

    roi_placeholders = [
        label_placeholder_metric("Hours saved"),
        label_placeholder_metric("Revenue influenced"),
        label_placeholder_metric("Cost savings"),
    ]

    error_count = sum(1 for f in findings if f.get("severity") == "error")
    warning_count = sum(1 for f in findings if f.get("severity") == "warning")
    verdict = "PASS" if error_count == 0 else "FAIL"
    if error_count == 0 and warning_count:
        verdict = "PASS_WITH_WARNINGS"

    return {
        "org_id": org_id,
        "verdict": verdict,
        "surfaces": REPORTING_SURFACES,
        "findings": findings,
        "summary": {
            "surface_count": len(REPORTING_SURFACES),
            "finding_errors": error_count,
            "finding_warnings": warning_count,
            "agents_scanned": len(agent_rows),
            "invented_100pct_zero_run": invented_defaults,
            "intelligence_outcome_events": outcome_count,
            "ops_success_rate_series_7_30_90": series_rates,
            "ops_series_assessment": static_check,
        },
        "roi_placeholders": roi_placeholders,
        "rules": {
            "never_default_success_rate_100_without_runs": True,
            "roi_hours_revenue_cost_not_configured": True,
            "metrics_ranges": ["7d", "30d", "90d"],
            "prefer_live_outcomes_for_agent_effectiveness": True,
            "static_report_metrics_flagged": True,
        },
    }
