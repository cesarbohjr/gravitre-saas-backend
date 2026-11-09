"""Tenant-bound cross-source diagnosis and governed intervention candidates.

Uses two already completed canonical workflow runs; no external calls, no
second agent engine, no cross-provider attribution without a join contract.
Bindings are advisory references to installed Plays and existing workflows.
Execution and approval continue exclusively through canonical Play/workflow APIs.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from app.services.analytics_metric_evidence import diagnose_ga4_run
from app.workflows.sales_growth_recipe import diagnose_authenticated_sales_run


class OpportunityAssessmentBlocked(ValueError):
    pass


# Explicitly selected intervention types, not inferred promises or arbitrary
# actions assembled by a language model. A missing installation is a blocker.
_CANDIDATES = (
    ("sales_pipeline_review", "revenue-leak-hunter", "Inspect CRM pipeline coverage", "sales"),
    ("acquisition_quality_review", "marketing-performance", "Review acquisition quality", "marketing"),
)


def assess_cross_source_opportunities(
    *,
    client: Any,
    org_id: str,
    environment_name: str,
    crm_run_id: str,
    analytics_run_id: str,
    as_of: datetime,
    installed_plays: list[dict[str, Any]],
    workflow_bindings: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    """Make evidence-linked *review candidates*, never authorize external writes.

    A GA4 session is not a HubSpot lead or deal. In the absence of a
    user-approved identity/attribution mapping, any funnel conversion
    calculation would be fabricated. Confidence is categorical, not an
    unsupported numeric probability.
    """
    if not org_id or not environment_name or not crm_run_id or not analytics_run_id:
        raise OpportunityAssessmentBlocked("authenticated_tenant_and_two_runs_required")
    if crm_run_id == analytics_run_id:
        raise OpportunityAssessmentBlocked("distinct_provider_runs_required")
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise OpportunityAssessmentBlocked("timezone_aware_assessment_required")
    try:
        crm = diagnose_authenticated_sales_run(
            client=client, org_id=org_id, environment_name=environment_name,
            run_id=crm_run_id,
        )
        analytics = diagnose_ga4_run(
            client=client, org_id=org_id, environment_name=environment_name,
            run_id=analytics_run_id,
        )
    except ValueError as exc:
        raise OpportunityAssessmentBlocked(str(exc)) from exc
    if crm is None or analytics is None:
        return {"status": "SOURCE_RUN_NOT_FOUND"}
    diagnosis = crm["diagnosis"]
    if not isinstance(diagnosis, dict):
        raise OpportunityAssessmentBlocked("crm_diagnosis_missing")
    crm_facts = diagnosis.get("observations") or []
    ga_rows = analytics.get("rows") or []
    ga_range = analytics.get("date_range") or {}
    if analytics.get("org_id") != org_id or analytics.get("environment") != environment_name:
        raise OpportunityAssessmentBlocked("analytics_tenant_mismatch")
    evidence: list[dict[str, Any]] = []
    now = as_of.astimezone(timezone.utc)
    for fact in crm_facts:
        if not isinstance(fact, dict) or fact.get("org_id") != org_id:
            raise OpportunityAssessmentBlocked("crm_evidence_tenant_mismatch")
        stamped = datetime.fromisoformat(str(fact.get("observed_at", "")).replace("Z", "+00:00"))
        if stamped.tzinfo is None or stamped > now or (now - stamped).days > 7:
            continue
        if fact.get("system") != "hubspot" or fact.get("metric_key") != "deals_record_count":
            continue
        evidence.append({
            "source": "hubspot", "run_id": crm_run_id,
            "metric": "deals_record_count", "value": fact["value"],
            "source_record_id": fact["source_record_id"],
            "observed_at": fact["observed_at"],
            "scope": "complete_persisted_deal_census",
        })
    # Daily rows are not aggregated into an estimate; even a complete report
    # may lack calendar dates (GA4 suppression, data readiness).
    try:
        end = date.fromisoformat(str(ga_range["end"]))
    except (KeyError, ValueError, TypeError) as exc:
        raise OpportunityAssessmentBlocked("ga4_date_scope_missing") from exc
    if end > now.date() or (now.date() - end).days > 7:
        ga_rows = []
    if ga_rows and analytics.get("status") == "GA4_DAILY_ROWS_OBSERVED_NOT_AGGREGATED":
        evidence.append({
            "source": "google_analytics", "run_id": analytics_run_id,
            "metric": analytics["metric_key"], "property_id": analytics["property_id"],
            "rows_observed": len(ga_rows), "date_range": ga_range,
            "scope": "daily_rows_no_cross_system_attribution",
        })

    installed = {
        str(row.get("play_key") or "").lower(): row
        for row in installed_plays
        if row.get("org_id") == org_id
        and row.get("environment_name") == environment_name
        and row.get("status") == "ready"
        and row.get("installed") is True
    }
    opportunities: list[dict[str, Any]] = []
    for key, play_key, title, department in _CANDIDATES:
        source = "hubspot" if department == "sales" else "google_analytics"
        supporting = [item for item in evidence if item["source"] == source]
        if not supporting:
            continue
        installation = installed.get(play_key)
        bindings = workflow_bindings.get(play_key) or []
        workflow_id = next((
            str(item.get("workflowId"))
            for item in bindings
            if item.get("org_id") == org_id
            and item.get("environment_name") == environment_name
            and item.get("status") not in {"archived", "deleted"}
            and str(item.get("workflowId") or "").strip()
        ), None)
        readiness = "REVIEW_REQUIRED" if installation and workflow_id else "NEEDS_PLAY_SETUP"
        opportunities.append({
            "id": key, "title": title, "department": department,
            "priority": "REVIEW" if source == "hubspot" else "INVESTIGATE",
            "confidence": "OBSERVATIONAL_ONLY",
            "impact_estimate": None, "cost_estimate": None,
            "evidence_refs": supporting,
            "assumptions": [
                "Cross-platform identity and attribution are not verified",
                "No causal performance improvement is established",
            ],
            "recommended_next_action": "Review the existing Play and its workflow",
            "status": readiness,
            "play_key": play_key if installation else None,
            "installation_id": str(installation.get("id")) if installation and installation.get("id") else None,
            "workflow_id": workflow_id if installation else None,
            "execution_authority": "NONE",
            "requires_approval": True,
            "execution_route": "canonical_play_or_workflow_only",
        })
    # Never turn a heuristic into an investment ROI ranking. Stable ordering
    # is based on evidence presence and source-specific investigation type.
    return {
        "status": "REVIEW_CANDIDATES" if opportunities else "INSUFFICIENT_CROSS_SOURCE_EVIDENCE",
        "org_id": org_id, "environment": environment_name,
        "source_runs": {"crm": crm_run_id, "analytics": analytics_run_id},
        "evidence": evidence,
        "opportunities": opportunities,
        "cross_source_conversion_rate": None,
        "attributed_revenue": None,
        "business_outcome": "NOT_MEASURED",
        "approval_status": "NOT_REQUESTED",
        "executed": False,
    }
