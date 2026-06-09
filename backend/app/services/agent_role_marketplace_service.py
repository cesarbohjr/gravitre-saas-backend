"""Agent role marketplace — one-click department pack install (STA-121)."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.services.agent_tool_permissions import default_demo_scopes_for_system, upsert_agent_tool_permission
from app.services.department_pack_catalog import (
    DepartmentPackSpec,
    get_pack_spec,
    list_pack_specs,
    pack_seed_id,
)
from app.services.vertical_workflow_helper import ensure_active_workflow_version
from app.workflows.audit import write_audit_event
from app.workflows.constants import SCHEMA_VERSION

logger = logging.getLogger(__name__)

AUDIT_ROLE_PACK_INSTALLED = "marketplace.role_pack.installed"

RESOURCE_TYPE_DEPARTMENT_PACK = "department_pack"


class RoleMarketplaceError(Exception):
    code = "ROLE_MARKETPLACE_ERROR"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        if code:
            self.code = code


def _is_missing_table_error(error: Exception | None) -> bool:
    if error is None:
        return False
    message = str(error).lower()
    return "does not exist" in message or ("relation" in message and "does not exist" in message)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def build_connector_checklist(
    client: Any,
    org_id: str,
    spec: DepartmentPackSpec,
    *,
    environment_name: str = "production",
) -> list[dict[str, Any]]:
    active = _active_connector_types(client, org_id, environment_name=environment_name)
    checklist: list[dict[str, Any]] = []
    for req in spec.required_connectors:
        connected = req.connector_type in active
        checklist.append(
            {
                "connectorType": req.connector_type,
                "label": req.label,
                "required": req.required,
                "connected": connected,
                "connectPath": req.connect_path,
                "ready": connected or not req.required,
            }
        )
    return checklist


def _serialize_install(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "packId": row["pack_id"],
        "department": row["department"],
        "agentIds": row.get("agent_ids") or [],
        "workflowIds": row.get("workflow_ids") or [],
        "ragSourceIds": row.get("rag_source_ids") or [],
        "connectorChecklist": row.get("connector_checklist") or [],
        "installedAt": row.get("installed_at"),
        "updatedAt": row.get("updated_at"),
    }


def _get_install_row(client: Any, org_id: str, pack_id: str) -> dict[str, Any] | None:
    try:
        result = (
            client.table("org_department_pack_installs")
            .select("*")
            .eq("org_id", org_id)
            .eq("pack_id", pack_id)
            .limit(1)
            .execute()
        )
    except Exception as exc:
        if _is_missing_table_error(exc):
            return None
        raise
    if _is_missing_table_error(getattr(result, "error", None)):
        return None
    if not result.data:
        return None
    return dict(result.data[0])


def _list_install_rows(client: Any, org_id: str) -> dict[str, dict[str, Any]]:
    try:
        installs = (
            client.table("org_department_pack_installs")
            .select("*")
            .eq("org_id", org_id)
            .execute()
        )
    except Exception as exc:
        if _is_missing_table_error(exc):
            return {}
        raise
    if _is_missing_table_error(getattr(installs, "error", None)):
        return {}
    return {str(row["pack_id"]): dict(row) for row in (installs.data or [])}


def _serialize_catalog_entry(
    spec: DepartmentPackSpec,
    *,
    installed: dict[str, Any] | None,
    checklist: list[dict[str, Any]],
) -> dict[str, Any]:
    required_total = sum(1 for item in checklist if item.get("required"))
    required_connected = sum(1 for item in checklist if item.get("required") and item.get("connected"))
    return {
        "packId": spec.pack_id,
        "name": spec.name,
        "department": spec.department,
        "description": spec.description,
        "tags": spec.marketplace_tags,
        "installed": installed is not None,
        "installedAt": installed.get("installed_at") if installed else None,
        "agentIds": (installed or {}).get("agent_ids") or [],
        "workflowIds": (installed or {}).get("workflow_ids") or [],
        "ragSourceIds": (installed or {}).get("rag_source_ids") or [],
        "connectorChecklist": checklist,
        "connectorsReady": required_connected >= required_total if required_total else True,
        "requiredConnectorsConnected": required_connected,
        "requiredConnectorsTotal": required_total,
    }


def list_department_packs(
    client: Any,
    org_id: str,
    *,
    environment_name: str = "production",
) -> list[dict[str, Any]]:
    by_pack = _list_install_rows(client, org_id)
    entries: list[dict[str, Any]] = []
    for spec in list_pack_specs():
        installed = by_pack.get(spec.pack_id)
        checklist = build_connector_checklist(client, org_id, spec, environment_name=environment_name)
        if installed and installed.get("connector_checklist"):
            checklist = installed["connector_checklist"]
        entries.append(_serialize_catalog_entry(spec, installed=installed, checklist=checklist))
    return entries


def get_department_pack(
    client: Any,
    org_id: str,
    pack_id: str,
    *,
    environment_name: str = "production",
) -> dict[str, Any]:
    spec = get_pack_spec(pack_id)
    if not spec:
        raise RoleMarketplaceError("Department pack not found", code="NOT_FOUND")
    installed = _get_install_row(client, org_id, pack_id)
    checklist = build_connector_checklist(client, org_id, spec, environment_name=environment_name)
    if installed and installed.get("connector_checklist"):
        checklist = installed["connector_checklist"]
    return _serialize_catalog_entry(spec, installed=installed, checklist=checklist)


def _resolve_workflow_steps(
    spec: DepartmentPackSpec,
    org_id: str,
    agent_ids: dict[str, str],
    connector_ids: dict[str, str | None],
) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    for step in spec.workflow_steps:
        requires = step.get("requires_connector")
        if requires and not connector_ids.get(str(requires)):
            continue
        row = {
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
            row["metadata"] = metadata
        steps.append(row)
    if not steps:
        steps.append(
            {
                "id": "pack_overview",
                "name": f"{spec.name} overview",
                "type": "noop",
            }
        )
    return steps


def _ensure_agents(
    client: Any,
    org_id: str,
    spec: DepartmentPackSpec,
    *,
    actor_id: str | None,
) -> tuple[dict[str, str], list[str]]:
    agent_ids: dict[str, str] = {}
    rows: list[dict[str, Any]] = []
    for agent in spec.agents:
        seed_label = str(agent["seed_label"])
        agent_id = pack_seed_id(org_id, f"{spec.pack_id}:{seed_label}")
        agent_ids[seed_label] = agent_id
        rows.append(
            {
                "id": agent_id,
                "org_id": org_id,
                "name": agent["name"],
                "purpose": agent["purpose"],
                "role": agent["role"],
                "department": agent["department"],
                "model": agent.get("model") or "gpt-4.1",
                "capabilities": agent.get("capabilities") or [],
                "systems": agent.get("systems") or [],
                "guardrails": agent.get("guardrails") or [],
                "config": agent.get("config") or {},
                "status": "active",
            }
        )
    if rows:
        client.table("agents").upsert(rows, on_conflict="id").execute()
    for agent in spec.agents:
        seed_label = str(agent["seed_label"])
        agent_id = agent_ids[seed_label]
        for system in agent.get("systems") or []:
            upsert_agent_tool_permission(
                client,
                org_id,
                agent_id,
                connector_id=None,
                connector_type=str(system),
                scopes=default_demo_scopes_for_system(str(system)),
                granted_by=actor_id,
            )
    return agent_ids, list(agent_ids.values())


def _ensure_rag_sources(
    client: Any,
    org_id: str,
    spec: DepartmentPackSpec,
    agent_ids: dict[str, str],
    *,
    environment_name: str,
) -> list[str]:
    source_ids: list[str] = []
    rows: list[dict[str, Any]] = []
    for source in spec.rag_sources:
        seed_label = str(source["seed_label"])
        source_id = pack_seed_id(org_id, f"{spec.pack_id}:{seed_label}")
        source_ids.append(source_id)
        primary_agent = next(iter(agent_ids.values()), None)
        rows.append(
            {
                "id": source_id,
                "org_id": org_id,
                "title": source["title"],
                "name": source["title"],
                "type": source.get("type") or "manual",
                "status": "pending_upload",
                "environment": environment_name,
                "metadata": source.get("metadata") or {},
                "agent_id": primary_agent,
            }
        )
    if rows:
        client.table("rag_sources").upsert(rows, on_conflict="id").execute()
    return source_ids


def _ensure_workflow(
    client: Any,
    org_id: str,
    spec: DepartmentPackSpec,
    *,
    agent_ids: dict[str, str],
    connector_ids: dict[str, str | None],
    environment_name: str,
    actor_id: str | None,
) -> str:
    workflow_id = pack_seed_id(org_id, f"{spec.pack_id}:workflow")
    steps = _resolve_workflow_steps(spec, org_id, agent_ids, connector_ids)
    definition = {"schema_version": SCHEMA_VERSION, "steps": steps}
    workflow_config = {"demo": True, "departmentPack": spec.pack_id}

    client.table("workflow_defs").upsert(
        {
            "id": workflow_id,
            "org_id": org_id,
            "name": spec.workflow_name,
            "description": spec.workflow_description,
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
            "description": spec.workflow_description,
            "status": "active",
            "environment": environment_name,
            "nodes": [{"id": step["id"], "type": step["type"], "name": step["name"]} for step in steps],
            "edges": [
                {"from": steps[i]["id"], "to": steps[i + 1]["id"]}
                for i in range(len(steps) - 1)
            ],
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
    return workflow_id


def install_department_pack(
    client: Any,
    org_id: str,
    pack_id: str,
    *,
    actor_id: str,
    environment_name: str = "production",
) -> dict[str, Any]:
    spec = get_pack_spec(pack_id)
    if not spec:
        raise RoleMarketplaceError("Department pack not found", code="NOT_FOUND")

    checklist = build_connector_checklist(client, org_id, spec, environment_name=environment_name)
    if any(item.get("required") and not item.get("connected") for item in checklist):
        raise RoleMarketplaceError(
            "Connect required apps before installing this department pack",
            code="CONNECTORS_NOT_READY",
        )

    connector_ids = {
        req.connector_type: _find_active_connector_id(
            client, org_id, req.connector_type, environment_name=environment_name
        )
        for req in spec.required_connectors
    }
    agent_ids_map, agent_id_list = _ensure_agents(client, org_id, spec, actor_id=actor_id)
    rag_source_ids = _ensure_rag_sources(
        client,
        org_id,
        spec,
        agent_ids_map,
        environment_name=environment_name,
    )
    workflow_id = _ensure_workflow(
        client,
        org_id,
        spec,
        agent_ids=agent_ids_map,
        connector_ids=connector_ids,
        environment_name=environment_name,
        actor_id=actor_id,
    )
    checklist = build_connector_checklist(client, org_id, spec, environment_name=environment_name)
    now = _now()

    row = {
        "org_id": org_id,
        "pack_id": pack_id,
        "department": spec.department,
        "agent_ids": agent_id_list,
        "workflow_ids": [workflow_id],
        "rag_source_ids": rag_source_ids,
        "connector_checklist": checklist,
        "installed_by": actor_id,
        "installed_at": now,
        "updated_at": now,
    }
    result = client.table("org_department_pack_installs").upsert(row, on_conflict="org_id,pack_id").execute()
    install_row = dict((result.data or [row])[0])

    write_audit_event(
        client,
        org_id=org_id,
        actor_id=actor_id,
        action=AUDIT_ROLE_PACK_INSTALLED,
        resource_type=RESOURCE_TYPE_DEPARTMENT_PACK,
        resource_id=pack_id,
        metadata={
            "department": spec.department,
            "workflowId": workflow_id,
            "connectorsReady": all(item.get("ready") for item in checklist),
        },
    )
    logger.info(
        "department_pack_installed org_id=%s pack_id=%s workflow_id=%s",
        org_id,
        pack_id,
        workflow_id,
    )
    payload = _serialize_catalog_entry(spec, installed=install_row, checklist=checklist)
    payload["installed"] = True
    return payload
