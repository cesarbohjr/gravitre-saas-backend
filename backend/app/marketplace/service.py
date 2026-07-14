"""Unified marketplace install orchestration (MKT-7.1)."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.billing.service import get_plan_for_org
from app.marketplace.schemas import (
    AgentAssetConfig,
    ConnectorConfigAssetConfig,
    DepartmentPackAssetConfig,
    KnowledgePackAssetConfig,
    RequiredConnectorRef,
    WorkflowAssetConfig,
    parse_asset_config,
    validate_install_variables,
    validate_required_connectors,
)
from app.marketplace.counters import increment_marketplace_counter
from app.marketplace.variables import VariableResolutionError, resolve_variables
from app.operators.repository import create_operator, list_operators
from app.services.agent_tool_permissions import default_demo_scopes_for_system, upsert_agent_tool_permission
from app.services.department_pack_catalog import get_pack_spec, pack_seed_id
from app.services.vertical_workflow_helper import ensure_active_workflow_version
from app.workflows.audit import write_audit_event
from app.workflows.constants import SCHEMA_VERSION

logger = logging.getLogger(__name__)

AUDIT_ASSET_INSTALLED = "marketplace.asset.installed"
RESOURCE_TYPE_MARKETPLACE_ASSET = "marketplace_asset"


class MarketplaceError(Exception):
    code = "MARKETPLACE_ERROR"

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        blockers: list[dict[str, Any]] | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        if code:
            self.code = code
        self.blockers = blockers or []
        self.details = details or {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_missing_table_error(error: Exception | None) -> bool:
    if error is None:
        return False
    message = str(error).lower()
    return "does not exist" in message or ("relation" in message and "does not exist" in message)


def marketplace_entity_id(org_id: str, asset_id: str, label: str) -> str:
    return pack_seed_id(org_id, f"marketplace:{asset_id}:{label}")


def _active_connector_types(client: Any, org_id: str, *, environment_name: str) -> set[str]:
    result = (
        client.table("connectors")
        .select("type")
        .eq("org_id", org_id)
        .eq("status", "active")
        .execute()
    )
    types = {str(row["type"]) for row in (result.data or []) if row.get("type")}
    if environment_name:
        try:
            env_result = (
                client.table("connectors")
                .select("type")
                .eq("org_id", org_id)
                .eq("status", "active")
                .eq("environment", environment_name)
                .execute()
            )
            types.update(str(row["type"]) for row in (env_result.data or []) if row.get("type"))
        except Exception as exc:
            if not _is_missing_table_error(exc):
                message = str(exc).lower()
                if "42703" not in message and "environment" not in message:
                    raise
    return types


def _staged_connector_types(client: Any, org_id: str, *, environment_name: str) -> set[str]:
    """Connectors pre-staged by template install (needs_connection / pending_auth)."""
    staged_statuses = ["needs_connection", "pending_auth", "pending"]
    types: set[str] = set()
    try:
        result = (
            client.table("connectors")
            .select("type,status")
            .eq("org_id", org_id)
            .in_("status", staged_statuses)
            .execute()
        )
        types = {str(row["type"]) for row in (result.data or []) if row.get("type")}
        if environment_name:
            env_result = (
                client.table("connectors")
                .select("type,status")
                .eq("org_id", org_id)
                .in_("status", staged_statuses)
                .eq("environment", environment_name)
                .execute()
            )
            types.update(str(row["type"]) for row in (env_result.data or []) if row.get("type"))
    except Exception as exc:
        if not _is_missing_table_error(exc):
            message = str(exc).lower()
            if "42703" not in message and "environment" not in message and "needs_connection" not in message:
                raise
    return types


def _find_active_connector_id(
    client: Any,
    org_id: str,
    connector_type: str,
    *,
    environment_name: str = "production",
) -> str | None:
    for env in {environment_name, "production", "default"}:
        result = (
            client.table("connectors")
            .select("id")
            .eq("org_id", org_id)
            .eq("type", connector_type)
            .eq("status", "active")
            .eq("environment", env)
            .limit(1)
            .execute()
        )
        if result.data:
            return str(result.data[0]["id"])
    result = (
        client.table("connectors")
        .select("id")
        .eq("org_id", org_id)
        .eq("type", connector_type)
        .eq("status", "active")
        .limit(1)
        .execute()
    )
    if not result.data:
        return None
    return str(result.data[0]["id"])


def validate_connectors_for_asset(
    client: Any,
    org_id: str,
    required_connectors: list[RequiredConnectorRef] | list[dict[str, Any]],
    *,
    environment_name: str = "production",
) -> dict[str, Any]:
    """Return ``{can_install, blockers, checklist}`` (MKT-9.1 shape)."""
    refs: list[RequiredConnectorRef]
    if not required_connectors:
        refs = []
    elif isinstance(required_connectors[0], RequiredConnectorRef):
        refs = list(required_connectors)  # type: ignore[arg-type]
    else:
        refs = validate_required_connectors(required_connectors)  # type: ignore[arg-type]
    active = _active_connector_types(client, org_id, environment_name=environment_name)
    staged = _staged_connector_types(client, org_id, environment_name=environment_name)
    blockers: list[dict[str, Any]] = []
    checklist: list[dict[str, Any]] = []
    for req in refs:
        connected = req.connector_type in active
        needs_connection = (not connected) and req.connector_type in staged
        action_url = req.connect_path or f"/connectors?type={req.connector_type}"
        checklist.append(
            {
                "connectorType": req.connector_type,
                "label": req.label or req.connector_type,
                "required": req.required,
                "connected": connected,
                "needsConnection": needs_connection,
                "status": "connected" if connected else ("needs_connection" if needs_connection else "missing"),
                "connectPath": action_url,
                "action_url": action_url,
                "ready": connected or not req.required,
            }
        )
        if req.required and not connected:
            blockers.append(
                {
                    "connector": req.connector_type,
                    "reason": (
                        f"{req.label or req.connector_type} is staged — complete connection"
                        if needs_connection
                        else f"{req.label or req.connector_type} is not connected"
                    ),
                    "action_url": action_url,
                    "needsConnection": needs_connection,
                }
            )
    return {
        "can_install": len(blockers) == 0,
        "blockers": blockers,
        "checklist": checklist,
    }


def fetch_marketplace_asset(client: Any, asset_ref: str) -> dict[str, Any]:
    """Load asset by UUID or slug."""
    try:
        query = client.table("marketplace_assets").select("*")
        if _looks_like_uuid(asset_ref):
            query = query.eq("id", asset_ref)
        else:
            query = query.eq("slug", asset_ref)
        result = query.limit(1).execute()
    except Exception as exc:
        if _is_missing_table_error(exc):
            raise MarketplaceError("Marketplace assets are not available", code="NOT_AVAILABLE") from exc
        raise
    if not result.data:
        raise MarketplaceError("Marketplace asset not found", code="NOT_FOUND")
    return dict(result.data[0])


def _looks_like_uuid(value: str) -> bool:
    try:
        import uuid

        uuid.UUID(str(value))
        return True
    except ValueError:
        return False


def _assert_asset_installable(asset: dict[str, Any]) -> None:
    if asset.get("status") != "published":
        raise MarketplaceError("Asset is not published", code="NOT_PUBLISHED")
    if asset.get("visibility") not in {"public", "internal", "private"}:
        raise MarketplaceError("Asset visibility is invalid", code="VALIDATION_ERROR")


def _resolve_asset_payload(
    asset: dict[str, Any],
    install_values: dict[str, str] | None,
) -> dict[str, Any]:
    declared = validate_install_variables(asset.get("install_variables"))
    merged_values = install_values or {}
    try:
        config = resolve_variables(asset.get("config") or {}, merged_values, declared=declared)
    except VariableResolutionError as exc:
        raise MarketplaceError(
            exc.message,
            code="INSTALL_VARIABLES_INVALID",
            details={"errors": exc.errors},
        ) from exc
    return {
        "config": config,
        "declared_variables": declared,
    }


def _check_plan_limits(client: Any, org_id: str, asset_type: str) -> None:
    from app.billing.entitlement_service import PlanLimitExceededError

    plan = get_plan_for_org(client, org_id)
    if asset_type in {"ai_agent", "department_pack"}:
        limit = plan.get("agents_limit")
        current = len(list_operators(client, org_id))
        if limit is not None and current >= int(limit):
            raise PlanLimitExceededError(
                limit_type="agent_count",
                current=current,
                max_allowed=int(limit),
            )
    if asset_type in {"workflow", "department_pack"}:
        limit = plan.get("workflows_limit")
        if limit is not None:
            # Soft-deactivate archives workflow_defs on uninstall (STA-309); archived
            # rows must not consume plan capacity or reinstall forever 402s.
            result = (
                client.table("workflow_defs")
                .select("id")
                .eq("org_id", org_id)
                .neq("status", "archived")
                .execute()
            )
            current = len(result.data or [])
            if current >= int(limit):
                raise PlanLimitExceededError(
                    limit_type="workflow_count",
                    current=current,
                    max_allowed=int(limit),
                )


def _resolve_workflow_steps(
    steps: list[dict[str, Any]],
    *,
    agent_ids: dict[str, str],
    connector_ids: dict[str, str | None],
) -> list[dict[str, Any]]:
    resolved: list[dict[str, Any]] = []
    for step in steps:
        requires = step.get("requires_connector")
        if requires and not connector_ids.get(str(requires)):
            continue
        row: dict[str, Any] = {
            "id": step["id"],
            "name": step["name"],
            "type": step["type"],
        }
        if step.get("config"):
            config = dict(step["config"])
            if requires and connector_ids.get(str(requires)):
                config["connector_id"] = connector_ids[str(requires)]
            row["config"] = config
        if step.get("metadata"):
            metadata = dict(step["metadata"])
            agent_seed = metadata.pop("agent_seed", None)
            if agent_seed:
                metadata["agent_id"] = agent_ids.get(str(agent_seed))
            next_agent_seed = metadata.pop("next_agent_seed", None)
            if next_agent_seed:
                next_agent_id = agent_ids.get(str(next_agent_seed))
                if next_agent_id:
                    metadata["next_agent_id"] = next_agent_id
            row["metadata"] = metadata
        resolved.append(row)
    if not resolved:
        resolved.append({"id": "overview", "name": "Overview", "type": "noop"})
    return resolved


def _mirror_agent_row(
    client: Any,
    org_id: str,
    *,
    agent_id: str,
    config: AgentAssetConfig,
    asset_id: str,
) -> None:
    client.table("agents").upsert(
        {
            "id": agent_id,
            "org_id": org_id,
            "name": config.name,
            "purpose": config.purpose,
            "role": config.role,
            "department": config.department,
            "model": config.model,
            "capabilities": config.capabilities,
            "systems": config.systems,
            "guardrails": config.guardrails,
            "config": {**(config.config or {}), "marketplaceAssetId": asset_id},
            "status": "active",
        },
        on_conflict="id",
    ).execute()


def _install_ai_agent(
    client: Any,
    org_id: str,
    asset: dict[str, Any],
    config: AgentAssetConfig,
    *,
    actor_id: str,
    environment_name: str,
) -> dict[str, Any]:
    seed = config.seed_label or "agent"
    entity_id = marketplace_entity_id(org_id, str(asset["id"]), seed)
    operator = create_operator(
        client,
        org_id,
        {
            "id": entity_id,
            "name": config.name,
            "description": config.purpose,
            "role": config.role,
            "capabilities": config.capabilities,
            "config": {**(config.config or {}), "marketplaceAssetId": asset["id"]},
            "allowed_environments": [environment_name],
            "status": "active",
        },
        created_by=actor_id,
    )
    _mirror_agent_row(client, org_id, agent_id=entity_id, config=config, asset_id=str(asset["id"]))
    for system in config.systems:
        upsert_agent_tool_permission(
            client,
            org_id,
            entity_id,
            connector_id=None,
            connector_type=str(system),
            scopes=default_demo_scopes_for_system(str(system)),
            granted_by=actor_id,
        )
    return {
        "entityType": "operator",
        "entityId": entity_id,
        "operatorId": operator["id"],
        "agentId": entity_id,
    }


def _install_workflow_entity(
    client: Any,
    org_id: str,
    asset: dict[str, Any],
    config: WorkflowAssetConfig,
    *,
    actor_id: str,
    environment_name: str,
    agent_ids: dict[str, str] | None = None,
    connector_ids: dict[str, str | None] | None = None,
    workflow_label: str = "workflow",
) -> dict[str, Any]:
    workflow_id = marketplace_entity_id(org_id, str(asset["id"]), workflow_label)
    steps = _resolve_workflow_steps(
        config.steps,
        agent_ids=agent_ids or {},
        connector_ids=connector_ids or {},
    )
    definition = {"schema_version": config.schema_version or SCHEMA_VERSION, "steps": steps}
    workflow_config = {"marketplaceAssetId": asset["id"]}

    client.table("workflow_defs").upsert(
        {
            "id": workflow_id,
            "org_id": org_id,
            "name": config.name,
            "description": config.description,
            "status": "active",
            "schema_version": config.schema_version or SCHEMA_VERSION,
            "definition": definition,
            "config": workflow_config,
        },
        on_conflict="id",
    ).execute()

    client.table("workflows").upsert(
        {
            "id": workflow_id,
            "org_id": org_id,
            "name": config.name,
            "description": config.description,
            "status": "active",
            "environment": environment_name,
            "nodes": [{"id": step["id"], "type": step["type"], "name": step["name"]} for step in steps],
            "edges": [{"from": steps[i]["id"], "to": steps[i + 1]["id"]} for i in range(len(steps) - 1)],
            "config": workflow_config,
        },
        on_conflict="id",
    ).execute()

    ensure_active_workflow_version(
        client,
        org_id,
        workflow_id,
        definition,
        environment_name=environment_name,
        actor_id=actor_id,
    )
    return {"entityType": "workflow", "entityId": workflow_id, "workflowId": workflow_id}


def _install_knowledge_pack(
    client: Any,
    org_id: str,
    asset: dict[str, Any],
    config: KnowledgePackAssetConfig,
    *,
    environment_name: str,
    primary_agent_id: str | None = None,
) -> dict[str, Any]:
    source_ids: list[str] = []
    rows: list[dict[str, Any]] = []
    for index, document in enumerate(config.documents):
        seed = document.seed_label or f"doc-{index}"
        source_id = marketplace_entity_id(org_id, str(asset["id"]), f"rag:{seed}")
        source_ids.append(source_id)
        rows.append(
            {
                "id": source_id,
                "org_id": org_id,
                "title": document.title,
                "name": document.title,
                "type": document.type,
                "status": "pending_upload",
                "environment": environment_name,
                "metadata": {**(document.metadata or {}), "marketplaceAssetId": asset["id"]},
                "agent_id": primary_agent_id,
            }
        )
    if rows:
        client.table("rag_sources").upsert(rows, on_conflict="id").execute()
    return {"entityType": "knowledge_pack", "entityId": source_ids[0], "ragSourceIds": source_ids}


def _install_department_pack(
    client: Any,
    org_id: str,
    asset: dict[str, Any],
    config: DepartmentPackAssetConfig,
    *,
    actor_id: str,
    environment_name: str,
    connector_ids: dict[str, str | None],
) -> dict[str, Any]:
    root_id = marketplace_entity_id(org_id, str(asset["id"]), "department-pack")
    agent_ids: dict[str, str] = {}
    installed_agents: list[str] = []
    failures: list[dict[str, Any]] = []

    for index, agent_cfg in enumerate(config.agents):
        seed = agent_cfg.seed_label or f"agent-{index}"
        try:
            result = _install_ai_agent(
                client,
                org_id,
                asset,
                agent_cfg,
                actor_id=actor_id,
                environment_name=environment_name,
            )
            agent_ids[seed] = result["entityId"]
            installed_agents.append(result["entityId"])
        except Exception as exc:
            failures.append({"item": seed, "error": str(exc)})

    rag_result = _install_knowledge_pack(
        client,
        org_id,
        asset,
        KnowledgePackAssetConfig(documents=config.rag_sources or []),
        environment_name=environment_name,
        primary_agent_id=next(iter(installed_agents), None),
    )
    workflow_result = _install_workflow_entity(
        client,
        org_id,
        asset,
        WorkflowAssetConfig(
            schema_version=SCHEMA_VERSION,
            name=config.workflow_name,
            description=config.workflow_description,
            steps=config.workflow_steps,
        ),
        actor_id=actor_id,
        environment_name=environment_name,
        agent_ids=agent_ids,
        connector_ids=connector_ids,
        workflow_label="department-workflow",
    )

    return {
        "entityType": "department_pack",
        "entityId": root_id,
        "agentIds": installed_agents,
        "workflowIds": [workflow_result["workflowId"]],
        "ragSourceIds": rag_result.get("ragSourceIds") or [],
        "failures": failures,
    }


def _install_connector_config(
    client: Any,
    org_id: str,
    asset: dict[str, Any],
    config: ConnectorConfigAssetConfig,
    *,
    environment_name: str,
) -> dict[str, Any]:
    connector_id = _find_active_connector_id(
        client,
        org_id,
        config.connector_type,
        environment_name=environment_name,
    )
    if config.required and not connector_id:
        raise MarketplaceError(
            f"Connector {config.connector_type} is not connected",
            code="CONNECTORS_NOT_READY",
        )
    return {
        "entityType": "connector",
        "entityId": connector_id or config.connector_type,
        "connectorId": connector_id,
        "connectorType": config.connector_type,
    }


def _install_intelligence_pack_asset(
    client: Any,
    org_id: str,
    asset: dict[str, Any],
    *,
    actor_id: str,
    install_variables: dict[str, str] | None,
    environment_name: str = "production",
    settings: Any | None = None,
) -> dict[str, Any]:
    """Wire catalog intelligence_pack installs through install_intelligence_pack (Part D P5).

    Demo packs (demo_agent_name set): create agent + workflow + connector stubs (no agentId).
    Dispatch by pack_id — Executive activates FRED; MSP activates NVD; Sales stages CRM only.
    Other packs still require installVariables.agentId.
    """
    from app.marketplace.intelligence_packs.catalog import get_intelligence_pack_spec
    from app.marketplace.intelligence_packs.executive_install import install_executive_pack_demo_bundle
    from app.marketplace.intelligence_packs.install import install_intelligence_pack
    from app.marketplace.intelligence_packs.msp_install import install_msp_pack_demo_bundle
    from app.marketplace.intelligence_packs.cs_install import install_cs_pack_demo_bundle
    from app.marketplace.intelligence_packs.prospecting_install import install_prospecting_pack_demo_bundle
    from app.marketplace.intelligence_packs.sales_install import install_sales_pack_demo_bundle

    pack_id = str(asset.get("slug") or asset.get("id") or "").strip()
    spec = get_intelligence_pack_spec(pack_id)

    if spec and spec.demo_agent_name:
        if pack_id == "msp-intelligence-pack":
            bundle = install_msp_pack_demo_bundle(
                client,
                org_id,
                asset,
                spec,
                actor_id=actor_id,
                environment_name=environment_name,
                settings=settings,
                activate_nvd=True,
            )
            return {
                "entityType": "intelligence_pack",
                "entityId": str(asset["id"]),
                "agentId": bundle.get("agentId"),
                "workflowId": bundle.get("workflowId"),
                "packId": pack_id,
                "assignmentIds": bundle.get("assignmentIds") or [],
                "assignmentCount": bundle.get("assignmentCount") or 0,
                "connectorStubs": bundle.get("connectorStubs"),
                "nvdActivated": bundle.get("nvdActivated"),
                "cisaKevActivated": bundle.get("cisaKevActivated"),
                "demoBundle": True,
            }

        if pack_id == "sales-intelligence-pack":
            bundle = install_sales_pack_demo_bundle(
                client,
                org_id,
                asset,
                spec,
                actor_id=actor_id,
                environment_name=environment_name,
                settings=settings,
            )
            return {
                "entityType": "intelligence_pack",
                "entityId": str(asset["id"]),
                "agentId": bundle.get("agentId"),
                "workflowId": bundle.get("workflowId"),
                "packId": pack_id,
                "assignmentIds": bundle.get("assignmentIds") or [],
                "assignmentCount": bundle.get("assignmentCount") or 0,
                "connectorStubs": bundle.get("connectorStubs"),
                "hubspotConnectorId": bundle.get("hubspotConnectorId"),
                "stopLinesHonored": bundle.get("stopLinesHonored"),
                "demoBundle": True,
            }

        if pack_id == "customer-success-intelligence-pack":
            bundle = install_cs_pack_demo_bundle(
                client,
                org_id,
                asset,
                spec,
                actor_id=actor_id,
                environment_name=environment_name,
                settings=settings,
            )
            return {
                "entityType": "intelligence_pack",
                "entityId": str(asset["id"]),
                "agentId": bundle.get("agentId"),
                "workflowId": bundle.get("workflowId"),
                "packId": pack_id,
                "assignmentIds": bundle.get("assignmentIds") or [],
                "assignmentCount": bundle.get("assignmentCount") or 0,
                "connectorStubs": bundle.get("connectorStubs"),
                "hubspotConnectorId": bundle.get("hubspotConnectorId"),
                "zendeskConnectorId": bundle.get("zendeskConnectorId"),
                "stopLinesHonored": bundle.get("stopLinesHonored"),
                "demoBundle": True,
            }

        if pack_id == "prospecting-intelligence-pack":
            bundle = install_prospecting_pack_demo_bundle(
                client,
                org_id,
                asset,
                spec,
                actor_id=actor_id,
                environment_name=environment_name,
                settings=settings,
            )
            return {
                "entityType": "intelligence_pack",
                "entityId": str(asset["id"]),
                "agentId": bundle.get("agentId"),
                "workflowId": bundle.get("workflowId"),
                "packId": pack_id,
                "assignmentIds": bundle.get("assignmentIds") or [],
                "assignmentCount": bundle.get("assignmentCount") or 0,
                "connectorStubs": bundle.get("connectorStubs"),
                "byoStubs": bundle.get("byoStubs"),
                "apolloConnectorId": bundle.get("apolloConnectorId"),
                "hubspotConnectorId": bundle.get("hubspotConnectorId"),
                "stopLinesHonored": bundle.get("stopLinesHonored"),
                "demoBundle": True,
            }

        if pack_id != "executive-intelligence-pack":
            raise MarketplaceError(
                f"Unknown intelligence pack demo installer for {pack_id}",
                code="VALIDATION_ERROR",
            )

        bundle = install_executive_pack_demo_bundle(
            client,
            org_id,
            asset,
            spec,
            actor_id=actor_id,
            environment_name=environment_name,
            settings=settings,
            activate_fred=True,
        )
        return {
            "entityType": "intelligence_pack",
            "entityId": str(asset["id"]),
            "agentId": bundle.get("agentId"),
            "workflowId": bundle.get("workflowId"),
            "packId": pack_id,
            "assignmentIds": bundle.get("assignmentIds") or [],
            "assignmentCount": bundle.get("assignmentCount") or 0,
            "connectorStubs": bundle.get("connectorStubs"),
            "fredActivated": bundle.get("fredActivated"),
            "secEdgarActivated": bundle.get("secEdgarActivated"),
            "demoBundle": True,
        }

    variables = install_variables or {}
    agent_id = str(
        variables.get("agentId")
        or variables.get("agent_id")
        or variables.get("AGENTID")
        or ""
    ).strip()
    if not agent_id:
        raise MarketplaceError(
            "intelligence_pack install requires installVariables.agentId",
            code="VALIDATION_ERROR",
        )
    result = install_intelligence_pack(
        client,
        org_id,
        agent_id,
        pack_id,
        actor_id=actor_id,
        asset_id=str(asset.get("id") or ""),
    )
    return {
        "entityType": "intelligence_pack",
        # marketplace_installs.installed_entity_id is uuid — use asset id, not slug.
        "entityId": str(asset["id"]),
        "agentId": agent_id,
        "packId": pack_id,
        "assignmentIds": [row.get("id") for row in result.get("assignments") or [] if row.get("id")],
        "assignmentCount": result.get("count") or 0,
    }


def _normalize_installed_entity_metadata(installed: dict[str, Any]) -> dict[str, Any]:
    """Ensure singular entity ids are mirrored into plural arrays for UI counts/deep links."""
    meta = {k: v for k, v in installed.items() if k not in {"entityType", "entityId"}}
    agent_ids = [str(v) for v in (meta.get("agentIds") or []) if v]
    workflow_ids = [str(v) for v in (meta.get("workflowIds") or []) if v]
    rag_ids = [str(v) for v in (meta.get("ragSourceIds") or []) if v]
    for key, bucket in (
        ("agentId", agent_ids),
        ("operatorId", agent_ids),
        ("workflowId", workflow_ids),
        ("ragSourceId", rag_ids),
    ):
        value = meta.get(key)
        if value and str(value) not in bucket:
            bucket.append(str(value))
    if agent_ids:
        meta["agentIds"] = agent_ids
    if workflow_ids:
        meta["workflowIds"] = workflow_ids
    if rag_ids:
        meta["ragSourceIds"] = rag_ids
    return meta


def _notify_asset_installed(
    client: Any,
    *,
    org_id: str,
    actor_id: str,
    asset: dict[str, Any],
    install_row: dict[str, Any],
    deep_links: list[dict[str, Any]],
) -> None:
    """Bell + email that the pack is live in this workspace."""
    title = str(asset.get("title") or asset.get("slug") or "Marketplace asset")
    primary = next((link for link in deep_links if link.get("path")), None)
    path = str((primary or {}).get("path") or "/marketplace/installed")
    body = (
        f"“{title}” is installed and ready in your Gravitre workspace. "
        "Open Agents, Workflows, or Installed to start using it."
    )
    try:
        from app.services.notification_emitter import emit_notification

        emit_notification(
            client,
            org_id=org_id,
            user_id=actor_id,
            event_type="system",
            title=f"Installed · {title}",
            body=body,
            entity_ref={
                "entity_type": "marketplace_install",
                "entity_id": str(install_row.get("id") or asset.get("id") or ""),
                "result_url": path,
            },
            channel_hints={"bell": True, "email": True},
            email_context={
                "kind": "marketplace_install",
                "asset_title": title,
                "asset_type": str(asset.get("asset_type") or ""),
                "view_path": path,
                "deep_link_count": len(deep_links),
            },
        )
    except Exception as exc:  # noqa: BLE001 — install must succeed even if notify fails
        logger.warning(
            "marketplace_install_notify_failed org_id=%s asset_id=%s error=%s",
            org_id,
            asset.get("id"),
            exc,
        )


def _record_install(
    client: Any,
    *,
    org_id: str,
    asset: dict[str, Any],
    installed: dict[str, Any],
    actor_id: str,
    install_variables: dict[str, str] | None,
    checklist: list[dict[str, Any]],
) -> dict[str, Any]:
    entity_meta = _normalize_installed_entity_metadata(installed)
    row = {
        "org_id": org_id,
        "asset_id": asset["id"],
        "asset_version": asset.get("current_version") or 1,
        "installed_entity_type": installed["entityType"],
        "installed_entity_id": installed["entityId"],
        "install_variables": install_variables or {},
        "status": "active",
        "installed_by": actor_id,
        "installed_at": _now(),
        "updated_at": _now(),
        "metadata": {
            "checklist": checklist,
            **entity_meta,
        },
    }
    existing = (
        client.table("marketplace_installs")
        .select("id")
        .eq("org_id", org_id)
        .eq("asset_id", asset["id"])
        .eq("status", "active")
        .limit(1)
        .execute()
    )
    if existing.data:
        result = (
            client.table("marketplace_installs")
            .update(row)
            .eq("id", existing.data[0]["id"])
            .execute()
        )
    else:
        result = client.table("marketplace_installs").insert(row).execute()
    return dict((result.data or [row])[0])


def _increment_install_count(client: Any, asset_id: str) -> None:
    increment_marketplace_counter(client, asset_id, "install_count")


def install_asset(
    client: Any,
    org_id: str,
    asset_id: str,
    *,
    actor_id: str,
    environment_name: str = "production",
    install_variables: dict[str, str] | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """
    Install a published marketplace asset into an org via existing creation paths.

    Raises ``MarketplaceError`` with ``blockers`` when connectors are missing.
    """
    asset = fetch_marketplace_asset(client, asset_id)
    _assert_asset_installable(asset)

    from app.marketplace.entitlements import assert_install_entitlement

    assert_install_entitlement(client, org_id, asset)

    legacy_pack = get_pack_spec(str(asset.get("slug") or ""))
    config_payload = asset.get("config") or {}
    if (
        legacy_pack
        and asset.get("asset_type") == "department_pack"
        and config_payload == {}
    ):
        from app.services.agent_role_marketplace_service import install_department_pack

        return install_department_pack(
            client,
            org_id,
            legacy_pack.pack_id,
            actor_id=actor_id,
            environment_name=environment_name,
        )

    connector_validation = validate_connectors_for_asset(
        client,
        org_id,
        asset.get("required_connectors") or [],
        environment_name=environment_name,
    )
    if not connector_validation["can_install"] and not force:
        raise MarketplaceError(
            "Connect required apps before installing this asset",
            code="CONNECTORS_NOT_READY",
            blockers=connector_validation["blockers"],
            details={"checklist": connector_validation["checklist"]},
        )

    _check_plan_limits(client, org_id, str(asset["asset_type"]))
    resolved = _resolve_asset_payload(asset, install_variables)
    parsed = parse_asset_config(str(asset["asset_type"]), resolved["config"], publish=True)
    connector_ids = {
        item["connectorType"]: _find_active_connector_id(
            client,
            org_id,
            item["connectorType"],
            environment_name=environment_name,
        )
        for item in connector_validation["checklist"]
        if item.get("connected")
    }

    asset_type = str(asset["asset_type"])
    if asset_type == "ai_agent":
        installed = _install_ai_agent(
            client,
            org_id,
            asset,
            parsed,  # type: ignore[arg-type]
            actor_id=actor_id,
            environment_name=environment_name,
        )
    elif asset_type == "workflow":
        installed = _install_workflow_entity(
            client,
            org_id,
            asset,
            parsed,  # type: ignore[arg-type]
            actor_id=actor_id,
            environment_name=environment_name,
            connector_ids=connector_ids,
        )
    elif asset_type == "knowledge_pack":
        installed = _install_knowledge_pack(
            client,
            org_id,
            asset,
            parsed,  # type: ignore[arg-type]
            environment_name=environment_name,
        )
    elif asset_type == "department_pack":
        installed = _install_department_pack(
            client,
            org_id,
            asset,
            parsed,  # type: ignore[arg-type]
            actor_id=actor_id,
            environment_name=environment_name,
            connector_ids=connector_ids,
        )
    elif asset_type == "connector_config":
        installed = _install_connector_config(
            client,
            org_id,
            asset,
            parsed,  # type: ignore[arg-type]
            environment_name=environment_name,
        )
    elif asset_type == "intelligence_pack":
        from app.config import get_settings

        installed = _install_intelligence_pack_asset(
            client,
            org_id,
            asset,
            actor_id=actor_id,
            install_variables=install_variables,
            environment_name=environment_name,
            settings=get_settings(),
        )
    else:
        raise MarketplaceError(f"Unsupported asset type: {asset_type}", code="VALIDATION_ERROR")

    install_row = _record_install(
        client,
        org_id=org_id,
        asset=asset,
        installed=installed,
        actor_id=actor_id,
        install_variables=install_variables,
        checklist=connector_validation["checklist"],
    )
    _increment_install_count(client, asset_id)

    write_audit_event(
        client,
        org_id=org_id,
        actor_id=actor_id,
        action=AUDIT_ASSET_INSTALLED,
        resource_type=RESOURCE_TYPE_MARKETPLACE_ASSET,
        resource_id=str(asset["id"]),
        metadata={
            "assetType": asset_type,
            "slug": asset.get("slug"),
            "entityType": installed["entityType"],
            "entityId": installed["entityId"],
            "installId": install_row.get("id"),
        },
    )
    from app.marketplace.support import build_install_deep_links

    deep_links = build_install_deep_links(install_row)
    _notify_asset_installed(
        client,
        org_id=org_id,
        actor_id=actor_id,
        asset=asset,
        install_row=install_row,
        deep_links=deep_links,
    )
    logger.info(
        "marketplace_asset_installed org_id=%s asset_id=%s entity_type=%s entity_id=%s",
        org_id,
        asset_id,
        installed["entityType"],
        installed["entityId"],
    )
    return {
        "installed": True,
        "assetId": asset_id,
        "assetType": asset_type,
        "slug": asset.get("slug"),
        "title": asset.get("title"),
        "install": install_row,
        "entities": installed,
        "deepLinks": deep_links,
        "connectorChecklist": connector_validation["checklist"],
    }


def preview_install(
    client: Any,
    org_id: str,
    asset_id: str,
    *,
    environment_name: str = "production",
) -> dict[str, Any]:
    asset = fetch_marketplace_asset(client, asset_id)
    validation = validate_connectors_for_asset(
        client,
        org_id,
        asset.get("required_connectors") or [],
        environment_name=environment_name,
    )
    from app.marketplace.entitlements import get_entitlement_status

    entitlement = get_entitlement_status(client, org_id, asset)
    payment_blockers: list[dict[str, Any]] = []
    can_install = validation["can_install"] and (
        not entitlement["requiresPayment"] or entitlement["hasEntitlement"]
    )
    if entitlement["requiresPayment"] and not entitlement["hasEntitlement"]:
        payment_blockers.append(
            {
                "connector": "payment",
                "reason": "Purchase required before install",
                "action_url": f"/marketplace/assets/{asset.get('slug')}?purchase=1",
            }
        )
    return {
        "assetId": asset_id,
        "slug": asset.get("slug"),
        "assetType": asset.get("asset_type"),
        "canInstall": can_install,
        "blockers": validation["blockers"] + payment_blockers,
        "connectorChecklist": validation["checklist"],
        **entitlement,
    }
