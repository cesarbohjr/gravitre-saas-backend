"""HR & Talent Intelligence Pack — Recruiting Talent Analyst + HRIS/ATS stubs (H3).

Stop-lines: no LinkedIn scrape; employee/compensation PII Memory/KG blocked;
HR read-only tip; path H3 all HR live (Gusto partner OAuth when approved).
"""
from __future__ import annotations

from typing import Any

from app.core.logging import get_logger
from app.marketplace.connector_category_templates import (
    connector_stub_coverage,
    install_connector_category_template,
)
from app.marketplace.intelligence_packs.catalog import IntelligencePackSpec
from app.marketplace.intelligence_packs.install import install_intelligence_pack
from app.services.agent_tool_permissions import default_demo_scopes_for_system, upsert_agent_tool_permission
from app.workflows.constants import SCHEMA_VERSION

logger = get_logger(__name__)

_HR_STUB_TYPES = ("workday", "bamboohr", "greenhouse", "gusto")


def _marketplace_entity_id(org_id: str, asset_id: str, seed: str) -> str:
    from app.marketplace.service import marketplace_entity_id

    return marketplace_entity_id(org_id, asset_id, seed)


def _active_id_from_coverage(coverage: dict[str, Any], connector_type: str) -> str | None:
    info = (coverage.get("byType") or {}).get(connector_type) or {}
    if info.get("active") and info.get("id"):
        return str(info["id"])
    return None


def _stub_id_from_coverage(coverage: dict[str, Any], connector_type: str) -> str | None:
    info = (coverage.get("byType") or {}).get(connector_type) or {}
    if info.get("stagedOk") and info.get("id"):
        return str(info["id"])
    return None


def install_hr_talent_pack_demo_bundle(
    client: Any,
    org_id: str,
    asset: dict[str, Any],
    spec: IntelligencePackSpec,
    *,
    actor_id: str,
    environment_name: str = "production",
    settings: Any | None = None,
) -> dict[str, Any]:
    """Create Recruiting Talent Analyst + assignments + Greenhouse workflow + stage stubs."""
    _ = settings
    asset_id = str(asset["id"])
    agent_id = _marketplace_entity_id(org_id, asset_id, "recruiting-talent-analyst")
    agent_name = spec.demo_agent_name or "Recruiting Talent Analyst"
    demo_systems = list(spec.demo_systems) or ["workday", "bamboohr", "greenhouse", "gusto"]

    from app.operators.repository import create_operator

    create_operator(
        client,
        org_id,
        {
            "id": agent_id,
            "name": agent_name,
            "description": (
                "Reads Workday, BambooHR, Greenhouse, and Gusto (when partner OAuth connected) "
                "for recruiting / talent briefings. Employee and compensation PII stay Memory/KG gated; "
                "LinkedIn scrape forbidden."
            ),
            "role": "analyst",
            "capabilities": [
                "recruiting",
                "greenhouse_read",
                "workday_read",
                "bamboohr_read",
                "gusto_read",
            ],
            "config": {
                "marketplaceAssetId": asset_id,
                "permitted_tools": demo_systems,
                "pack_id": spec.pack_id,
                "department": "hr",
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
            "purpose": "HR & talent intelligence (Workday/BambooHR/Greenhouse/Gusto read-only)",
            "role": "analyst",
            "department": "hr",
            "model": "default",
            "capabilities": [
                "recruiting",
                "greenhouse_read",
                "workday_read",
                "bamboohr_read",
                "gusto_read",
            ],
            "systems": demo_systems,
            "guardrails": [
                "no_linkedin_scrape",
                "employee_pii_memory_kg_blocked",
                "compensation_memory_kg_blocked",
                "hr_read_only_tip",
                "path_h3_all_hr_live",
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

    staging_error: str | None = None
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
            staging_error = str(exc)
            logger.warning("hr_talent_pack_stub_stage_failed err=%s", exc)
            staged = {"error": staging_error, "created": [], "stagedCount": 0, "skipped": []}

    coverage = connector_stub_coverage(
        client,
        org_id,
        list(_HR_STUB_TYPES),
        environment_name=environment_name,
    )
    workday_id = _active_id_from_coverage(coverage, "workday")
    bamboo_id = _active_id_from_coverage(coverage, "bamboohr")
    greenhouse_id = _active_id_from_coverage(coverage, "greenhouse")
    gusto_id = _active_id_from_coverage(coverage, "gusto")

    workflow_id = None
    if spec.workflow_name and spec.workflow_steps:
        workflow_id = _marketplace_entity_id(org_id, asset_id, "hr-talent-recruiting-workflow")
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
            logger.debug("hr_talent_pack_workflow_version_skipped err=%s", exc)

    return {
        "pack_id": spec.pack_id,
        "agentId": agent_id,
        "workflowId": workflow_id,
        "assignmentCount": assignments.get("count") or 0,
        "assignmentIds": [row.get("id") for row in assignments.get("assignments") or [] if row.get("id")],
        "connectorStubs": staged,
        "stagingError": staging_error,
        "stubCoverage": coverage,
        "workdayConnectorId": workday_id,
        "bamboohrConnectorId": bamboo_id,
        "greenhouseConnectorId": greenhouse_id,
        "gustoConnectorId": gusto_id,
        "workdayStubConnectorId": _stub_id_from_coverage(coverage, "workday"),
        "bamboohrStubConnectorId": _stub_id_from_coverage(coverage, "bamboohr"),
        "greenhouseStubConnectorId": _stub_id_from_coverage(coverage, "greenhouse"),
        "gustoStubConnectorId": _stub_id_from_coverage(coverage, "gusto"),
        "stopLinesHonored": [
            "no_linkedin_scrape",
            "employee_pii_memory_kg_blocked",
            "compensation_memory_kg_blocked",
            "hr_read_only_tip",
            "path_h3_all_hr_live",
        ],
    }
