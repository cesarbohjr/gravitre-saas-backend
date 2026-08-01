"""Support Intelligence Pack — demo agent + Zendesk queue snapshot workflow."""
from __future__ import annotations

from typing import Any

from app.core.logging import get_logger
from app.marketplace.intelligence_packs.catalog import IntelligencePackSpec
from app.marketplace.intelligence_packs.install import install_intelligence_pack
from app.marketplace.intelligence_packs.pack_install_helpers import (
    upsert_preconfigured_workflow,
)
from app.services.agent_tool_permissions import default_demo_scopes_for_system, upsert_agent_tool_permission

logger = get_logger(__name__)

AGENT_SLUG = "support-queue-analyst"


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


def install_support_pack_demo_bundle(
    client: Any,
    org_id: str,
    asset: dict[str, Any],
    spec: IntelligencePackSpec,
    *,
    actor_id: str,
    environment_name: str = "production",
    settings: Any | None = None,
) -> dict[str, Any]:
    """Create Support Queue Analyst + assignments + Zendesk queue workflow."""
    _ = settings
    asset_id = str(asset["id"])
    agent_id = _marketplace_entity_id(org_id, asset_id, AGENT_SLUG)
    agent_name = spec.demo_agent_name or "Support Queue Analyst"

    from app.operators.repository import create_operator

    create_operator(
        client,
        org_id,
        {
            "id": agent_id,
            "name": agent_name,
            "description": (
                "Reads Zendesk open/recent tickets for queue triage and escalation briefings. "
                "Uses assigned KB / playbook knowledge. Read-oriented demo."
            ),
            "role": "analyst",
            "capabilities": ["ticket_triage", "zendesk_read", "escalation"],
            "config": {
                "marketplaceAssetId": asset_id,
                "permitted_tools": ["zendesk"],
                "pack_id": spec.pack_id,
                "marketplaceSlug": AGENT_SLUG,
                "department": "support",
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
            "purpose": "Support queue health from Zendesk tickets (read-only demo)",
            "role": "analyst",
            "department": "support",
            "model": "default",
            "capabilities": ["ticket_triage", "zendesk_read", "escalation"],
            "systems": list(spec.demo_systems) or ["zendesk"],
            "guardrails": ["read_only_support", "no_external_enrichment"],
            "config": {
                "marketplaceAssetId": asset_id,
                "permitted_tools": ["zendesk"],
                "pack_id": spec.pack_id,
                "marketplaceSlug": AGENT_SLUG,
            },
            "status": "active",
        },
        on_conflict="id",
    ).execute()

    for system in spec.demo_systems or ["zendesk"]:
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

    zendesk_connector_id = _active_connector_id(client, org_id, "zendesk")

    workflow_id = None
    if spec.workflow_name and spec.workflow_steps:
        workflow_id = _marketplace_entity_id(org_id, asset_id, "support-zendesk-workflow")
        upsert_preconfigured_workflow(
            client,
            org_id=org_id,
            workflow_id=workflow_id,
            workflow_name=spec.workflow_name,
            workflow_description=spec.workflow_description or "",
            steps=list(spec.workflow_steps),
            agent_id=agent_id,
            agent_slug=AGENT_SLUG,
            asset_id=asset_id,
            pack_id=spec.pack_id,
            actor_id=actor_id,
            environment_name=environment_name,
            log_prefix="support",
        )

    return {
        "pack_id": spec.pack_id,
        "agentId": agent_id,
        "workflowId": workflow_id,
        "assignmentCount": assignments.get("count") or 0,
        "assignmentIds": [row.get("id") for row in assignments.get("assignments") or [] if row.get("id")],
        "connectorStubs": {"created": [], "stagedCount": 0, "skipped": ["reuse_existing_zendesk"]},
        "zendeskConnectorId": zendesk_connector_id,
        "stopLinesHonored": [
            "reuse_existing_zendesk",
            "no_new_external_governance",
            "no_external_enrichment",
        ],
    }
