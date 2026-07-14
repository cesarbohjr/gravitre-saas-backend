"""Prospecting & Lead Scouting Pack — demo agent + Apollo outbound workflows.

Reuses existing Apollo/HubSpot actions and BYO stubs. Does NOT stage
Crunchbase/PDL for Memory/KG (STA-312 governance stop-line). ZoomInfo /
LinkedIn Sales Nav remain needs_connection BYO only.
"""
from __future__ import annotations

from typing import Any

from app.core.logging import get_logger
from app.marketplace.connector_category_templates import install_connector_category_template
from app.marketplace.intelligence_packs.catalog import IntelligencePackSpec
from app.marketplace.intelligence_packs.install import install_intelligence_pack
from app.services.agent_tool_permissions import default_demo_scopes_for_system, upsert_agent_tool_permission
from app.workflows.constants import SCHEMA_VERSION

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
        .limit(10)
        .execute()
    )
    preferred = {"active", "connected", "healthy", "syncing"}
    fallback: str | None = None
    for row in rows.data or []:
        cid = str(row["id"])
        status = str(row.get("status") or "").lower()
        if status in preferred:
            return cid
        # Prefer non-stub rows even if health flipped to error (credentials may still work)
        if status not in {"needs_connection", "pending_auth", "deleted"} and not fallback:
            fallback = cid
    return fallback


def install_prospecting_pack_demo_bundle(
    client: Any,
    org_id: str,
    asset: dict[str, Any],
    spec: IntelligencePackSpec,
    *,
    actor_id: str,
    environment_name: str = "production",
    settings: Any | None = None,
) -> dict[str, Any]:
    """Create Lead Scouting Analyst + Apollo outbound workflow + stubs."""
    _ = settings
    asset_id = str(asset["id"])
    agent_id = _marketplace_entity_id(org_id, asset_id, "lead-scouting-analyst")
    agent_name = spec.demo_agent_name or "Lead Scouting Analyst"

    from app.operators.repository import create_operator

    create_operator(
        client,
        org_id,
        {
            "id": agent_id,
            "name": agent_name,
            "description": (
                "Outbound lead scouting via Apollo (find companies/contacts, create lists). "
                "Optional HubSpot list sync. Crunchbase/PDL → Memory/KG gated (STA-312); "
                "BYO ZoomInfo/LI Sales Nav fail-closed without customer keys."
            ),
            "role": "analyst",
            "capabilities": ["lead_scouting", "icp", "apollo_read", "apollo_lists"],
            "config": {
                "marketplaceAssetId": asset_id,
                "permitted_tools": ["apollo", "hubspot"],
                "pack_id": spec.pack_id,
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
            "purpose": "Outbound prospecting — Apollo search + lists (not Sales CRM pipeline)",
            "role": "analyst",
            "department": "sales",
            "model": "default",
            "capabilities": ["lead_scouting", "icp", "apollo_read", "apollo_lists"],
            "systems": list(spec.demo_systems) or ["apollo", "hubspot"],
            "guardrails": [
                "no_crunchbase_pdl_memory",
                "no_byo_shared_keys",
                "no_linkedin_scrape",
            ],
            "config": {
                "marketplaceAssetId": asset_id,
                "permitted_tools": ["apollo", "hubspot"],
                "pack_id": spec.pack_id,
            },
            "status": "active",
        },
        on_conflict="id",
    ).execute()

    for system in spec.demo_systems or ["apollo", "hubspot"]:
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
    byo_staged: dict[str, Any] = {"created": [], "stagedCount": 0, "skipped": []}
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
            logger.warning("prospecting_pack_stub_stage_failed err=%s", exc)
            staged = {"error": str(exc), "created": [], "stagedCount": 0, "skipped": []}
    try:
        byo_staged = install_connector_category_template(
            client,
            org_id,
            "byo-premium-prospecting",
            created_by=actor_id,
            environment_name=environment_name,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("prospecting_byo_stub_stage_failed err=%s", exc)
        byo_staged = {"error": str(exc), "created": [], "stagedCount": 0, "skipped": []}

    apollo_connector_id = _active_connector_id(client, org_id, "apollo")
    hubspot_connector_id = _active_connector_id(client, org_id, "hubspot")

    workflow_id = None
    if spec.workflow_name and spec.workflow_steps:
        workflow_id = _marketplace_entity_id(org_id, asset_id, "prospecting-apollo-workflow")
        steps = list(spec.workflow_steps)
        definition = {"schema_version": SCHEMA_VERSION, "steps": steps}
        workflow_config = {"marketplaceAssetId": asset_id, "pack_id": spec.pack_id}
        client.table("workflow_defs").upsert(
            {
                "id": workflow_id,
                "org_id": org_id,
                "name": spec.workflow_name,
                "description": spec.workflow_description or "",
                "status": "active",
                "schema_version": SCHEMA_VERSION,
                "definition": definition,
                "config": workflow_config,
            },
            on_conflict="id",
        ).execute()
        client.table("workflows").upsert(
            {
                "id": workflow_id,
                "org_id": org_id,
                "name": spec.workflow_name,
                "description": spec.workflow_description or "",
                "status": "active",
                "environment": environment_name,
                "nodes": [
                    {"id": step.get("id"), "type": step.get("type"), "name": step.get("name")}
                    for step in steps
                ],
                "edges": [
                    {"from": steps[i].get("id"), "to": steps[i + 1].get("id")}
                    for i in range(len(steps) - 1)
                ],
                "config": workflow_config,
            },
            on_conflict="id",
        ).execute()
        try:
            from app.services.vertical_workflow_helper import ensure_active_workflow_version

            ensure_active_workflow_version(
                client,
                org_id,
                workflow_id,
                definition,
                environment_name=environment_name,
                actor_id=actor_id,
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("prospecting_pack_workflow_version_skipped err=%s", exc)

    return {
        "pack_id": spec.pack_id,
        "agentId": agent_id,
        "workflowId": workflow_id,
        "assignmentCount": assignments.get("count") or 0,
        "assignmentIds": [row.get("id") for row in assignments.get("assignments") or [] if row.get("id")],
        "connectorStubs": staged,
        "byoStubs": byo_staged,
        "apolloConnectorId": apollo_connector_id,
        "hubspotConnectorId": hubspot_connector_id,
        "stopLinesHonored": [
            "no_crunchbase_pdl_kg_memory",
            "no_opencorporates_enable",
            "no_byo_shared_keys",
            "no_linkedin_scrape",
            "reuse_existing_connectors",
            "sales_vs_prospecting_boundary",
        ],
    }
