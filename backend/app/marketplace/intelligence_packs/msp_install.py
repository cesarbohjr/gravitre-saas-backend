"""MSP Intelligence Pack — demo agent + NVD workflow + vulnerability source stubs."""
from __future__ import annotations

from typing import Any

from app.core.logging import get_logger
from app.marketplace.connector_category_templates import install_connector_category_template
from app.marketplace.intelligence_packs.catalog import IntelligencePackSpec
from app.marketplace.intelligence_packs.install import install_intelligence_pack
from app.services.agent_tool_permissions import default_demo_scopes_for_system, upsert_agent_tool_permission
from app.services.gravitree_connector_activation import activate_gravitree_connector
from app.workflows.constants import SCHEMA_VERSION

logger = get_logger(__name__)


def _marketplace_entity_id(org_id: str, asset_id: str, seed: str) -> str:
    from app.marketplace.service import marketplace_entity_id

    return marketplace_entity_id(org_id, asset_id, seed)


def _activate_connector_type(
    client: Any,
    org_id: str,
    connector_type: str,
    *,
    staged: dict[str, Any],
    settings: Any,
) -> dict[str, Any] | None:
    connector_id: str | None = None
    for row in staged.get("created") or []:
        if str(row.get("connectorType") or row.get("type") or "").lower() == connector_type:
            connector_id = str(row.get("id"))
            break
    if not connector_id:
        for row in staged.get("skipped") or []:
            if str(row.get("connectorType") or row.get("type") or "").lower() == connector_type:
                connector_id = str(row.get("id") or "") or None
                break
    if not connector_id:
        existing = (
            client.table("connectors")
            .select("id, type, status")
            .eq("org_id", org_id)
            .eq("type", connector_type)
            .is_("deleted_at", "null")
            .limit(1)
            .execute()
        )
        if existing.data:
            connector_id = str(existing.data[0]["id"])
    if not connector_id:
        return None
    try:
        return activate_gravitree_connector(
            client,
            org_id=org_id,
            connector_id=connector_id,
            settings=settings,
        )
    except Exception as exc:  # noqa: BLE001
        logger.info("msp_pack_%s_activate_skipped err=%s", connector_type, exc)
        return None


def install_msp_pack_demo_bundle(
    client: Any,
    org_id: str,
    asset: dict[str, Any],
    spec: IntelligencePackSpec,
    *,
    actor_id: str,
    environment_name: str = "production",
    settings: Any | None = None,
    activate_nvd: bool = True,
) -> dict[str, Any]:
    """Create MSP analyst + assignments + NVD workflow + stage NVD/CISA stubs."""
    from app.operators.repository import create_operator

    asset_id = str(asset["id"])
    agent_id = _marketplace_entity_id(org_id, asset_id, "msp-vuln-analyst")
    agent_name = spec.demo_agent_name or "MSP Vulnerability Analyst"

    create_operator(
        client,
        org_id,
        {
            "id": agent_id,
            "name": agent_name,
            "description": "Reads Gravitree-managed vulnerability feeds (NVD first; CISA KEV staged) for MSP ops.",
            "role": "analyst",
            "capabilities": ["vulnerability_intelligence", "nvd_lookup"],
            "config": {
                "marketplaceAssetId": asset_id,
                "permitted_tools": ["nvd_get_cve", "cisa_kev_get_feed", "nvd", "cisa_kev"],
                "pack_id": spec.pack_id,
                "department": "msp",
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
            "purpose": "MSP vulnerability intelligence from Gravitree-managed sources",
            "role": "analyst",
            "department": "msp",
            "model": "default",
            "capabilities": ["vulnerability_intelligence", "nvd_lookup"],
            "systems": list(spec.demo_systems) or ["nvd", "cisa_kev"],
            "guardrails": ["read_only_external_sources"],
            "config": {
                "marketplaceAssetId": asset_id,
                "permitted_tools": ["nvd_get_cve", "cisa_kev_get_feed", "nvd", "cisa_kev"],
                "pack_id": spec.pack_id,
            },
            "status": "active",
        },
        on_conflict="id",
    ).execute()

    for system in spec.demo_systems or ["nvd", "cisa_kev"]:
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
            logger.warning("msp_pack_stub_stage_failed err=%s", exc)
            staged = {"error": str(exc), "created": [], "stagedCount": 0, "skipped": []}

    activated_nvd: dict[str, Any] | None = None
    activated_cisa: dict[str, Any] | None = None
    if activate_nvd and settings is not None:
        activated_nvd = _activate_connector_type(
            client, org_id, "nvd", staged=staged, settings=settings
        )
        activated_cisa = _activate_connector_type(
            client, org_id, "cisa_kev", staged=staged, settings=settings
        )

    workflow_id = None
    if spec.workflow_name and spec.workflow_steps:
        workflow_id = _marketplace_entity_id(org_id, asset_id, "msp-nvd-workflow")
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
            logger.debug("msp_pack_workflow_version_skipped err=%s", exc)

    return {
        "pack_id": spec.pack_id,
        "agentId": agent_id,
        "workflowId": workflow_id,
        "assignmentCount": assignments.get("count") or 0,
        "assignmentIds": [row.get("id") for row in assignments.get("assignments") or [] if row.get("id")],
        "connectorStubs": staged,
        "nvdActivated": activated_nvd,
        "cisaKevActivated": activated_cisa,
    }
