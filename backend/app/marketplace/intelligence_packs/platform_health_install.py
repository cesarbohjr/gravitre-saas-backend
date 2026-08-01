"""Platform Health Intelligence Pack — self-signal demo agent + snapshot workflow.

Zero new external connectors. Telemetry from audit_events + workflow runs only.
"""
from __future__ import annotations

from typing import Any

from app.core.logging import get_logger
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

def install_platform_health_pack_demo_bundle(
    client: Any,
    org_id: str,
    asset: dict[str, Any],
    spec: IntelligencePackSpec,
    *,
    actor_id: str,
    environment_name: str = "production",
    settings: Any | None = None,
) -> dict[str, Any]:
    """Create Platform Reliability Analyst + assignments + health snapshot workflow."""
    _ = settings
    asset_id = str(asset["id"])
    agent_id = _marketplace_entity_id(org_id, asset_id, "platform-reliability-analyst")
    agent_name = spec.demo_agent_name or "Platform Reliability Analyst"

    from app.operators.repository import create_operator

    create_operator(
        client,
        org_id,
        {
            "id": agent_id,
            "name": agent_name,
            "description": (
                "Reads org-local audit_events and workflow run history for approval latency, "
                "step failures, flaky connectors, and stalled workflows. No external connectors."
            ),
            "role": "analyst",
            "capabilities": [
                "approval_latency",
                "workflow_reliability",
                "connector_ops",
                "platform_health",
            ],
            "config": {
                "marketplaceAssetId": asset_id,
                "permitted_tools": ["platform"],
                "pack_id": spec.pack_id,
                "marketplaceSlug": "platform-reliability-analyst",
                "department": "platform",
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
            "purpose": "Platform health from audit_events + workflow runs (self-signal, read-only)",
            "role": "analyst",
            "department": "platform",
            "model": "default",
            "capabilities": [
                "approval_latency",
                "workflow_reliability",
                "connector_ops",
                "platform_health",
            ],
            "systems": list(spec.demo_systems) or ["platform"],
            "guardrails": ["read_only_platform_telemetry", "no_external_enrichment"],
            "config": {
                "marketplaceAssetId": asset_id,
                "permitted_tools": ["platform"],
                "pack_id": spec.pack_id,
                "marketplaceSlug": "platform-reliability-analyst",
            },
            "status": "active",
        },
        on_conflict="id",
    ).execute()

    for system in spec.demo_systems or ["platform"]:
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

    workflow_id = None
    if spec.workflow_name and spec.workflow_steps:
        workflow_id = _marketplace_entity_id(org_id, asset_id, "platform-health-workflow")
        upsert_preconfigured_workflow(
            client,
            org_id=org_id,
            workflow_id=workflow_id,
            workflow_name=spec.workflow_name,
            workflow_description=spec.workflow_description or "",
            steps=list(spec.workflow_steps),
            agent_id=agent_id,
            agent_slug="platform-reliability-analyst",
            asset_id=asset_id,
            pack_id=spec.pack_id,
            actor_id=actor_id,
            environment_name=environment_name,
            log_prefix="platform_health",
        )

    return {
        "pack_id": spec.pack_id,
        "agentId": agent_id,
        "workflowId": workflow_id,
        "assignmentCount": assignments.get("count") or 0,
        "assignmentIds": [row.get("id") for row in assignments.get("assignments") or [] if row.get("id")],
        "connectorStubs": {"created": [], "stagedCount": 0, "skipped": ["none_by_design"]},
        "stopLinesHonored": [
            "internal_data_only",
            "zero_new_external_connectors",
            "no_new_external_governance",
            "reuse_sta124_integration_health",
        ],
    }
