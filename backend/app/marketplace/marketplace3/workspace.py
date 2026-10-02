"""Tenant-scoped department surfaces built from installed version contracts."""
from typing import Any

from app.marketplace.service import MarketplaceError, fetch_marketplace_asset
from app.marketplace.schemas import OutcomePackAssetConfig
from app.marketplace.marketplace3.evidence import resolve_outcome_evidence


def contract_view(config: OutcomePackAssetConfig) -> dict[str, Any]:
    return {
        "outcome": config.outcome_contract.model_dump(mode="json"),
        "dashboard": config.dashboard.model_dump(mode="json"),
        "dataset": config.dataset.model_dump(mode="json"),
        "providers": sorted({p.provider for p in config.runtime_profiles}),
        "plays": [{"key": p.key, "name": p.name, "description": p.description,
                   "kpiKeys": p.kpi_keys, "runtimeInputs": p.runtime_inputs,
                   "trigger": p.trigger} for p in config.plays],
        "agents": [{"name": a.name, "purpose": a.purpose, "capabilities": a.capabilities} for a in config.agents],
        "knowledge": [{"title": k.title, "purpose": (k.metadata or {}).get("purpose", "")} for k in config.knowledge],
    }


def department_workspace(client: Any, org_id: str, asset_ref: str) -> dict[str, Any]:
    asset = fetch_marketplace_asset(client, asset_ref)
    installs = client.table("marketplace_installs").select("*").eq("org_id", org_id).eq(
        "asset_id", asset["id"]).eq("status", "active").limit(1).execute().data or []
    if not installs or asset.get("asset_type") != "outcome_pack":
        raise MarketplaceError("An active department pack install is required", code="NOT_FOUND")
    install = installs[0]
    versions = client.table("marketplace_asset_versions").select("config").eq(
        "asset_id", asset["id"]).eq("version_number", install["asset_version"]).limit(1).execute().data or []
    if not versions:
        raise MarketplaceError("Installed pack version is unavailable", code="WORKSPACE_VERSION_MISSING")
    config = OutcomePackAssetConfig.model_validate(versions[0]["config"])
    metadata = install.get("metadata") or {}
    workflow_ids = metadata.get("workflowIds") or []
    runs = []
    if workflow_ids:
        runs = client.table("workflow_runs").select("id,status,run_type,environment,completed_at,created_at,workflow_id").eq(
            "org_id", org_id).in_("workflow_id", workflow_ids).order("created_at", desc=True).limit(100).execute().data or []
    production_ids = [r["id"] for r in runs if r.get("environment") == "production" and r.get("run_type") == "execute"
                      and r.get("status") == "completed" and r.get("completed_at")]
    events = []
    if production_ids:
        events = client.table("intelligence_outcome_events").select("id").eq("org_id", org_id).eq(
            "outcome_event", "play_business_result").in_("workflow_run_id", production_ids).order(
            "measured_at", desc=True).limit(100).execute().data or []
    measured = resolve_outcome_evidence(client, config, {"orgId": org_id, "eventIds": [e["id"] for e in events]})
    sources = []
    if metadata.get("ragSourceIds"):
        sources = client.table("rag_sources").select("id,title,status").eq("org_id", org_id).in_(
            "id", metadata["ragSourceIds"]).execute().data or []
    return {
        "asset": {"id": asset["id"], "slug": asset["slug"], "title": asset["title"],
                  "department": asset.get("department"), "certificationLevel": asset.get("certification_level")},
        "install": {"id": install["id"], "version": install["asset_version"],
                    "pilot": metadata.get("pilot") is True, "installedAt": install.get("installed_at"),
                    "agentIds": metadata.get("agentIds") or [], "workflowIds": workflow_ids,
                    "plays": metadata.get("plays") or [], "capabilityPackageIds": metadata.get("capabilityPackageIds") or []},
        "contract": contract_view(config), "measurements": measured.get("measurements") or [],
        "sources": sources, "recentRuns": runs, "activityLimit": 100,
    }
