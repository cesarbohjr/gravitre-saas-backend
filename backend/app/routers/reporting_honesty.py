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
    normalize_agent_success_rate,
)
from app.services.agent_roi_service import fetch_agent_roi

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

    agent_roi: dict[str, Any] | None = None
    try:
        agent_roi = fetch_agent_roi(client, org_id, period_days=30)
        honesty = agent_roi.get("honesty") if isinstance(agent_roi, dict) else {}
        org_totals = (agent_roi or {}).get("orgTotals") or {}
        for field in (honesty.get("estimateFields") or []):
            metric = org_totals.get(field) or {}
            if metric.get("provenance") not in {"estimate", "insufficient_data"}:
                findings.append(
                    {
                        "surface": "enterprise_agent_roi",
                        "severity": "error",
                        "detail": f"{field} must be estimate/insufficient_data, got {metric.get('provenance')}",
                    }
                )
        for field in (honesty.get("measuredFields") or []):
            metric = org_totals.get(field) or {}
            if metric.get("provenance") != "measured":
                findings.append(
                    {
                        "surface": "enterprise_agent_roi",
                        "severity": "error",
                        "detail": f"{field} must be measured, got {metric.get('provenance')}",
                    }
                )
        for field in (honesty.get("operationalFields") or []):
            metric = org_totals.get(field) or {}
            if metric.get("provenance") != "operational":
                findings.append(
                    {
                        "surface": "enterprise_agent_roi",
                        "severity": "error",
                        "detail": f"{field} must be operational, got {metric.get('provenance')}",
                    }
                )
        rev = org_totals.get("revenueInfluencedUsd") or {}
        if rev.get("value") is not None and rev.get("provenance") == "not_configured":
            findings.append(
                {
                    "surface": "enterprise_agent_roi",
                    "severity": "error",
                    "detail": "revenueInfluencedUsd has value but provenance not_configured",
                }
            )
        if rev.get("value") is None and rev.get("provenance") not in {"not_configured", "measured"}:
            findings.append(
                {
                    "surface": "enterprise_agent_roi",
                    "severity": "warning",
                    "detail": f"unexpected revenue provenance {rev.get('provenance')}",
                }
            )
    except Exception as exc:  # noqa: BLE001
        findings.append(
            {
                "surface": "enterprise_agent_roi",
                "severity": "error",
                "detail": f"agent-roi unavailable: {str(exc)[:160]}",
            }
        )

    roi_metrics = []
    if agent_roi:
        totals = agent_roi.get("orgTotals") or {}
        for key in (
            "tasksCompleted",
            "agentCostUsd",
            "estimatedHoursSaved",
            "estimatedLaborValueUsd",
            "revenueInfluencedUsd",
            "roiMultiple",
        ):
            m = totals.get(key) or {}
            roi_metrics.append(
                {
                    "label": m.get("label") or key,
                    "value": m.get("value"),
                    "provenance": m.get("provenance"),
                    "honesty_ok": bool(m.get("honesty_ok", True)),
                    "note": m.get("note"),
                }
            )

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
            "agent_roi_agents": len((agent_roi or {}).get("agents") or []),
        },
        "roi_metrics": roi_metrics,
        "rules": {
            "never_default_success_rate_100_without_runs": True,
            "agent_roi_estimates_labeled": True,
            "agent_roi_revenue_only_with_evidence": True,
            "metrics_ranges": ["7d", "30d", "90d"],
            "prefer_live_outcomes_for_agent_effectiveness": True,
            "static_report_metrics_flagged": True,
        },
    }
