"""Customer Success Intelligence Pack — demo agent + CRM/support read workflows.

Internal data only: HubSpot (CRM health) + Zendesk (support). No new external
governance surface; no Crunchbase/PDL/KG writes; billing/product usage as
knowledge assignments only (no new connectors).
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

def install_cs_pack_demo_bundle(
    client: Any,
    org_id: str,
    asset: dict[str, Any],
    spec: IntelligencePackSpec,
    *,
    actor_id: str,
    environment_name: str = "production",
    settings: Any | None = None,
) -> dict[str, Any]:
    """Create CS Health Analyst + assignments + HubSpot/Zendesk read workflow + stubs."""
    _ = settings
    asset_id = str(asset["id"])
    agent_id = _marketplace_entity_id(org_id, asset_id, "cs-health-analyst")
    agent_name = spec.demo_agent_name or "Customer Success Health Analyst"

    from app.operators.repository import create_operator

    create_operator(
        client,
        org_id,
        {
            "id": agent_id,
            "name": agent_name,
            "description": (
                "Reads customer CRM pipeline health (HubSpot) and support tickets (Zendesk) "
                "for retention / QBR-style briefings. Internal connectors only."
            ),
            "role": "analyst",
            "capabilities": ["health_scoring", "qbr", "hubspot_read", "zendesk_read"],
            "config": {
                "marketplaceAssetId": asset_id,
                "permitted_tools": ["hubspot", "zendesk"],
                "pack_id": spec.pack_id,
                "marketplaceSlug": "cs-health-analyst",
                "department": "customer_success",
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
            "purpose": "Customer success health from CRM + support (HubSpot/Zendesk read-only demo)",
            "role": "analyst",
            "department": "customer_success",
            "model": "default",
            "capabilities": ["health_scoring", "qbr", "hubspot_read", "zendesk_read"],
            "systems": list(spec.demo_systems) or ["hubspot", "zendesk"],
            "guardrails": ["read_only_crm_support", "no_external_enrichment"],
            "config": {
                "marketplaceAssetId": asset_id,
                "permitted_tools": ["hubspot", "zendesk"],
                "pack_id": spec.pack_id,
                "marketplaceSlug": "cs-health-analyst",
            },
            "status": "active",
        },
        on_conflict="id",
    ).execute()

    for system in spec.demo_systems or ["hubspot", "zendesk"]:
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
            logger.warning("cs_pack_stub_stage_failed err=%s", exc)
            staged = {"error": str(exc), "created": [], "stagedCount": 0, "skipped": []}

    hubspot_connector_id = _active_connector_id(client, org_id, "hubspot")
    zendesk_connector_id = _active_connector_id(client, org_id, "zendesk")

    workflow_id = None
    if spec.workflow_name and spec.workflow_steps:
        workflow_id = _marketplace_entity_id(org_id, asset_id, "cs-health-workflow")
        upsert_preconfigured_workflow(
            client,
            org_id=org_id,
            workflow_id=workflow_id,
            workflow_name=spec.workflow_name,
            workflow_description=spec.workflow_description or "",
            steps=list(spec.workflow_steps),
            agent_id=agent_id,
            agent_slug="cs-health-analyst",
            asset_id=asset_id,
            pack_id=spec.pack_id,
            actor_id=actor_id,
            environment_name=environment_name,
            log_prefix="cs",
        )

    return {
        "pack_id": spec.pack_id,
        "agentId": agent_id,
        "workflowId": workflow_id,
        "assignmentCount": assignments.get("count") or 0,
        "assignmentIds": [row.get("id") for row in assignments.get("assignments") or [] if row.get("id")],
        "connectorStubs": staged,
        "hubspotConnectorId": hubspot_connector_id,
        "zendeskConnectorId": zendesk_connector_id,
        "stopLinesHonored": [
            "internal_data_only",
            "no_new_external_governance",
            "no_crunchbase_pdl_kg_memory",
            "reuse_existing_connectors",
        ],
    }
