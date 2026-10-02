"""System-generated Marketplace 3.0 certification runner.

The runner intentionally separates fixture/static evidence from live production
proof. Fixture checks can discover defects and persist a certification report,
but they never set the production-proof booleans required for publication.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from app.connectors.action_catalog.registry import get_action_spec
from app.marketplace.marketplace3.certification_store import (
    certify_and_record_outcome_pack,
    get_outcome_pack_certification,
)
from app.marketplace.schemas import OutcomePackAssetConfig
from app.marketplace.marketplace3.production_evidence import collect_production_evidence
from app.services.tool_service import list_registered_actions
from app.services.write_success_verification import resolve_success_verification


CertificationRunMode = Literal["fixture", "production"]


@dataclass(frozen=True)
class RunnerCheck:
    key: str
    passed: bool
    detail: str
    metadata: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "passed": self.passed,
            "detail": self.detail,
            "metadata": self.metadata or {},
        }


class CertificationRunnerError(Exception):
    code = "MARKETPLACE_3_CERTIFICATION_RUNNER_ERROR"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        if code:
            self.code = code


def _load_asset(client: Any, org_id: str, asset_ref: str) -> dict[str, Any]:
    query = client.table("marketplace_assets").select("*").eq("org_id", org_id)
    if len(asset_ref) == 36 and asset_ref.count("-") == 4:
        query = query.eq("id", asset_ref)
    else:
        query = query.eq("slug", asset_ref)
    result = query.limit(1).execute()
    rows = result.data or []
    if not rows:
        raise CertificationRunnerError("Outcome Pack asset not found", code="NOT_FOUND")
    asset = dict(rows[0])
    if str(asset.get("asset_type") or "") != "outcome_pack":
        raise CertificationRunnerError(
            "Certification runner only supports Marketplace 3.0 Outcome Packs",
            code="INVALID_ASSET_TYPE",
        )
    return asset


def _play_agent_seeds(config: OutcomePackAssetConfig) -> set[str]:
    seeds: set[str] = set()
    for play in config.plays:
        for step in play.workflow_steps:
            if step.get("type") != "agent":
                continue
            metadata = step.get("metadata") if isinstance(step.get("metadata"), dict) else {}
            seed = str(metadata.get("agent_seed") or "").strip()
            if seed:
                seeds.add(seed)
    return seeds


def _declared_agent_seeds(config: OutcomePackAssetConfig) -> set[str]:
    return {
        str(agent.seed_label or "").strip()
        for agent in config.agents
        if str(agent.seed_label or "").strip()
    }


def _workflow_actions(config: OutcomePackAssetConfig) -> set[str]:
    actions: set[str] = set()
    for play in config.plays:
        for step in play.workflow_steps:
            if step.get("type") != "invoke_tool":
                continue
            row = step.get("config") if isinstance(step.get("config"), dict) else {}
            action = str(row.get("action") or row.get("tool_action") or "").strip()
            if action:
                actions.add(action)
    return actions


def _fixture_checks(config: OutcomePackAssetConfig) -> list[RunnerCheck]:
    checks: list[RunnerCheck] = []

    declared_kpis = {item.key for item in config.outcome_contract.kpis}
    dataset_kpis = {item.key for item in config.dataset.metrics}
    dashboard_kpis = {item.kpi_key for item in config.dashboard.metrics}
    missing_dataset = sorted(declared_kpis - dataset_kpis)
    missing_dashboard = sorted(declared_kpis - dashboard_kpis)
    checks.append(
        RunnerCheck(
            key="kpi_contract_coverage",
            passed=not missing_dataset and not missing_dashboard,
            detail=(
                "Every declared KPI has a dataset metric and dashboard metric."
                if not missing_dataset and not missing_dashboard
                else "One or more declared KPIs are missing dataset/dashboard definitions."
            ),
            metadata={
                "missingDatasetKpis": missing_dataset,
                "missingDashboardKpis": missing_dashboard,
            },
        )
    )

    play_seeds = _play_agent_seeds(config)
    agent_seeds = _declared_agent_seeds(config)
    missing_agents = sorted(play_seeds - agent_seeds)
    checks.append(
        RunnerCheck(
            key="play_agent_bindings",
            passed=not missing_agents,
            detail=(
                "Every Play agent reference resolves to a declared Outcome Pack agent."
                if not missing_agents
                else "One or more Play agent references are unresolved."
            ),
            metadata={"missingAgentSeeds": missing_agents},
        )
    )

    registered = set(list_registered_actions())
    workflow_actions = _workflow_actions(config)
    declared_actions = {
        action
        for profile in config.runtime_profiles
        for action in profile.actions
    }
    actions = workflow_actions | declared_actions
    missing_actions = sorted(actions - registered)
    checks.append(
        RunnerCheck(
            key="runtime_actions_registered",
            passed=not missing_actions,
            detail=(
                "Every invoke_tool action is registered in Gravitre."
                if not missing_actions
                else "One or more invoke_tool actions are not registered."
            ),
            metadata={"missingActions": missing_actions},
        )
    )

    governance_failures: list[dict[str, Any]] = []
    for action in sorted(actions):
        spec = get_action_spec(action)
        if spec is None:
            governance_failures.append({"action": action, "reason": "action_spec_missing"})
            continue
        if spec.kind == "read":
            continue
        if not spec.requires_approval:
            governance_failures.append({"action": action, "reason": "approval_not_required"})
        verification = resolve_success_verification(action)
        if verification.mode == "accepted_async":
            governance_failures.append(
                {"action": action, "reason": "source_verification_missing"}
            )
        elif verification.mode in {"follow_up_entity_get", "follow_up_field_assert"}:
            read_action = str(verification.read_action or "").strip()
            if not read_action or read_action not in registered:
                governance_failures.append(
                    {
                        "action": action,
                        "reason": "verification_read_unavailable",
                        "readAction": read_action,
                    }
                )
    checks.append(
        RunnerCheck(
            key="write_governance_contract",
            passed=not governance_failures,
            detail=(
                "All declared writes are approval-governed and independently verifiable."
                if not governance_failures
                else "One or more write actions fail Marketplace 3.0 governance requirements."
            ),
            metadata={"failures": governance_failures},
        )
    )

    duplicate_events = len(config.outcome_contract.outcome_events) != len(
        set(config.outcome_contract.outcome_events)
    )
    play_events = {
        event
        for play in config.plays
        for event in play.outcome_events
    }
    undeclared_play_events = sorted(
        play_events - set(config.outcome_contract.outcome_events)
    )
    checks.append(
        RunnerCheck(
            key="outcome_event_contract",
            passed=not duplicate_events and not undeclared_play_events,
            detail=(
                "Play outcome events reconcile to the Outcome Contract."
                if not duplicate_events and not undeclared_play_events
                else "Outcome-event declarations are inconsistent."
            ),
            metadata={
                "duplicateContractEvents": duplicate_events,
                "undeclaredPlayEvents": undeclared_play_events,
            },
        )
    )

    return checks


def run_outcome_pack_certification(
    client: Any,
    *,
    org_id: str,
    asset_ref: str,
    actor_id: str,
    mode: CertificationRunMode = "fixture",
    permission_probe: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run system-owned certification checks and persist their evidence.

    Fixture mode never grants production evidence. Production mode is reserved
    for the live-provider runner and deliberately fails closed until that runner
    supplies actual install/execution/source-of-record proof.
    """
    asset = _load_asset(client, org_id, asset_ref)
    config = OutcomePackAssetConfig.model_validate(asset.get("config") or {})
    checks = _fixture_checks(config)
    fixture_passed = all(check.passed for check in checks)

    if mode == "production":
        evidence = collect_production_evidence(
            client,
            org_id=org_id,
            asset_id=str(asset["id"]),
            config=config,
        )
        evidence["fixture_checks_passed"] = fixture_passed
        evidence["fixture_checks"] = [check.as_dict() for check in checks]
        if permission_probe is not None:
            evidence["permission_probe"] = permission_probe
            evidence["permissions_passed"] = permission_probe.get("passed") is True
    else:
        evidence = {
            "runner_mode": "fixture",
            "fixture_checks_passed": fixture_passed,
            "fixture_checks": [check.as_dict() for check in checks],
            # Required production proof stays false in fixture mode by design.
            "fresh_install_passed": False,
            "golden_path_passed": False,
            "failure_path_passed": False,
            "permissions_passed": False,
            "kpi_reconciliation_passed": False,
            "source_of_record_verification_passed": False,
        }

    resolved_skill_ids = {
        str(package_id).strip()
        for package_id in config.skill_bindings.values()
        if str(package_id).strip()
    }
    certification = certify_and_record_outcome_pack(
        client,
        org_id=org_id,
        asset_id=str(asset["id"]),
        config=config,
        actor_id=actor_id,
        resolved_skill_ids=resolved_skill_ids,
        evidence=evidence,
    )
    return {
        "assetId": str(asset["id"]),
        "slug": asset.get("slug"),
        "mode": mode,
        "fixturePassed": fixture_passed,
        "checks": [check.as_dict() for check in checks],
        "productionEvidence": evidence if mode == "production" else None,
        "certification": certification,
    }


def get_current_outcome_pack_certification(
    client: Any,
    *,
    org_id: str,
    asset_ref: str,
) -> dict[str, Any]:
    asset = _load_asset(client, org_id, asset_ref)
    config = OutcomePackAssetConfig.model_validate(asset.get("config") or {})
    current = get_outcome_pack_certification(
        client,
        org_id=org_id,
        asset_id=str(asset["id"]),
        config=config,
    )
    return {
        "assetId": str(asset["id"]),
        "slug": asset.get("slug"),
        "certification": current,
    }
