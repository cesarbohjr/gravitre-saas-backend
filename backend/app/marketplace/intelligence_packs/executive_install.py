"""Executive Intelligence Pack — demo agent + workflow + connector stubs."""
from __future__ import annotations

from typing import Any

from app.core.logging import get_logger
from app.marketplace.intelligence_packs.catalog import IntelligencePackSpec, get_intelligence_pack_spec
from app.marketplace.intelligence_packs.install import install_intelligence_pack
from app.marketplace.connector_category_templates import install_connector_category_template
from app.services.agent_tool_permissions import default_demo_scopes_for_system, upsert_agent_tool_permission
from app.services.gravitree_connector_activation import activate_gravitree_connector
from app.workflows.constants import SCHEMA_VERSION

logger = get_logger(__name__)


def _marketplace_entity_id(org_id: str, asset_id: str, seed: str) -> str:
    from app.marketplace.service import marketplace_entity_id

    return marketplace_entity_id(org_id, asset_id, seed)


def install_executive_pack_demo_bundle(
    client: Any,
    org_id: str,
    asset: dict[str, Any],
    spec: IntelligencePackSpec,
    *,
    actor_id: str,
    environment_name: str = "production",
    settings: Any | None = None,
    activate_fred: bool = True,
) -> dict[str, Any]:
    """Create agent + assignments + FRED workflow + stage executive source stubs."""
    from app.operators.repository import create_operator

    asset_id = str(asset["id"])
    agent_id = _marketplace_entity_id(org_id, asset_id, "executive-analyst")
    agent_name = spec.demo_agent_name or "Executive Macro Analyst"

    create_operator(
        client,
        org_id,
        {
            "id": agent_id,
            "name": agent_name,
            "description": "Reads Gravitree-managed macro sources (FRED first) for executive briefings.",
            "role": "analyst",
            "capabilities": ["macro_intelligence", "fred_lookup"],
            "config": {
                "marketplaceAssetId": asset_id,
                "permitted_tools": ["fred_get_series", "fred"],
                "pack_id": spec.pack_id,
                "department": "executive",
            },
            "allowed_environments": [environment_name],
            "status": "active",
        },
        created_by=actor_id,
    )
    # Mirror already runs inside create_operator; keep agents row enriched for pack UI.
    client.table("agents").upsert(
        {
            "id": agent_id,
            "org_id": org_id,
            "name": agent_name,
            "purpose": "Executive macro intelligence from Gravitree-managed sources",
            "role": "analyst",
            "department": "executive",
            "model": "default",
            "capabilities": ["macro_intelligence", "fred_lookup"],
            "systems": list(spec.demo_systems) or ["fred"],
            "guardrails": ["read_only_external_sources"],
            "config": {
                "marketplaceAssetId": asset_id,
                "permitted_tools": ["fred_get_series", "fred"],
                "pack_id": spec.pack_id,
            },
            "status": "active",
        },
        on_conflict="id",
    ).execute()

    for system in spec.demo_systems or ["fred"]:
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

    staged: dict[str, Any] = {"created": [], "stagedCount": 0}
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
            logger.warning("executive_pack_stub_stage_failed err=%s", exc)
            staged = {"error": str(exc), "created": [], "stagedCount": 0}

    activated_fred: dict[str, Any] | None = None
    if activate_fred and settings is not None:
        fred_connector_id: str | None = None
        for row in staged.get("created") or []:
            if str(row.get("connectorType") or row.get("type") or "").lower() == "fred":
                fred_connector_id = str(row.get("id"))
                break
        if not fred_connector_id:
            existing_fred = (
                client.table("connectors")
                .select("id, type, status")
                .eq("org_id", org_id)
                .eq("type", "fred")
                .is_("deleted_at", "null")
                .limit(1)
                .execute()
            )
            if existing_fred.data:
                fred_connector_id = str(existing_fred.data[0]["id"])
        if fred_connector_id:
            try:
                activated_fred = activate_gravitree_connector(
                    client,
                    org_id=org_id,
                    connector_id=fred_connector_id,
                    settings=settings,
                )
            except Exception as exc:  # noqa: BLE001
                logger.info("executive_pack_fred_activate_skipped err=%s", exc)

    workflow_id = None
    if spec.workflow_name and spec.workflow_steps:
        workflow_id = _marketplace_entity_id(org_id, asset_id, "executive-fred-workflow")
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
            logger.debug("executive_pack_workflow_version_skipped err=%s", exc)

    return {
        "pack_id": spec.pack_id,
        "agentId": agent_id,
        "workflowId": workflow_id,
        "assignmentCount": assignments.get("count") or 0,
        "assignmentIds": [row.get("id") for row in assignments.get("assignments") or [] if row.get("id")],
        "connectorStubs": staged,
        "fredActivated": activated_fred,
    }
