"""Read-only production evidence collector for Marketplace 3.0 certification.

This module never fabricates evidence and never performs a consequential write.
It inspects Gravitre's canonical install, Play-run, workflow-run, and verified
business-result ledgers. Missing proof remains false.
"""
from __future__ import annotations

from typing import Any

from app.connectors.action_catalog.registry import get_action_spec
from app.marketplace.schemas import OutcomePackAssetConfig
from app.plays.outcomes import PLAY_BUSINESS_RESULT_EVENT, BusinessResultStatus


def _configuration(row: dict[str, Any]) -> dict[str, Any]:
    value = row.get("configuration")
    return value if isinstance(value, dict) else {}


def _metadata(row: dict[str, Any]) -> dict[str, Any]:
    value = row.get("metadata")
    return value if isinstance(value, dict) else {}


def _string_set(values: Any) -> set[str]:
    if not isinstance(values, list):
        return set()
    return {str(value).strip() for value in values if str(value).strip()}


def collect_production_evidence(
    client: Any,
    *,
    org_id: str,
    asset_id: str,
    config: OutcomePackAssetConfig,
) -> dict[str, Any]:
    expected_play_keys = {play.key for play in config.plays}

    marketplace_rows = (
        client.table("marketplace_installs")
        .select("id, asset_id, status, metadata, installed_at")
        .eq("org_id", org_id)
        .eq("asset_id", asset_id)
        .eq("status", "active")
        .execute()
        .data
        or []
    )
    marketplace_install = dict(marketplace_rows[0]) if marketplace_rows else {}
    install_meta = _metadata(marketplace_install)
    installed_agent_ids = _string_set(install_meta.get("agentIds"))
    installed_rag_ids = _string_set(install_meta.get("ragSourceIds"))
    installed_pack_play_keys = {
        str(row.get("playKey") or "").strip()
        for row in (install_meta.get("plays") or [])
        if isinstance(row, dict) and str(row.get("playKey") or "").strip()
    }

    play_install_rows = (
        client.table("play_installations")
        .select("id, play_key, status, environment_name, configuration")
        .eq("org_id", org_id)
        .execute()
        .data
        or []
    )
    pack_play_installs = [
        dict(row)
        for row in play_install_rows
        if str(_configuration(row).get("marketplaceAssetId") or "") == asset_id
    ]
    installed_play_keys = {
        str(row.get("play_key") or "").strip()
        for row in pack_play_installs
        if str(row.get("status") or "") in {"ready", "active"}
    }
    play_installation_ids = {
        str(row.get("id") or "")
        for row in pack_play_installs
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

    agent_contract_ok = len(installed_agent_ids) >= len(config.agents)
    knowledge_contract_ok = (
        not config.knowledge or len(installed_rag_ids) >= len(config.knowledge)
    )
    plays_contract_ok = (
        expected_play_keys == installed_play_keys
        and expected_play_keys <= installed_pack_play_keys
    )
    fresh_install_passed = (
        bool(marketplace_install)
        and agent_contract_ok
        and knowledge_contract_ok
        and plays_contract_ok
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
        .limit(1000)
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
        str(row.get("play_key") or "").strip()
        for row in pack_play_runs
        if str(row.get("status") or "").lower() == "completed"
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
        and str(row.get("status") or "").lower()
        in {"completed", "partial_success", "failed", "cancelled"}
    ]
    failure_play_keys = {
        str(row.get("play_key") or "").strip()
        for row in failure_rows
        if str(row.get("play_key") or "").strip()
    }
    failure_path_passed = expected_play_keys == failure_play_keys

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

    declared_runtime_actions = {
        action
        for profile in config.runtime_profiles
        for action in profile.actions
    }
    completed_read_actions: set[str] = set()
    verified_write_actions: set[str] = set()
    verified_write_rows: list[dict[str, Any]] = []
    action_run_ids: dict[str, set[str]] = {}

    for row in workflow_rows:
        params = row.get("parameters") if isinstance(row.get("parameters"), dict) else {}
        action = str(params.get("invoke_action") or "").strip()
        if not action or action not in declared_runtime_actions:
            continue
        spec = get_action_spec(action)
        if spec is None:
            continue
        run_id = str(row.get("id") or "").strip()
        if run_id:
            action_run_ids.setdefault(action, set()).add(run_id)
        completed = str(row.get("status") or "").lower() == "completed"
        if spec.kind == "read":
            if completed:
                completed_read_actions.add(action)
            continue

        verification = (
            params.get("verification")
            if isinstance(params.get("verification"), dict)
            else {}
        )
        verification_state = str(
            params.get("verification_status")
            or verification.get("state")
            or verification.get("status")
            or ""
        ).strip().lower()
        verified = (
            completed
            and bool(verification.get("verified"))
            and verification_state
            in {
                "verified",
                "completed",
                "success",
                "verified_success",
                "verified success",
            }
        )
        if verified:
            verified_write_actions.add(action)
            verified_write_rows.append(
                {
                    "runId": run_id,
                    "action": action,
                    "verification": verification,
                }
            )

    declared_write_actions = {
        action
        for action in declared_runtime_actions
        if (get_action_spec(action) is not None and get_action_spec(action).kind != "read")
    }
    source_of_record_verification_passed = (
        not declared_write_actions
        or declared_write_actions <= verified_write_actions
    )

    verified_runtime_actions = completed_read_actions | verified_write_actions
    runtime_evidence: dict[str, Any] = {}
    for profile in config.runtime_profiles:
        profile_actions = set(profile.actions)
        run_ids = sorted(
            {
                run_id
                for action in profile_actions
                for run_id in action_run_ids.get(action, set())
            }
        )
        runtime_evidence[profile.provider] = {
            "environment": "production",
            "evidence_ref": (
                "workflow_runs:" + ",".join(run_ids)
                if run_ids
                else ""
            ),
            "verified_actions": sorted(profile_actions & verified_runtime_actions),
        }

    result_rows = (
        client.table("intelligence_outcome_events")
        .select(
            "id, outcome_event, workflow_run_id, before_value, after_value, "
            "measurement_status, metadata, measured_at"
        )
        .eq("org_id", org_id)
        .eq("outcome_event", PLAY_BUSINESS_RESULT_EVENT)
        .order("created_at", desc=True)
        .limit(1000)
        .execute()
        .data
        or []
    )
    declared_kpis = {item.key for item in config.outcome_contract.kpis}
    verified_metric_keys: set[str] = set()
    verified_outcome_events: set[str] = set()
    verified_result_ids: list[str] = []

    for row in result_rows:
        meta = _metadata(row)
        if str(meta.get("play_key") or "").strip() not in expected_play_keys:
            continue
        if (
            str(meta.get("verification_state") or "").strip().upper()
            != BusinessResultStatus.VERIFIED_SUCCESS.value
        ):
            continue
        metric_key = str(meta.get("metric_key") or "").strip()
        if metric_key:
            verified_metric_keys.add(metric_key)
        outcome_type = str(meta.get("outcome_type") or "").strip()
        if outcome_type:
            verified_outcome_events.add(outcome_type)
        if row.get("id"):
            verified_result_ids.append(str(row["id"]))

    dashboard_kpis = {item.kpi_key for item in config.dashboard.metrics}
    kpi_reconciliation_passed = (
        bool(dashboard_kpis)
        and dashboard_kpis <= declared_kpis
        and dashboard_kpis <= verified_metric_keys
    )

    return {
        "runner_mode": "production_evidence_inspection",
        "fresh_install_passed": fresh_install_passed,
        "golden_path_passed": golden_path_passed,
        "failure_path_passed": failure_path_passed,
        # User-context RLS proof is injected by permissions_probe.
        "permissions_passed": False,
        "kpi_reconciliation_passed": kpi_reconciliation_passed,
        "source_of_record_verification_passed": source_of_record_verification_passed,
        "runtime_evidence": runtime_evidence,
        "verified_outcome_events": sorted(verified_outcome_events),
        "proof": {
            "marketplaceInstallId": str(marketplace_install.get("id") or ""),
            "expectedPlayKeys": sorted(expected_play_keys),
            "installedPlayKeys": sorted(installed_play_keys),
            "marketplaceInstallPlayKeys": sorted(installed_pack_play_keys),
            "installedAgentIds": sorted(installed_agent_ids),
            "installedKnowledgeSourceIds": sorted(installed_rag_ids),
            "goldenPlayKeys": sorted(golden_play_keys),
            "failurePlayKeys": sorted(failure_play_keys),
            "failurePathRunIds": [
                str(row.get("id") or "") for row in failure_rows if row.get("id")
            ],
            "verifiedWriteRuns": verified_write_rows,
            "verifiedMetricKeys": sorted(verified_metric_keys),
            "verifiedBusinessResultIds": verified_result_ids,
            "datasetInstallIds": [str(row.get("id") or "") for row in dataset_rows],
            "dashboardInstallIds": [str(row.get("id") or "") for row in dashboard_rows],
        },
    }
