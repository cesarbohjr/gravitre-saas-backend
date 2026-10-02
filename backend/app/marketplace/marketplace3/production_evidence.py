"""Read-only production evidence collector for Marketplace 3.0 certification.

This module never fabricates evidence and never performs a consequential write.
It inspects Gravitre's canonical install, Play-run, workflow-run, and verified
business-result ledgers. Any missing proof remains false.
"""
from __future__ import annotations

from typing import Any

from app.marketplace.schemas import OutcomePackAssetConfig
from app.plays.outcomes import PLAY_BUSINESS_RESULT_EVENT


def _configuration(row: dict[str, Any]) -> dict[str, Any]:
    value = row.get("configuration")
    return value if isinstance(value, dict) else {}


def _metadata(row: dict[str, Any]) -> dict[str, Any]:
    value = row.get("metadata")
    return value if isinstance(value, dict) else {}


def collect_production_evidence(
    client: Any,
    *,
    org_id: str,
    asset_id: str,
    config: OutcomePackAssetConfig,
) -> dict[str, Any]:
    expected_play_keys = {play.key for play in config.plays}

    install_rows = (
        client.table("play_installations")
        .select("id, play_key, status, environment_name, configuration")
        .eq("org_id", org_id)
        .execute()
        .data
        or []
    )
    pack_installs = [
        dict(row)
        for row in install_rows
        if str(_configuration(row).get("marketplaceAssetId") or "") == asset_id
    ]
    installed_play_keys = {
        str(row.get("play_key") or "")
        for row in pack_installs
        if str(row.get("status") or "") in {"ready", "active"}
    }
    play_installation_ids = {
        str(row.get("id") or "")
        for row in pack_installs
        if str(row.get("id") or "")
    }

    dataset_rows = (
        client.table("marketplace_dataset_pack_installations")
        .select("id, asset_id, status")
        .eq("org_id", org_id)
        .eq("asset_id", asset_id)
        .eq("status", "active")
        .execute()
        .data
        or []
    )
    dashboard_rows = (
        client.table("marketplace_dashboard_pack_installations")
        .select("id, asset_id, status")
        .eq("org_id", org_id)
        .eq("asset_id", asset_id)
        .eq("status", "active")
        .execute()
        .data
        or []
    )
    fresh_install_passed = (
        expected_play_keys == installed_play_keys
        and bool(dataset_rows)
        and bool(dashboard_rows)
    )

    play_run_rows = (
        client.table("play_runs")
        .select(
            "id, installation_id, play_key, status, workflow_run_ids, metadata, created_at"
        )
        .eq("org_id", org_id)
        .order("created_at", desc=True)
        .limit(500)
        .execute()
        .data
        or []
    )
    pack_play_runs = [
        dict(row)
        for row in play_run_rows
        if str(row.get("installation_id") or "") in play_installation_ids
    ]

    golden_play_keys = {
        str(row.get("play_key") or "")
        for row in pack_play_runs
        if str(row.get("status") or "") == "completed"
        and _metadata(row).get("certificationScenario") == "golden_path"
        and _metadata(row).get("certificationExpected") is True
    }
    golden_path_passed = expected_play_keys == golden_play_keys

    failure_rows = [
        row
        for row in pack_play_runs
        if _metadata(row).get("certificationScenario") == "failure_path"
        and _metadata(row).get("certificationExpected") is True
        and _metadata(row).get("failureHandledSafely") is True
        and str(row.get("status") or "") in {
            "completed",
            "partial_success",
            "failed",
            "cancelled",
        }
    ]
    failure_path_passed = bool(failure_rows)

    workflow_run_ids: set[str] = set()
    for row in pack_play_runs:
        for value in row.get("workflow_run_ids") or []:
            text = str(value or "").strip()
            if text:
                workflow_run_ids.add(text)

    workflow_rows: list[dict[str, Any]] = []
    if workflow_run_ids:
        rows = (
            client.table("workflow_runs")
            .select("id, status, parameters")
            .eq("org_id", org_id)
            .in_("id", sorted(workflow_run_ids))
            .execute()
            .data
            or []
        )
        workflow_rows = [dict(row) for row in rows]

    verified_write_rows: list[dict[str, Any]] = []
    for row in workflow_rows:
        params = row.get("parameters") if isinstance(row.get("parameters"), dict) else {}
        action = str(params.get("invoke_action") or "").strip()
        if not action:
            continue
        verification = params.get("verification") if isinstance(params.get("verification"), dict) else {}
        if (
            str(params.get("verification_status") or "").lower() == "verified"
            and bool(verification.get("verified"))
            and str(row.get("status") or "").lower() == "completed"
        ):
            verified_write_rows.append(
                {
                    "runId": str(row.get("id") or ""),
                    "action": action,
                    "verification": verification,
                }
            )
    source_of_record_verification_passed = bool(verified_write_rows)

    result_rows = (
        client.table("intelligence_outcome_events")
        .select(
            "id, outcome_event, workflow_run_id, before_value, after_value, "
            "measurement_status, metadata, measured_at"
        )
        .eq("org_id", org_id)
        .eq("outcome_event", PLAY_BUSINESS_RESULT_EVENT)
        .order("created_at", desc=True)
        .limit(500)
        .execute()
        .data
        or []
    )
    declared_kpis = {item.key for item in config.outcome_contract.kpis}
    verified_metric_keys: set[str] = set()
    verified_outcome_events: set[str] = set()
    for row in result_rows:
        meta = _metadata(row)
        if str(meta.get("play_key") or "") not in expected_play_keys:
            continue
        if str(meta.get("verification_state") or "") != "VERIFIED SUCCESS":
            continue
        metric_key = str(meta.get("metric_key") or "").strip()
        if metric_key:
            verified_metric_keys.add(metric_key)
        outcome_type = str(meta.get("outcome_type") or "").strip()
        if outcome_type:
            verified_outcome_events.add(outcome_type)

    # Live KPI proof requires every dashboard KPI to have a verified measured
    # result; static formula coverage alone is intentionally insufficient.
    dashboard_kpis = {item.kpi_key for item in config.dashboard.metrics}
    kpi_reconciliation_passed = (
        bool(dashboard_kpis)
        and dashboard_kpis <= declared_kpis
        and dashboard_kpis <= verified_metric_keys
    )

    # RLS/permission isolation cannot be proven truthfully from the service-role
    # client used by the API. It must be supplied by the dedicated auth-context
    # certification probe; until then production certification remains blocked.
    permissions_passed = False

    return {
        "runner_mode": "production_evidence_inspection",
        "fresh_install_passed": fresh_install_passed,
        "golden_path_passed": golden_path_passed,
        "failure_path_passed": failure_path_passed,
        "permissions_passed": permissions_passed,
        "kpi_reconciliation_passed": kpi_reconciliation_passed,
        "source_of_record_verification_passed": source_of_record_verification_passed,
        "verified_outcome_events": sorted(verified_outcome_events),
        "proof": {
            "expectedPlayKeys": sorted(expected_play_keys),
            "installedPlayKeys": sorted(installed_play_keys),
            "goldenPlayKeys": sorted(golden_play_keys),
            "failurePathRunIds": [
                str(row.get("id") or "") for row in failure_rows
            ],
            "verifiedWriteRuns": verified_write_rows,
            "verifiedMetricKeys": sorted(verified_metric_keys),
            "datasetInstallIds": [str(row.get("id") or "") for row in dataset_rows],
            "dashboardInstallIds": [str(row.get("id") or "") for row in dashboard_rows],
        },
    }
