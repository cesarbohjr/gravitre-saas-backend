"""Marketplace 3.0 portfolio readiness.

This module answers a narrow operational question: what is already built, what
passes Gravitre's static/fixture certification bar, and what evidence is still
required before a pack can be promoted. It never upgrades certification based
on fixture success alone.
"""
from __future__ import annotations

from typing import Any
from types import SimpleNamespace
from pydantic import ValidationError

from app.marketplace.marketplace3.certification import certify_outcome_pack
from app.marketplace.marketplace3.certification_runner import fixture_checks
from app.marketplace.marketplace3.department_portfolio import (
    department_portfolio_marketplace3_assets,
)
from app.marketplace.marketplace3.msp_service_desk import (
    msp_service_desk_marketplace3_assets,
)
from app.marketplace.schemas import OutcomePackAssetConfig
from app.marketplace.marketplace3.evidence import resolve_runtime_evidence, resolve_outcome_evidence


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


def portfolio_readiness_report(client: Any = None) -> dict[str, Any]:
    """Report source readiness offline or fresh database-resolved readiness live.

    Stored certification labels are historical claims. Live reports recheck
    their referenced executions and measurements without mutating the catalog.
    Missing deployments are explicit; source fixtures cannot hide them.
    """
    source_assets = _outcome_assets()
    deployed = {}
    child_counts: dict[str, int] = {}
    if client is not None:
        rows = client.table("marketplace_assets").select("*").in_(
            "slug", [asset.slug for asset in source_assets]
        ).execute().data or []
        deployed = {row["slug"]: row for row in rows
                    if row.get("asset_type") == "outcome_pack" and row.get("org_id") is None}
        if deployed:
            links = client.table("marketplace_pack_items").select("pack_asset_id").in_(
                "pack_asset_id", [row["id"] for row in deployed.values()]
            ).execute().data or []
            for link in links:
                key = link["pack_asset_id"]
                child_counts[key] = child_counts.get(key, 0) + 1
    packs: list[dict[str, Any]] = []
    for source_asset in source_assets:
        stored = deployed.get(source_asset.slug)
        asset = source_asset
        if stored:
            asset = SimpleNamespace(**{
                **vars(source_asset), **stored,
            })
        try:
            config = OutcomePackAssetConfig.model_validate(asset.config or {})
        except ValidationError:
            packs.append({
                "slug": asset.slug, "assetId": (stored or {}).get("id"),
                "title": asset.title, "department": asset.department,
                "deployed": stored is not None, "status": asset.status,
                "visibility": asset.visibility, "fixturePassed": False,
                "certificationLevel": None, "publishReady": False,
                "storedCertificationLevel": (stored or {}).get("certification_level"),
                "blockingFindingCodes": ["INVALID_CONFIG"],
                "nextGate": "fix_fixture_or_contract_failures",
            })
            continue
        checks = fixture_checks(config)
        failed = [check for check in checks if not check.passed]
        evidence = (stored or {}).get("certification_evidence")
        evidence = evidence if isinstance(evidence, dict) else {}
        runtime_claim = evidence.get("runtime")
        outcome_claim = evidence.get("outcome")
        runtime = resolve_runtime_evidence(client, config, runtime_claim if isinstance(runtime_claim, dict) else {}) if stored else {}
        outcome = resolve_outcome_evidence(client, config, outcome_claim if isinstance(outcome_claim, dict) else {}) if stored else {}
        certification = certify_outcome_pack(config, runtime_evidence=runtime, outcome_evidence=outcome)
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
                "assetId": (stored or {}).get("id"),
                "deployed": stored is not None if client is not None else None,
                "storedCertificationLevel": (stored or {}).get("certification_level"),
                "certificationUpdatedAt": (stored or {}).get("certification_updated_at"),
                "title": asset.title,
                "department": asset.department,
                "status": "missing" if client is not None and not stored else asset.status,
                "visibility": None if client is not None and not stored else asset.visibility,
                "playCount": len(config.plays),
                "agentCount": len(config.agents),
                "kpiCount": len(config.outcome_contract.kpis),
                "knowledgeCount": len(config.knowledge),
                "skillRequirementCount": len(config.skill_requirements),
                "runtimeProfileCount": len(config.runtime_profiles),
                "requiredSystems": required_systems,
                "supportedSystems": supported_systems,
                "packChildCount": child_counts.get(stored["id"], 0) if stored else len(asset.pack_children) if client is None else 0,
                "fixturePassed": not failed,
                "fixtureChecks": [check.as_dict() for check in checks],
                "failedFixtureChecks": [check.as_dict() for check in failed],
                "certificationLevel": None if client is not None and not stored else certification.level,
                "publishReady": certification.publish_ready and not failed and (client is None or stored is not None),
                "runtimeEvidenceProviders": sorted(key for key in runtime if key != "runner"),
                "measuredOutcomeCount": len(outcome.get("measurements") or []),
                "certificationFindings": findings,
                "blockingFindingCodes": [
                    finding["code"] for finding in findings if finding.get("blocking")
                ],
                "nextGate": "seed_catalog" if client is not None and not stored else
                "promote_certified_pack" if stored and certification.publish_ready and not failed
                and asset.status != "published" else _next_gate(
                    certification.level,
                    fixture_passed=not failed,
                    publish_ready=certification.publish_ready,
                ),
            }
        )

    packs.sort(key=lambda row: (str(row["department"] or ""), str(row["title"])))
    return {
        "source": "deployed_catalog" if client is not None else "source_catalog",
        "deployedPackCount": len(deployed) if client is not None else None,
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
