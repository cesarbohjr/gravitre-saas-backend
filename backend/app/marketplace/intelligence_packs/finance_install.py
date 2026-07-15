"""Finance Intelligence Pack — Cash Flow Analyst + QB/Xero/NetSuite/Plaid stubs (F3).

Stop-lines: reuse existing connectors; finance read-only tip; raw payroll/banking
Memory/KG blocked; path F3 all finance live (Plaid if entitled).
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


def install_finance_pack_demo_bundle(
    client: Any,
    org_id: str,
    asset: dict[str, Any],
    spec: IntelligencePackSpec,
    *,
    actor_id: str,
    environment_name: str = "production",
    settings: Any | None = None,
) -> dict[str, Any]:
    """Create Cash Flow Analyst + assignments + QB workflow + stage stubs."""
    _ = settings
    asset_id = str(asset["id"])
    agent_id = _marketplace_entity_id(org_id, asset_id, "cash-flow-analyst")
    agent_name = spec.demo_agent_name or "Cash Flow Analyst"
    demo_systems = list(spec.demo_systems) or ["quickbooks", "xero", "netsuite", "plaid"]

    from app.operators.repository import create_operator

    create_operator(
        client,
        org_id,
        {
            "id": agent_id,
            "name": agent_name,
            "description": (
                "Reads QuickBooks, Xero, NetSuite, and Plaid (if entitled) for cash-flow briefings. "
                "Read-only tip; raw payroll/banking stay Memory/KG gated."
            ),
            "role": "analyst",
            "capabilities": [
                "cash_flow",
                "quickbooks_read",
                "xero_read",
                "netsuite_read",
                "plaid_read",
            ],
            "config": {
                "marketplaceAssetId": asset_id,
                "permitted_tools": demo_systems,
                "pack_id": spec.pack_id,
                "department": "finance",
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
            "purpose": "Finance cash-flow intelligence (QB/Xero/NetSuite/Plaid read-only)",
            "role": "analyst",
            "department": "finance",
            "model": "default",
            "capabilities": [
                "cash_flow",
                "quickbooks_read",
                "xero_read",
                "netsuite_read",
                "plaid_read",
            ],
            "systems": demo_systems,
            "guardrails": [
                "reuse_existing_connectors",
                "finance_read_only_tip",
                "raw_payroll_banking_memory_kg_blocked",
                "path_f3_all_finance_live",
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
            logger.warning("finance_pack_stub_stage_failed err=%s", exc)
            staged = {"error": str(exc), "created": [], "stagedCount": 0, "skipped": []}

    qb_id = _active_connector_id(client, org_id, "quickbooks")
    xero_id = _active_connector_id(client, org_id, "xero")
    netsuite_id = _active_connector_id(client, org_id, "netsuite")
    plaid_id = _active_connector_id(client, org_id, "plaid")

    workflow_id = None
    if spec.workflow_name and spec.workflow_steps:
        workflow_id = _marketplace_entity_id(org_id, asset_id, "finance-cash-flow-workflow")
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
            logger.debug("finance_pack_workflow_version_skipped err=%s", exc)

    return {
        "pack_id": spec.pack_id,
        "agentId": agent_id,
        "workflowId": workflow_id,
        "assignmentCount": assignments.get("count") or 0,
        "assignmentIds": [row.get("id") for row in assignments.get("assignments") or [] if row.get("id")],
        "connectorStubs": staged,
        "quickbooksConnectorId": qb_id,
        "xeroConnectorId": xero_id,
        "netsuiteConnectorId": netsuite_id,
        "plaidConnectorId": plaid_id,
        "stopLinesHonored": [
            "reuse_existing_connectors",
            "finance_read_only_tip",
            "raw_payroll_banking_memory_kg_blocked",
            "path_f3_all_finance_live",
        ],
    }
