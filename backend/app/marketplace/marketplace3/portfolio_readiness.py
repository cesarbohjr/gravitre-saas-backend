"""Marketplace 3.0 portfolio readiness.

This module answers a narrow operational question: what is already built, what
passes Gravitre's static/fixture certification bar, and what evidence is still
required before a pack can be promoted. It never upgrades certification based
on fixture success alone.
"""
from __future__ import annotations

from typing import Any

from app.marketplace.marketplace3.certification import certify_outcome_pack
from app.marketplace.marketplace3.certification_runner import fixture_checks
from app.marketplace.marketplace3.department_portfolio import (
    department_portfolio_marketplace3_assets,
)
from app.marketplace.marketplace3.msp_service_desk import (
    msp_service_desk_marketplace3_assets,
)
from app.marketplace.schemas import OutcomePackAssetConfig


def _outcome_assets() -> list[Any]:
    assets = [
        *msp_service_desk_marketplace3_assets(),
        *department_portfolio_marketplace3_assets(),
    ]
    return [asset for asset in assets if asset.asset_type == "outcome_pack"]


def _next_gate(level: str, *, fixture_passed: bool, publish_ready: bool) -> str:
    if not fixture_passed:
        return "fix_fixture_or_contract_failures"
    if publish_ready and level == "outcome_verified":
        return "complete"
    if publish_ready and level == "production_verified":
        return "measured_outcome_evidence"
    if level == "governed":
        return "live_production_runtime_evidence"
    if level == "tested":
        return "governance_and_verification"
    return "schema_runtime_readiness"


def portfolio_readiness_report() -> dict[str, Any]:
    """Return quantified readiness for every first-party Marketplace 3.0 pack."""
    packs: list[dict[str, Any]] = []
    for asset in _outcome_assets():
        config = OutcomePackAssetConfig.model_validate(asset.config or {})
        checks = fixture_checks(config)
        failed = [check for check in checks if not check.passed]
        certification = certify_outcome_pack(config)
        required_systems = sorted({profile.provider for profile in config.runtime_profiles})
        supported_systems = sorted(
            set(required_systems)
            | {
                str(member)
                for group in config.connector_alternatives
                for member in group
                if str(member).strip()
            }
        )
        findings = [finding.as_dict() for finding in certification.findings]
        packs.append(
            {
                "slug": asset.slug,
                "title": asset.title,
                "department": asset.department,
                "status": asset.status,
                "visibility": asset.visibility,
                "playCount": len(config.plays),
                "agentCount": len(config.agents),
                "kpiCount": len(config.outcome_contract.kpis),
                "knowledgeCount": len(config.knowledge),
                "skillRequirementCount": len(config.skill_requirements),
                "runtimeProfileCount": len(config.runtime_profiles),
                "requiredSystems": required_systems,
                "supportedSystems": supported_systems,
                "packChildCount": len(asset.pack_children),
                "fixturePassed": not failed,
                "fixtureChecks": [check.as_dict() for check in checks],
                "failedFixtureChecks": [check.as_dict() for check in failed],
                "certificationLevel": certification.level,
                "publishReady": certification.publish_ready,
                "certificationFindings": findings,
                "blockingFindingCodes": [
                    finding["code"] for finding in findings if finding.get("blocking")
                ],
                "nextGate": _next_gate(
                    certification.level,
                    fixture_passed=not failed,
                    publish_ready=certification.publish_ready,
                ),
            }
        )

    packs.sort(key=lambda row: (str(row["department"] or ""), str(row["title"])))
    return {
        "packCount": len(packs),
        "fixtureReadyCount": sum(1 for row in packs if row["fixturePassed"]),
        "governedCount": sum(
            1 for row in packs if row["certificationLevel"] == "governed"
        ),
        "productionVerifiedCount": sum(
            1 for row in packs if row["certificationLevel"] == "production_verified"
        ),
        "outcomeVerifiedCount": sum(
            1 for row in packs if row["certificationLevel"] == "outcome_verified"
        ),
        "publishReadyCount": sum(1 for row in packs if row["publishReady"]),
        "draftInternalCount": sum(
            1
            for row in packs
            if row["status"] == "draft" and row["visibility"] == "internal"
        ),
        "packs": packs,
    }
