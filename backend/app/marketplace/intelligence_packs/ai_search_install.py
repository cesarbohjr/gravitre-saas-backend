"""AI Search Intelligence Pack — demo agent + Ahrefs/Finseo/UI stubs.

Locked path C + S2 (2026-07-15): Ahrefs + Finseo dual BYO (use whichever connected);
UI scrape ai_visibility_ui v1–v3. Raw AI answer text Memory/KG blocked; no LinkedIn scrape.
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
        .limit(5)
        .execute()
    )
    for row in rows.data or []:
        if str(row.get("status") or "").lower() in {"active", "connected", "healthy"}:
            return str(row["id"])
    return None


def install_ai_search_pack_demo_bundle(
    client: Any,
    org_id: str,
    asset: dict[str, Any],
    spec: IntelligencePackSpec,
    *,
    actor_id: str,
    environment_name: str = "production",
    settings: Any | None = None,
) -> dict[str, Any]:
    """Create AI Visibility Analyst + assignments + Brand Radar workflow + stage stubs."""
    _ = settings
    asset_id = str(asset["id"])
    agent_id = _marketplace_entity_id(org_id, asset_id, "ai-visibility-analyst")
    agent_name = spec.demo_agent_name or "AI Visibility Analyst"
    demo_systems = list(spec.demo_systems) or ["ahrefs", "finseo", "ai_visibility_ui"]

    from app.operators.repository import create_operator

    create_operator(
        client,
        org_id,
        {
            "id": agent_id,
            "name": agent_name,
            "description": (
                "Tracks answer-engine visibility via Ahrefs Brand Radar and/or Finseo BYO, "
                "plus optional consumer-UI scrape (ai_visibility_ui). "
                "Raw AI answers stay Memory/KG gated; LinkedIn scrape forbidden."
            ),
            "role": "analyst",
            "capabilities": [
                "ai_visibility",
                "ahrefs_brand_radar",
                "finseo_read",
                "ui_visibility_scrape",
            ],
            "config": {
                "marketplaceAssetId": asset_id,
                "permitted_tools": demo_systems,
                "pack_id": spec.pack_id,
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
            "purpose": "AI answer-engine visibility (Ahrefs/Finseo BYO + UI scrape)",
            "role": "analyst",
            "department": "marketing",
            "model": "default",
            "capabilities": [
                "ai_visibility",
                "ahrefs_brand_radar",
                "finseo_read",
                "ui_visibility_scrape",
            ],
            "systems": demo_systems,
            "guardrails": [
                "ahrefs_finseo_byo_only",
                "raw_ai_answer_memory_kg_blocked",
                "no_linkedin_scrape",
                "ui_scrape_provenance_required",
                "reuse_existing_connectors",
            ],
            "config": {
                "marketplaceAssetId": asset_id,
                "permitted_tools": demo_systems,
                "pack_id": spec.pack_id,
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
            logger.warning("ai_search_pack_stub_stage_failed err=%s", exc)
            staged = {"error": str(exc), "created": [], "stagedCount": 0, "skipped": []}

    ahrefs_connector_id = _active_connector_id(client, org_id, "ahrefs")
    finseo_connector_id = _active_connector_id(client, org_id, "finseo")
    ui_connector_id = _active_connector_id(client, org_id, "ai_visibility_ui")

    workflow_id = None
    if spec.workflow_name and spec.workflow_steps:
        workflow_id = _marketplace_entity_id(org_id, asset_id, "ai-search-visibility-workflow")
        steps = list(spec.workflow_steps)
        definition = {"schema_version": SCHEMA_VERSION, "steps": steps}
        workflow_config = {"marketplaceAssetId": asset_id, "pack_id": spec.pack_id}
        from app.marketplace.workflow_contract import steps_to_rich_contract
        contract_nodes, contract_edges = steps_to_rich_contract(steps)
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
                "nodes": contract_nodes,
                "edges": contract_edges,
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
            logger.debug("ai_search_pack_workflow_version_skipped err=%s", exc)

    return {
        "pack_id": spec.pack_id,
        "agentId": agent_id,
        "workflowId": workflow_id,
        "assignmentCount": assignments.get("count") or 0,
        "assignmentIds": [row.get("id") for row in assignments.get("assignments") or [] if row.get("id")],
        "connectorStubs": staged,
        "ahrefsConnectorId": ahrefs_connector_id,
        "finseoConnectorId": finseo_connector_id,
        "aiVisibilityUiConnectorId": ui_connector_id,
        "stopLinesHonored": [
            "ahrefs_finseo_byo_only",
            "raw_ai_answer_memory_kg_blocked",
            "no_linkedin_scrape",
            "ui_scrape_provenance_required",
            "reuse_existing_connectors",
            "path_c_dual_byo",
            "path_s2_ui_scrape_v1_v2_v3",
        ],
    }
