"""MSP Intelligence Pack — prospecting coordinator + vuln analyst + list-builder workflow."""
from __future__ import annotations

from typing import Any

from app.core.logging import get_logger
from app.marketplace.connector_category_templates import install_connector_category_template
from app.marketplace.intelligence_packs.catalog import IntelligencePackSpec
from app.marketplace.intelligence_packs.install import install_intelligence_pack
from app.marketplace.workflows.msp_prospecting_list_workflow import (
    SCOUT_AGENT_CAPABILITIES,
    SCOUT_AGENT_DEPARTMENT,
    SCOUT_AGENT_NAME,
    SCOUT_AGENT_PURPOSE,
    SCOUT_AGENT_ROLE,
    SCOUT_AGENT_SLUG,
    SCOUT_AGENT_SYSTEMS,
    WORKFLOW_SLUG,
)
from app.services.agent_tool_permissions import default_demo_scopes_for_system, upsert_agent_tool_permission
from app.services.gravitree_connector_activation import activate_gravitree_connector
from app.workflows.constants import SCHEMA_VERSION

logger = get_logger(__name__)

LEGACY_WORKFLOW_NAMES = frozenset({"MSP NVD CVE Lookup", "MSP NVD CVE lookup"})


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


def _upsert_agent(
    client: Any,
    *,
    org_id: str,
    agent_id: str,
    name: str,
    purpose: str,
    role: str,
    department: str,
    capabilities: list[str],
    systems: list[str],
    asset_id: str,
    pack_id: str,
    actor_id: str,
    environment_name: str,
    guardrails: list[str] | None = None,
) -> None:
    from app.operators.repository import create_operator

    create_operator(
        client,
        org_id,
        {
            "id": agent_id,
            "name": name,
            "description": purpose,
            "role": role,
            "capabilities": capabilities,
            "config": {
                "marketplaceAssetId": asset_id,
                "marketplaceSlug": (
                    SCOUT_AGENT_SLUG if "prospecting" in capabilities else "msp-vuln-analyst"
                ),
                "slug": SCOUT_AGENT_SLUG if "prospecting" in capabilities else "msp-vuln-analyst",
                "permitted_tools": list(systems),
                "pack_id": pack_id,
                "department": department,
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
            "name": name,
            "purpose": purpose,
            "role": role,
            "department": department,
            "model": "default",
            "capabilities": capabilities,
            "systems": list(systems),
            "guardrails": guardrails or [],
            "config": {
                "marketplaceAssetId": asset_id,
                "marketplaceSlug": (
                    SCOUT_AGENT_SLUG if "prospecting" in capabilities else "msp-vuln-analyst"
                ),
                "slug": SCOUT_AGENT_SLUG if "prospecting" in capabilities else "msp-vuln-analyst",
                "permitted_tools": list(systems),
                "pack_id": pack_id,
                "agent_slug": SCOUT_AGENT_SLUG if "prospecting" in capabilities else "msp-vuln-analyst",
            },
            "status": "active",
        },
        on_conflict="id",
    ).execute()
    for system in systems:
        upsert_agent_tool_permission(
            client,
            org_id,
            agent_id,
            connector_id=None,
            connector_type=str(system),
            scopes=default_demo_scopes_for_system(str(system)),
            granted_by=actor_id,
        )


def _resolve_agent_seeds(
    steps: list[dict[str, Any]],
    *,
    agent_ids_by_seed: dict[str, str],
) -> list[dict[str, Any]]:
    from app.marketplace.workflow_contract import resolve_step_agent_seeds

    return resolve_step_agent_seeds(steps, agent_ids_by_seed=agent_ids_by_seed)


def _upsert_workflow(
    client: Any,
    *,
    org_id: str,
    workflow_id: str,
    asset_id: str,
    pack_id: str,
    name: str,
    description: str,
    steps: list[dict[str, Any]],
    environment_name: str,
    actor_id: str,
    agent_ids_by_seed: dict[str, str] | None = None,
) -> None:
    from app.marketplace.workflow_contract import steps_to_rich_contract

    steps = _resolve_agent_seeds(steps, agent_ids_by_seed=agent_ids_by_seed or {})
    definition = {"schema_version": SCHEMA_VERSION, "steps": steps}
    workflow_config = {
        "marketplaceAssetId": asset_id,
        "pack_id": pack_id,
        "workflow_slug": WORKFLOW_SLUG,
        "replaces": "MSP NVD CVE Lookup",
    }
    contract_nodes, contract_edges = steps_to_rich_contract(steps)
    client.table("workflow_defs").upsert(
        {
            "id": workflow_id,
            "org_id": org_id,
            "name": name,
            "description": description,
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
            "name": name,
            "description": description,
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
        logger.debug("msp_pack_workflow_version_skipped err=%s", exc)


def _upgrade_legacy_named_workflows(
    client: Any,
    *,
    org_id: str,
    name: str,
    description: str,
    steps: list[dict[str, Any]],
    asset_id: str,
    pack_id: str,
    environment_name: str,
    actor_id: str,
    agent_ids_by_seed: dict[str, str] | None = None,
) -> list[str]:
    """In-place upgrade for orgs that still have the old NVD CVE Lookup title."""
    upgraded: list[str] = []
    try:
        rows = (
            client.table("workflows")
            .select("id, name")
            .eq("org_id", org_id)
            .eq("environment", environment_name)
            .in_("name", list(LEGACY_WORKFLOW_NAMES))
            .execute()
            .data
            or []
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("msp_legacy_workflow_lookup_skipped err=%s", exc)
        return upgraded
    for row in rows:
        wid = str(row.get("id") or "")
        if not wid:
            continue
        _upsert_workflow(
            client,
            org_id=org_id,
            workflow_id=wid,
            asset_id=asset_id,
            pack_id=pack_id,
            name=name,
            description=description,
            steps=steps,
            environment_name=environment_name,
            actor_id=actor_id,
            agent_ids_by_seed=agent_ids_by_seed,
        )
        upgraded.append(wid)
    return upgraded


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
    """Create prospecting coordinator + vuln analyst + list-builder workflow + stubs."""
    asset_id = str(asset["id"])

    scout_id = _marketplace_entity_id(org_id, asset_id, SCOUT_AGENT_SLUG)
    _upsert_agent(
        client,
        org_id=org_id,
        agent_id=scout_id,
        name=spec.demo_agent_name or SCOUT_AGENT_NAME,
        purpose=SCOUT_AGENT_PURPOSE,
        role=SCOUT_AGENT_ROLE,
        department=SCOUT_AGENT_DEPARTMENT,
        capabilities=list(SCOUT_AGENT_CAPABILITIES),
        systems=[s for s in SCOUT_AGENT_SYSTEMS if s in (spec.demo_systems or SCOUT_AGENT_SYSTEMS)]
        or list(SCOUT_AGENT_SYSTEMS),
        asset_id=asset_id,
        pack_id=spec.pack_id,
        actor_id=actor_id,
        environment_name=environment_name,
        guardrails=["no_byo_shared_keys"],
    )

    # Keep vuln analyst for NVD/CISA knowledge assignments (separate from list-builder).
    vuln_id = _marketplace_entity_id(org_id, asset_id, "msp-vuln-analyst")
    _upsert_agent(
        client,
        org_id=org_id,
        agent_id=vuln_id,
        name="MSP Vulnerability Analyst",
        purpose="Reads Gravitree-managed vulnerability feeds (NVD / CISA KEV) for MSP ops.",
        role="analyst",
        department="msp",
        capabilities=["vulnerability_intelligence", "nvd_lookup"],
        systems=["nvd", "cisa_kev"],
        asset_id=asset_id,
        pack_id=spec.pack_id,
        actor_id=actor_id,
        environment_name=environment_name,
        guardrails=["read_only_external_sources"],
    )

    # Primary agent for pack install metadata / knowledge assignment attach.
    agent_id = scout_id
    assignments = install_intelligence_pack(
        client,
        org_id,
        agent_id,
        spec.pack_id,
        actor_id=actor_id,
        asset_id=asset_id,
    )
    # Also attach vuln-focused knowledge to the vulnerability analyst.
    try:
        install_intelligence_pack(
            client,
            org_id,
            vuln_id,
            spec.pack_id,
            actor_id=actor_id,
            asset_id=asset_id,
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("msp_vuln_assignments_skipped err=%s", exc)

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
    upgraded_legacy: list[str] = []
    if spec.workflow_name and spec.workflow_steps:
        steps = list(spec.workflow_steps)
        agent_ids_by_seed = {f"agent:{SCOUT_AGENT_SLUG}": scout_id}
        # Keep legacy seed so existing installed workflow rows upgrade in place.
        workflow_id = _marketplace_entity_id(org_id, asset_id, "msp-nvd-workflow")
        _upsert_workflow(
            client,
            org_id=org_id,
            workflow_id=workflow_id,
            asset_id=asset_id,
            pack_id=spec.pack_id,
            name=spec.workflow_name,
            description=spec.workflow_description or "",
            steps=steps,
            environment_name=environment_name,
            actor_id=actor_id,
            agent_ids_by_seed=agent_ids_by_seed,
        )
        upgraded_legacy = _upgrade_legacy_named_workflows(
            client,
            org_id=org_id,
            name=spec.workflow_name,
            description=spec.workflow_description or "",
            steps=steps,
            asset_id=asset_id,
            pack_id=spec.pack_id,
            environment_name=environment_name,
            actor_id=actor_id,
            agent_ids_by_seed=agent_ids_by_seed,
        )

    return {
        "pack_id": spec.pack_id,
        "agentId": agent_id,
        "prospectingAgentId": scout_id,
        "vulnerabilityAgentId": vuln_id,
        "workflowId": workflow_id,
        "upgradedLegacyWorkflowIds": upgraded_legacy,
        "assignmentCount": assignments.get("count") or 0,
        "assignmentIds": [row.get("id") for row in assignments.get("assignments") or [] if row.get("id")],
        "connectorStubs": staged,
        "nvdActivated": activated_nvd,
        "cisaKevActivated": activated_cisa,
    }
