"""Marketplace 3.0 Outcome Pack certification.

Certification is deliberately stricter than schema validation. A syntactically
valid pack may remain a blueprint, but it cannot be published as a verified
operating capability until runtime actions, governance, verification, and skill
dependencies are real.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.connectors.action_catalog.registry import get_action_spec
from app.marketplace.schemas import OutcomePackAssetConfig
from app.services.tool_service import list_registered_actions
from app.services.write_success_verification import resolve_success_verification


_CERT_LEVELS = (
    "compatible",
    "tested",
    "governed",
    "production_verified",
    "outcome_verified",
)


@dataclass
class CertificationFinding:
    code: str
    message: str
    blocking: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "blocking": self.blocking,
            "metadata": self.metadata,
        }


@dataclass
class OutcomePackCertification:
    level: str
    publish_ready: bool
    findings: list[CertificationFinding]
    play_count: int
    runtime_actions: list[str]
    verified_skills: list[str]
    unresolved_skill_requirements: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "level": self.level,
            "publishReady": self.publish_ready,
            "playCount": self.play_count,
            "runtimeActions": self.runtime_actions,
            "verifiedSkills": self.verified_skills,
            "unresolvedSkillRequirements": self.unresolved_skill_requirements,
            "findings": [item.as_dict() for item in self.findings],
        }


def _workflow_actions(config: OutcomePackAssetConfig) -> set[str]:
    out: set[str] = set()
    for play in config.plays:
        for step in play.workflow_steps:
            if step.get("type") != "invoke_tool":
                continue
            step_config = step.get("config")
            if not isinstance(step_config, dict):
                continue
            action = str(
                step_config.get("action")
                or step_config.get("tool_action")
                or ""
            ).strip()
            if action:
                out.add(action)
    return out


def certify_outcome_pack(
    config: OutcomePackAssetConfig,
    *,
    resolved_skill_ids: set[str] | None = None,
    runtime_evidence: dict[str, Any] | None = None,
    production_evidence: dict[str, Any] | None = None,
    outcome_evidence: dict[str, Any] | None = None,
) -> OutcomePackCertification:
    """Return the strongest certification level supported by current evidence.

    This function never turns configuration intent into evidence. Runtime
    profiles describe supported/tested capability; production_verified is earned
    only from live, evidence-linked runtime, install, permission, KPI, failure
    path, and source-of-record proof.
    """
    findings: list[CertificationFinding] = []
    registered = set(list_registered_actions())
    runtime_actions = sorted(_workflow_actions(config))

    if len(config.plays) < 6:
        findings.append(
            CertificationFinding(
                "MINIMUM_PLAYS",
                "Marketplace 3.0 Outcome Packs require at least six meaningful Plays.",
            )
        )

    declared_actions = {
        action
        for profile in config.runtime_profiles
        for action in profile.actions
    }
    missing_registered = sorted(action for action in runtime_actions if action not in registered)
    if missing_registered:
        findings.append(
            CertificationFinding(
                "RUNTIME_ACTION_NOT_REGISTERED",
                "One or more workflow actions are not executable in Gravitre.",
                metadata={"actions": missing_registered},
            )
        )
    undeclared = sorted(set(runtime_actions) - declared_actions)
    if undeclared:
        findings.append(
            CertificationFinding(
                "RUNTIME_ACTION_UNDECLARED",
                "Workflow actions must belong to an explicit runtime profile.",
                metadata={"actions": undeclared},
            )
        )

    for action in sorted(declared_actions):
        spec = get_action_spec(action)
        if spec is None:
            findings.append(
                CertificationFinding(
                    "ACTION_SPEC_MISSING",
                    f"Action {action} is missing a Marketplace action specification.",
                    metadata={"action": action},
                )
            )
            continue
        if spec.kind != "read":
            if not spec.requires_approval:
                findings.append(
                    CertificationFinding(
                        "WRITE_APPROVAL_MISSING",
                        f"Write action {action} is not approval governed.",
                        metadata={"action": action},
                    )
                )
            verification = resolve_success_verification(action)
            if verification.mode == "accepted_async":
                findings.append(
                    CertificationFinding(
                        "WRITE_VERIFICATION_INCOMPLETE",
                        f"Write action {action} lacks independent source-of-record verification.",
                        metadata={"action": action, "mode": verification.mode},
                    )
                )
            if verification.mode in {"follow_up_entity_get", "follow_up_field_assert"}:
                read_action = str(verification.read_action or "").strip()
                if not read_action or read_action not in registered:
                    findings.append(
                        CertificationFinding(
                            "WRITE_VERIFICATION_READ_UNAVAILABLE",
                            f"Write verification for {action} depends on an unavailable read action.",
                            metadata={"action": action, "readAction": read_action},
                        )
                    )

    resolved_package_ids = set(resolved_skill_ids or set()) | set(config.skills)
    bound_requirements = {
        requirement
        for requirement, package_id in config.skill_bindings.items()
        if str(package_id).strip()
        and str(package_id).strip() in resolved_package_ids
    }
    unresolved_skills = sorted(
        requirement for requirement in config.skill_requirements
        if requirement not in bound_requirements
    )
    if unresolved_skills:
        findings.append(
            CertificationFinding(
                "SKILL_REQUIREMENTS_UNRESOLVED",
                "Required skill capabilities have not been resolved to reviewed Marketplace packages.",
                metadata={"requirements": unresolved_skills},
            )
        )

    runtime_statuses = {profile.status for profile in config.runtime_profiles}
    if not config.runtime_profiles:
        findings.append(
            CertificationFinding(
                "RUNTIME_PROFILE_MISSING",
                "Outcome Pack has no declared executable runtime profile.",
            )
        )

    evidence = runtime_evidence if isinstance(runtime_evidence, dict) else {}
    verified_profiles: set[str] = set()
    for profile in config.runtime_profiles:
        row = evidence.get(profile.provider)
        if not isinstance(row, dict):
            continue
        environment = str(row.get("environment") or "").strip().lower()
        evidence_ref = str(row.get("evidence_ref") or "").strip()
        verified_actions = {
            str(value).strip()
            for value in (row.get("verified_actions") or [])
            if str(value).strip()
        }
        if (
            environment == "production"
            and evidence_ref
            and set(profile.actions).issubset(verified_actions)
        ):
            verified_profiles.add(profile.provider)

    schema_runtime_ok = not any(
        finding.code in {
            "MINIMUM_PLAYS",
            "RUNTIME_ACTION_NOT_REGISTERED",
            "RUNTIME_ACTION_UNDECLARED",
            "ACTION_SPEC_MISSING",
        }
        for finding in findings
    )
    governed_ok = schema_runtime_ok and not any(
        finding.code in {
            "WRITE_APPROVAL_MISSING",
            "WRITE_VERIFICATION_INCOMPLETE",
            "WRITE_VERIFICATION_READ_UNAVAILABLE",
        }
        for finding in findings
    )

    level = "compatible"
    tested_runtime = (
        bool(runtime_statuses)
        and "implementation" not in runtime_statuses
        and runtime_statuses <= {"tested", "production_verified"}
    )
    if schema_runtime_ok and tested_runtime:
        level = "tested"
    if governed_ok and level == "tested":
        level = "governed"

    production_payload = (
        production_evidence if isinstance(production_evidence, dict) else {}
    )
    production_attempted = bool(production_payload) or bool(evidence) or any(
        profile.status == "production_verified" for profile in config.runtime_profiles
    )

    missing_live_profiles = sorted(
        profile.provider
        for profile in config.runtime_profiles
        if profile.provider not in verified_profiles
    )
    if production_attempted and missing_live_profiles:
        findings.append(
            CertificationFinding(
                "PRODUCTION_EVIDENCE_MISSING",
                "Production Verified requires evidence-linked live proof for every runtime profile and advertised action.",
                metadata={"providers": missing_live_profiles},
            )
        )

    required_production_checks = {
        "fixture_checks_passed": "Fixture certification checks did not all pass.",
        "fresh_install_passed": "A fresh composite Outcome Pack installation has not been proven.",
        "golden_path_passed": "Every Play has not completed its certified golden path.",
        "failure_path_passed": "Every Play has not demonstrated a safe failure path.",
        "permissions_passed": "Tenant permission/RLS isolation has not been proven with a user-scoped token.",
        "kpi_reconciliation_passed": "Dashboard KPIs have not reconciled to verified measured outcomes.",
        "source_of_record_verification_passed": "Consequential writes have not been independently verified against source of record.",
    }
    missing_production_checks = [
        key
        for key in required_production_checks
        if production_payload.get(key) is not True
    ]
    if production_attempted and missing_production_checks:
        findings.append(
            CertificationFinding(
                "PRODUCTION_EVIDENCE_INCOMPLETE",
                "Marketplace 3.0 production certification evidence is incomplete.",
                metadata={
                    "missingChecks": missing_production_checks,
                    "requirements": {
                        key: required_production_checks[key]
                        for key in missing_production_checks
                    },
                },
            )
        )

    production_ok = (
        governed_ok
        and tested_runtime
        and bool(config.runtime_profiles)
        and len(verified_profiles) == len(config.runtime_profiles)
        and not unresolved_skills
        and bool(production_payload)
        and not missing_production_checks
    )
    if production_ok:
        level = "production_verified"

    outcome_evidence_payload = outcome_evidence if isinstance(outcome_evidence, dict) else {}
    observed_events = {
        str(value)
        for value in (outcome_evidence_payload.get("verified_outcome_events") or [])
        if str(value).strip()
    }
    declared_events = set(config.outcome_contract.outcome_events)
    if production_ok and declared_events.intersection(observed_events):
        level = "outcome_verified"

    publish_ready = level in {"production_verified", "outcome_verified"}
    return OutcomePackCertification(
        level=level,
        publish_ready=publish_ready,
        findings=findings,
        play_count=len(config.plays),
        runtime_actions=runtime_actions,
        verified_skills=sorted(
            str(package_id).strip()
            for package_id in config.skill_bindings.values()
            if str(package_id).strip()
        ),
        unresolved_skill_requirements=unresolved_skills,
    )


def certification_level_rank(level: str) -> int:
    try:
        return _CERT_LEVELS.index(level)
    except ValueError:
        return -1
