"""Audit existing Marketplace packs against the Marketplace 3.0 Outcome Pack bar.

This does not delete or hide legacy packs. It produces a migration/replacement
report so incomplete 2.x department packs are not mistaken for verified 3.0.
"""
from __future__ import annotations

from typing import Any

from app.marketplace.marketplace3.certification import certify_outcome_pack
from app.marketplace.marketplace3.certification_runner import fixture_checks
from app.marketplace.schemas import OutcomePackAssetConfig
from app.marketplace.seed_catalog import CatalogAsset, list_catalog_assets


def _gaps_for_department_pack(asset: CatalogAsset) -> list[str]:
    config = asset.config if isinstance(asset.config, dict) else {}
    gaps: list[str] = []
    if not config.get("plays") and asset.asset_type != "outcome_pack":
        gaps.append("missing Plays")
    if not config.get("agents"):
        gaps.append("missing agents")
    if not config.get("workflow_steps"):
        gaps.append("weak workflow coverage")
    if not config.get("skills") and not config.get("skill_bindings"):
        gaps.append("missing skills")
    if not config.get("rag_sources") and not config.get("knowledge"):
        gaps.append("missing knowledge")
    if not config.get("dataset"):
        gaps.append("missing dataset")
    if not config.get("dashboard"):
        gaps.append("missing dashboard")
    if not asset.required_connectors:
        gaps.append("missing connectors")
    if not config.get("outcome_contract"):
        gaps.append("missing outcome contracts")
    if not config.get("runtime_profiles"):
        gaps.append("missing verification")
    return gaps


def audit_catalog_packs() -> dict[str, Any]:
    assets = list_catalog_assets()
    rows: list[dict[str, Any]] = []
    for asset in assets:
        if asset.asset_type not in {"department_pack", "outcome_pack", "knowledge_pack", "capability_package", "intelligence_pack"}:
            continue
        if asset.asset_type == "outcome_pack":
            config = OutcomePackAssetConfig.model_validate(asset.config or {})
            checks = fixture_checks(config)
            failed_checks = [check for check in checks if not check.passed]
            certification = certify_outcome_pack(config)
            gaps = [
                f"fixture check failed: {check.key}"
                for check in failed_checks
            ]
            gaps.extend(
                finding.message
                for finding in certification.findings
                if finding.blocking
            )
            if (
                not failed_checks
                and certification.level == "governed"
                and not certification.publish_ready
            ):
                gaps.append("live production runtime evidence required")
            rows.append(
                {
                    "slug": asset.slug,
                    "title": asset.title,
                    "assetType": asset.asset_type,
                    "status": asset.status,
                    "visibility": asset.visibility,
                    "playCount": len(config.plays),
                    "agentCount": len(config.agents),
                    "kpiCount": len(config.outcome_contract.kpis),
                    "knowledgeCount": len(config.knowledge),
                    "runtimeProfileCount": len(config.runtime_profiles),
                    "fixturePassed": not failed_checks,
                    "certificationLevel": certification.level,
                    "publishReady": certification.publish_ready,
                    "marketplace3": True,
                    "gaps": gaps,
                    "replacement": None,
                }
            )
            continue
        gaps = _gaps_for_department_pack(asset)
        rows.append(
            {
                "slug": asset.slug,
                "title": asset.title,
                "assetType": asset.asset_type,
                "status": asset.status,
                "visibility": asset.visibility,
                "playCount": 0,
                "marketplace3": False,
                "gaps": gaps,
                "replacement": "Keep legacy pack installable. Rebuild as a Marketplace 3.0 Outcome Pack before verified 3.0 publication.",
            }
        )
    return {
        "packCount": len(rows),
        "marketplace3Count": sum(1 for row in rows if row["marketplace3"]),
        "legacyCount": sum(1 for row in rows if not row["marketplace3"]),
        "packs": rows,
    }
