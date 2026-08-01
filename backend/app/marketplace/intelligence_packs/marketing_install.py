"""Marketing Intelligence Pack — demo agent + GSC/GA4/HubSpot workflows.

Stop-lines: GSC raw query strings blocked from Memory/KG; SEMrush/Ahrefs BYO only
(not auto-staged); reuse existing connectors when active.
"""
from __future__ import annotations

from typing import Any

from app.core.logging import get_logger
from app.marketplace.connector_category_templates import install_connector_category_template
from app.marketplace.intelligence_packs.catalog import IntelligencePackSpec
from app.marketplace.intelligence_packs.pack_install_helpers import (
    upsert_preconfigured_workflow,
)
from app.marketplace.intelligence_packs.install import install_intelligence_pack
from app.services.agent_tool_permissions import default_demo_scopes_for_system, upsert_agent_tool_permission

logger = get_logger(__name__)

def _marketplace_entity_id(org_id: str, asset_id: str, seed: str) -> str:
    from app.marketplace.service import marketplace_entity_id

    return marketplace_entity_id(org_id, asset_id, seed)

def _active_connector_id(client: Any, org_id: str, connector_type: str) -> str | None:
    rows = (
        client.table("connectors")
        .select("id, type, status")
        .eq("org_id", org_id)
        .eq("type", connector_type)
        .is_("deleted_at", "null")
        .limit(5)
        .execute()
    )
    for row in rows.data or []:
        if str(row.get("status") or "").lower() in {"active", "connected", "healthy"}:
            return str(row["id"])
    return None

def install_marketing_pack_demo_bundle(
    client: Any,
    org_id: str,
    asset: dict[str, Any],
    spec: IntelligencePackSpec,
    *,
    actor_id: str,
    environment_name: str = "production",
    settings: Any | None = None,
) -> dict[str, Any]:
    """Create SEO / Marketing Analyst + assignments + GSC workflow + stage stubs."""
    _ = settings
    asset_id = str(asset["id"])
    agent_id = _marketplace_entity_id(org_id, asset_id, "seo-marketing-analyst")
    agent_name = spec.demo_agent_name or "SEO / Marketing Analyst"
    demo_systems = list(spec.demo_systems) or [
        "google_search_console",
        "google_analytics",
        "hubspot",
    ]

    from app.operators.repository import create_operator

    create_operator(
        client,
        org_id,
        {
            "id": agent_id,
            "name": agent_name,
            "description": (
                "Reads Google Search Console, GA4, and HubSpot for SEO / marketing briefings. "
                "GSC raw query strings stay Memory/KG gated; SEMrush/Ahrefs are BYO only."
            ),
            "role": "analyst",
            "capabilities": ["seo_intelligence", "gsc_read", "ga4_read", "hubspot_read"],
            "config": {
                "marketplaceAssetId": asset_id,
                "permitted_tools": demo_systems,
                "pack_id": spec.pack_id,
                "marketplaceSlug": "seo-marketing-analyst",
                "department": "marketing",
            },
            "allowed_environments": [environment_name],
            "status": "active",
        },
        created_by=actor_id,
    )
    client.table("agents").upsert(
        {
            "id": agent_id,
            "org_id": org_id,
            "name": agent_name,
            "purpose": "SEO / marketing intelligence from GSC + GA4 + HubSpot (read-only demo)",
            "role": "analyst",
            "department": "marketing",
            "model": "default",
            "capabilities": ["seo_intelligence", "gsc_read", "ga4_read", "hubspot_read"],
            "systems": demo_systems,
            "guardrails": [
                "gsc_raw_query_memory_kg_blocked",
                "semrush_ahrefs_byo_only",
                "reuse_existing_connectors",
            ],
            "config": {
                "marketplaceAssetId": asset_id,
                "permitted_tools": demo_systems,
                "pack_id": spec.pack_id,
                "marketplaceSlug": "seo-marketing-analyst",
            },
            "status": "active",
        },
        on_conflict="id",
    ).execute()

    for system in demo_systems:
        upsert_agent_tool_permission(
            client,
            org_id,
            agent_id,
            connector_id=None,
            connector_type=str(system),
            scopes=default_demo_scopes_for_system(str(system)),
            granted_by=actor_id,
        )

    assignments = install_intelligence_pack(
        client,
        org_id,
        agent_id,
        spec.pack_id,
        actor_id=actor_id,
        asset_id=asset_id,
    )

    staged: dict[str, Any] = {"created": [], "stagedCount": 0, "skipped": []}
    if spec.connector_template_id:
        try:
            staged = install_connector_category_template(
                client,
                org_id,
                spec.connector_template_id,
                created_by=actor_id,
                environment_name=environment_name,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("marketing_pack_stub_stage_failed err=%s", exc)
            staged = {"error": str(exc), "created": [], "stagedCount": 0, "skipped": []}

    gsc_connector_id = _active_connector_id(client, org_id, "google_search_console")
    ga4_connector_id = _active_connector_id(client, org_id, "google_analytics")
    hubspot_connector_id = _active_connector_id(client, org_id, "hubspot")

    workflow_id = None
    if spec.workflow_name and spec.workflow_steps:
        workflow_id = _marketplace_entity_id(org_id, asset_id, "marketing-gsc-workflow")
        upsert_preconfigured_workflow(
            client,
            org_id=org_id,
            workflow_id=workflow_id,
            workflow_name=spec.workflow_name,
            workflow_description=spec.workflow_description or "",
            steps=list(spec.workflow_steps),
            agent_id=agent_id,
            agent_slug="seo-marketing-analyst",
            asset_id=asset_id,
            pack_id=spec.pack_id,
            actor_id=actor_id,
            environment_name=environment_name,
            log_prefix="marketing",
        )

    return {
        "pack_id": spec.pack_id,
        "agentId": agent_id,
        "workflowId": workflow_id,
        "assignmentCount": assignments.get("count") or 0,
        "assignmentIds": [row.get("id") for row in assignments.get("assignments") or [] if row.get("id")],
        "connectorStubs": staged,
        "gscConnectorId": gsc_connector_id,
        "hubspotConnectorId": hubspot_connector_id,
        "ga4ConnectorId": ga4_connector_id,
        "stopLinesHonored": [
            "gsc_raw_query_memory_kg_blocked",
            "semrush_ahrefs_byo_only",
            "reuse_existing_connectors",
        ],
    }
