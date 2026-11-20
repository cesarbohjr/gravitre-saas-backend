"""Read-only GA4 metric evidence from an authenticated persisted workflow run.

This is not a connector, planner, or execution path. It consumes the existing
workflow runtime's snapshots after the caller's tenant/environment boundary.
GA4 reported observations are not CRM conversions or incremental revenue.
"""
from __future__ import annotations

import math
import re
from datetime import date
from typing import Any

from app.workflows.repository import get_run_with_steps

_ALLOWED_METRICS = frozenset({"sessions", "activeUsers", "totalUsers", "eventCount", "keyEvents"})
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class AnalyticsEvidenceBlocked(ValueError):
    pass


def _iso_date(value: Any) -> date:
    text = str(value or "")
    if not _DATE.fullmatch(text):
        raise AnalyticsEvidenceBlocked("explicit_ga4_date_range_required")
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise AnalyticsEvidenceBlocked("invalid_ga4_date_range") from exc


def diagnose_ga4_run(*, client: Any, org_id: str, environment_name: str, run_id: str) -> dict[str, Any] | None:
    """Require one completed GA4 report step from a real workflow run.

    No external request is made. A successful provider tool response is an
    observed report, not independent confirmation of business causality.
    """
    if not org_id or not environment_name or not run_id:
        raise AnalyticsEvidenceBlocked("authenticated_run_context_required")
    run = get_run_with_steps(client, org_id, run_id, environment_name)
    if run is None:
        return None
    if run.get("org_id") != org_id or run.get("environment") != environment_name:
        raise AnalyticsEvidenceBlocked("ga4_tenant_environment_mismatch")
    if run.get("run_type") != "execute" or run.get("status") != "completed":
        raise AnalyticsEvidenceBlocked("completed_ga4_execution_required")
    snapshot = run.get("definition_snapshot")
    steps = snapshot.get("steps") if isinstance(snapshot, dict) else None
    if not isinstance(steps, list) or len(steps) != 1:
        raise AnalyticsEvidenceBlocked("single_ga4_report_step_required")
    definition = steps[0]
    if not isinstance(definition, dict) or definition.get("type") != "invoke_tool":
        raise AnalyticsEvidenceBlocked("ga4_invoke_tool_required")
    config = definition.get("config")
    if not isinstance(config, dict) or config.get("action") != "analytics.reports.run":
        raise AnalyticsEvidenceBlocked("unsupported_ga4_action")
    start, end = _iso_date(config.get("start_date")), _iso_date(config.get("end_date"))
    if end < start:
        raise AnalyticsEvidenceBlocked("invalid_ga4_date_range")
    dimensions, metrics = config.get("dimensions"), config.get("metrics")
    # The GA4 tool defaults to campaign segmentation and two metrics if unset.
    # Require explicitly bound fields so an implicit shape is never mistaken
    # for an aggregate KPI. Only the dimensionless report is a total.
    if dimensions != ["date"] or not isinstance(metrics, list) or len(metrics) != 1 or metrics[0] not in _ALLOWED_METRICS:
        raise AnalyticsEvidenceBlocked("explicit_ga4_dimension_and_metric_required")
    expected_id = str(definition.get("id") or "")
    if not expected_id:
        raise AnalyticsEvidenceBlocked("ga4_step_identity_required")
    actual = run.get("steps")
    if not isinstance(actual, list) or len(actual) != 1:
        raise AnalyticsEvidenceBlocked("ga4_persisted_step_count_mismatch")
    step = actual[0]
    if (step.get("org_id") != org_id or str(step.get("run_id")) != run_id
            or step.get("step_id") != expected_id or step.get("status") != "completed"):
        raise AnalyticsEvidenceBlocked("ga4_persisted_step_mismatch")
    output = step.get("output_snapshot")
    if not isinstance(output, dict) or output.get("simulated") is True or output.get("success") is not True:
        raise AnalyticsEvidenceBlocked("ga4_successful_provider_snapshot_required")
    if output.get("invoke_action") != "analytics.reports.run":
        raise AnalyticsEvidenceBlocked("ga4_provider_action_mismatch")
    payload = output.get("data") if isinstance(output.get("data"), dict) else output
    property_id, report = payload.get("property_id"), payload.get("report")
    if not str(property_id or "").isdigit() or not isinstance(report, dict):
        raise AnalyticsEvidenceBlocked("ga4_property_and_report_required")
    if report.get("propertyQuota") is not None and not isinstance(report["propertyQuota"], dict):
        raise AnalyticsEvidenceBlocked("invalid_ga4_property_quota")
    metadata = report.get("metadata") or {}
    if not isinstance(metadata, dict) or metadata.get("subjectToThresholding") is True or metadata.get("dataLossFromOtherRow") is True:
        raise AnalyticsEvidenceBlocked("ga4_privacy_threshold_or_data_loss")
    headers, dimension_headers = report.get("metricHeaders"), report.get("dimensionHeaders")
    if not isinstance(headers, list) or [h.get("name") for h in headers if isinstance(h, dict)] != metrics:
        raise AnalyticsEvidenceBlocked("ga4_metric_header_mismatch")
    if not isinstance(dimension_headers, list) or [h.get("name") for h in dimension_headers if isinstance(h, dict)] != ["date"]:
        raise AnalyticsEvidenceBlocked("ga4_dimension_header_mismatch")
    rows = report.get("rows") or []
    count = report.get("rowCount")
    if not isinstance(rows, list) or type(count) is not int or count != len(rows):
        raise AnalyticsEvidenceBlocked("ga4_incomplete_report_coverage")
    observations = []
    dates: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise AnalyticsEvidenceBlocked("invalid_ga4_row")
        d, v = row.get("dimensionValues"), row.get("metricValues")
        if not isinstance(d, list) or len(d) != 1 or not isinstance(v, list) or len(v) != 1:
            raise AnalyticsEvidenceBlocked("invalid_ga4_row")
        raw_date = str((d[0] or {}).get("value") or "") if isinstance(d[0], dict) else ""
        if not re.fullmatch(r"\d{8}", raw_date):
            raise AnalyticsEvidenceBlocked("invalid_ga4_report_date")
        try:
            day = date.fromisoformat(f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:]}")
        except ValueError as exc:
            raise AnalyticsEvidenceBlocked("invalid_ga4_report_date") from exc
        if not start <= day <= end or raw_date in dates:
            raise AnalyticsEvidenceBlocked("ga4_duplicate_or_outside_date")
        dates.add(raw_date)
        try:
            value = float(v[0]["value"])
        except (KeyError, ValueError, TypeError, OverflowError) as exc:
            raise AnalyticsEvidenceBlocked("invalid_ga4_metric_value") from exc
        if not math.isfinite(value) or value < 0 or not value.is_integer():
            raise AnalyticsEvidenceBlocked("invalid_ga4_metric_value")
        observations.append({"date": day.isoformat(), "value": int(value)})
    # Do not assume absent days mean zero, or sum rows into a total without
    # verifying complete day coverage and calendar attribution.
    return {
        "status": "GA4_DAILY_ROWS_OBSERVED_NOT_AGGREGATED" if observations else "GA4_EMPTY_REPORT",
        "org_id": org_id, "environment": environment_name,
        "run_id": run_id, "property_id": str(property_id),
        "metric_key": metrics[0], "unit": "count",
        "date_range": {"start": start.isoformat(), "end": end.isoformat()},
        "rows": observations,
        "row_count": count,
        "business_outcome": "NOT_MEASURED",
        "diagnosis": "OBSERVATIONS_ONLY",
        "recommended_writes": [],
    }
