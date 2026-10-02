"""Marketplace 3.0 certification runner.

Fixture and install-harness checks can fail a pack. They never grant
Production Verified or Outcome Verified by themselves.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.connectors.action_catalog.registry import get_action_spec
from app.marketplace.marketplace3.certification import certify_outcome_pack
from app.marketplace.marketplace3.certification_service import (
    Marketplace3CertificationError,
    certify_asset,
)
from app.marketplace.schemas import OutcomePackAssetConfig
from app.services.tool_service import list_registered_actions
from app.services.write_success_verification import resolve_success_verification


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

    def __init__(self, message: str, *, code: str | None = None, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        if code:
            self.code = code
        self.details = details or {}


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


def fixture_checks(config: OutcomePackAssetConfig) -> list[RunnerCheck]:
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
            detail="Every declared KPI has dataset and dashboard coverage."
            if not missing_dataset and not missing_dashboard
            else "Declared KPIs are missing dataset or dashboard coverage.",
            metadata={"missingDatasetKpis": missing_dataset, "missingDashboardKpis": missing_dashboard},
        )
    )

    missing_agents = sorted(_play_agent_seeds(config) - _declared_agent_seeds(config))
    checks.append(
        RunnerCheck(
            key="play_agent_bindings",
            passed=not missing_agents,
            detail="Every Play agent reference resolves to a declared agent."
            if not missing_agents
            else "One or more Play agent references are unresolved.",
            metadata={"missingAgentSeeds": missing_agents},
        )
    )

    registered = set(list_registered_actions())
    workflow_actions = _workflow_actions(config)
    missing_actions = sorted(workflow_actions - registered)
    checks.append(
        RunnerCheck(
            key="runtime_actions_registered",
            passed=not missing_actions,
            detail="Every invoke_tool action is registered."
            if not missing_actions
            else "One or more invoke_tool actions are not registered.",
            metadata={"missingActions": missing_actions},
        )
    )

    governance_failures: list[dict[str, Any]] = []
    for action in sorted(workflow_actions):
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
            governance_failures.append({"action": action, "reason": "source_verification_missing"})
    checks.append(
        RunnerCheck(
            key="write_governance_contract",
            passed=not governance_failures,
            detail="Write actions are approval-governed and independently verifiable."
            if not governance_failures
            else "Write-governance failures remain blocking.",
            metadata={"failures": governance_failures},
        )
    )

    play_events = {event for play in config.plays for event in play.outcome_events}
    undeclared = sorted(play_events - set(config.outcome_contract.outcome_events))
    checks.append(
        RunnerCheck(
            key="outcome_event_contract",
            passed=not undeclared,
            detail="Play outcome events reconcile to the Outcome Contract."
            if not undeclared
            else "Play outcome events are missing from the Outcome Contract.",
            metadata={"undeclaredPlayEvents": undeclared},
        )
    )

    missing_skill_bindings = sorted(set(config.skill_requirements) - set(config.skill_bindings))
    checks.append(
        RunnerCheck(
            key="skill_bindings_complete",
            passed=not missing_skill_bindings,
            detail="Required skills are bound to capability packages."
            if not missing_skill_bindings
            else "Required skills are missing package bindings.",
            metadata={"missingRequirements": missing_skill_bindings},
        )
    )

    six_plays = len(config.plays) >= 6
    checks.append(
        RunnerCheck(
            key="minimum_plays",
            passed=six_plays,
            detail="Outcome Pack includes at least six meaningful Plays."
            if six_plays
            else "Outcome Pack has fewer than six Plays.",
            metadata={"playCount": len(config.plays)},
        )
    )
    return checks


def evaluate_install_harness(
    *,
    golden_path_passed: bool,
    failure_path_closed: bool,
    observe_default: bool,
    approval_path_passed: bool,
    verification_path_passed: bool,
    uninstall_archives: bool,
    tenant_isolation_passed: bool,
    connector_alternative_or_group: bool,
) -> list[RunnerCheck]:
    cases = [
        ("golden_path", golden_path_passed, "Fresh install materializes required components."),
        ("failure_path_fail_closed", failure_path_closed, "Partial install cannot report success."),
        ("observe_default", observe_default, "Play installs start in OBSERVE mode."),
        ("approval_path", approval_path_passed, "Consequential writes remain approval-governed."),
        ("verification_path", verification_path_passed, "Provider acceptance is not terminal success."),
        ("uninstall_archives", uninstall_archives, "Uninstall archives spawned components."),
        ("tenant_isolation", tenant_isolation_passed, "Cross-org access is denied."),
        ("connector_or_group", connector_alternative_or_group, "Required connector classes use OR-group readiness."),
    ]
    return [
        RunnerCheck(key=key, passed=passed, detail=detail if passed else f"FAILED: {detail}")
        for key, passed, detail in cases
    ]


def run_outcome_pack_certification_runner(
    client: Any,
    *,
    slug: str,
    actor_id: str,
    runtime_evidence: dict[str, Any] | None = None,
    outcome_evidence: dict[str, Any] | None = None,
    install_harness: dict[str, bool] | None = None,
) -> dict[str, Any]:
    """Run fixture checks, persist them as evidence metadata, then certify.

    Failed fixture checks stay blocking. They are never rewritten as warnings.
    """
    from app.marketplace.marketplace3.certification_service import _asset_by_slug

    asset = _asset_by_slug(client, slug)
    if asset.get("asset_type") != "outcome_pack":
        raise CertificationRunnerError(
            "Certification runner only supports Outcome Packs",
            code="UNSUPPORTED_ASSET_TYPE",
        )
    config = OutcomePackAssetConfig.model_validate(asset.get("config") or {})
    checks = fixture_checks(config)
    if install_harness:
        checks.extend(
            evaluate_install_harness(
                golden_path_passed=bool(install_harness.get("golden_path_passed")),
                failure_path_closed=bool(install_harness.get("failure_path_closed")),
                observe_default=bool(install_harness.get("observe_default")),
                approval_path_passed=bool(install_harness.get("approval_path_passed")),
                verification_path_passed=bool(install_harness.get("verification_path_passed")),
                uninstall_archives=bool(install_harness.get("uninstall_archives")),
                tenant_isolation_passed=bool(install_harness.get("tenant_isolation_passed")),
                connector_alternative_or_group=bool(install_harness.get("connector_alternative_or_group")),
            )
        )
    failed = [check for check in checks if not check.passed]
    evidence_runtime = {} if failed else dict(runtime_evidence or {})
    evidence_runtime["runner"] = {
        "fixturePassed": not failed,
        "checks": [check.as_dict() for check in checks],
        "failedKeys": [check.key for check in failed],
    }
    try:
        persisted = certify_asset(
            client,
            slug=slug,
            actor_id=actor_id,
            runtime_evidence=evidence_runtime,
            outcome_evidence=outcome_evidence or {},
        )
    except Marketplace3CertificationError as exc:
        raise CertificationRunnerError(str(exc), code=exc.code, details=exc.details) from exc

    live = certify_outcome_pack(
        config,
        runtime_evidence=persisted["asset"]["certification_evidence"]["runtime"],
        outcome_evidence=persisted["asset"]["certification_evidence"]["outcome"],
    )
    runner_passed = not failed
    return {
        "passed": runner_passed,
        "fixturePassed": runner_passed,
        "checks": [check.as_dict() for check in checks],
        "failedChecks": [check.as_dict() for check in failed],
        "certification": persisted.get("certification") or live.as_dict(),
        "publishReady": bool((persisted.get("certification") or {}).get("publishReady")) and runner_passed,
    }
