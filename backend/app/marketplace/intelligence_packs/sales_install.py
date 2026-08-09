"""Sales Intelligence Pack — demo agent + HubSpot read workflow + CRM stubs.

Stop-lines (not wired): Crunchbase/PDL → KG/Memory, OpenCorporates enable,
ZoomInfo/LinkedIn Sales Nav shared keys, LinkedIn scrape, Phase 5 ML.
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

def install_sales_pack_demo_bundle(
    client: Any,
    org_id: str,
    asset: dict[str, Any],
    spec: IntelligencePackSpec,
    *,
    actor_id: str,
    environment_name: str = "production",
    settings: Any | None = None,
) -> dict[str, Any]:
    """Create Sales analyst + assignments + HubSpot read workflow + stage CRM stubs.

    HubSpot/Apollo are customer_owned — stubs only; no gravitre activation.
    Crunchbase/PDL/BYO premium not staged here.
    """
    from app.operators.repository import create_operator

    _ = settings  # reserved for future gravitre Sales sources (e.g. SEC) after invoke wiring
    asset_id = str(asset["id"])
    agent_id = _marketplace_entity_id(org_id, asset_id, "sales-pipeline-analyst")
    agent_name = spec.demo_agent_name or "Sales Pipeline Analyst"

    create_operator(
        client,
        org_id,
        {
            "id": agent_id,
            "name": agent_name,
            "description": (
                "Reads customer CRM pipeline (HubSpot) for sales briefings. "
                "No Crunchbase/PDL/KG writes; BYO prospecting connectors stay fail-closed."
            ),
            "role": "analyst",
            "capabilities": ["pipeline_intelligence", "hubspot_read"],
            "config": {
                "marketplaceAssetId": asset_id,
                "permitted_tools": ["hubspot"],
                "pack_id": spec.pack_id,
                "marketplaceSlug": "sales-pipeline-analyst",
                "department": "sales",
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
            "purpose": "Sales pipeline intelligence from customer CRM (HubSpot read-only demo)",
            "role": "analyst",
            "department": "sales",
            "model": "default",
            "capabilities": ["pipeline_intelligence", "hubspot_read"],
            "systems": list(spec.demo_systems) or ["hubspot"],
            "guardrails": ["read_only_crm", "no_crunchbase_pdl_memory"],
            "config": {
                "marketplaceAssetId": asset_id,
                "permitted_tools": ["hubspot"],
                "pack_id": spec.pack_id,
                "marketplaceSlug": "sales-pipeline-analyst",
            },
            "status": "active",
        },
        on_conflict="id",
    ).execute()

    for system in spec.demo_systems or ["hubspot"]:
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
            logger.warning("sales_pack_stub_stage_failed err=%s", exc)
            staged = {"error": str(exc), "created": [], "stagedCount": 0, "skipped": []}

    hubspot_connector_id = _active_connector_id(client, org_id, "hubspot")

    workflow_id = None
    if spec.workflow_name and spec.workflow_steps:
        workflow_id = _marketplace_entity_id(org_id, asset_id, "sales-hubspot-workflow")
        upsert_preconfigured_workflow(
            client,
            org_id=org_id,
            workflow_id=workflow_id,
            workflow_name=spec.workflow_name,
            workflow_description=spec.workflow_description or "",
            steps=list(spec.workflow_steps),
            agent_id=agent_id,
            agent_slug="sales-pipeline-analyst",
            asset_id=asset_id,
            pack_id=spec.pack_id,
            actor_id=actor_id,
            environment_name=environment_name,
            log_prefix="sales",
        )

    return {
        "pack_id": spec.pack_id,
        "agentId": agent_id,
        "workflowId": workflow_id,
        "assignmentCount": assignments.get("count") or 0,
        "assignmentIds": [row.get("id") for row in assignments.get("assignments") or [] if row.get("id")],
        "connectorStubs": staged,
        "hubspotConnectorId": hubspot_connector_id,
        "stopLinesHonored": [
            "no_crunchbase_pdl_kg_memory",
            "no_opencorporates_enable",
            "no_byo_shared_keys",
            "no_linkedin_scrape",
            "phase5_ml_held",
        ],
    }
