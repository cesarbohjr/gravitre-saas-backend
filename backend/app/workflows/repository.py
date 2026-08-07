"""BE-11: Workflow defs, runs, steps, audit — read and write via Supabase."""
from __future__ import annotations

from typing import Any
from datetime import datetime, timezone
from uuid import UUID

from supabase import Client, create_client

from app.config import Settings
from app.workflows.audit import write_audit_event
from app.workflows.schema_sync import contract_row_to_legacy_def, mirror_legacy_run_to_contract
from app.workflows.constants import (
    AUDIT_ACTION_DRY_RUN_COMPLETED,
    AUDIT_ACTION_DRY_RUN_STARTED,
    AUDIT_ACTION_DRY_RUN_STEP_COMPLETED,
    AUDIT_ACTION_DRY_RUN_STEP_FAILED,
    AUDIT_ACTION_EXECUTE_APPROVAL_RECORDED,
    AUDIT_ACTION_EXECUTE_APPROVED,
    AUDIT_ACTION_EXECUTE_CANCELLED,
    AUDIT_ACTION_EXECUTE_COMPLETED,
    AUDIT_ACTION_EXECUTE_CREATED,
    AUDIT_ACTION_EXECUTE_FAILED,
    AUDIT_ACTION_EXECUTE_PENDING_APPROVAL,
    AUDIT_ACTION_EXECUTE_REJECTED,
    AUDIT_ACTION_EXECUTE_STARTED,
    AUDIT_ACTION_EXECUTE_STEP_COMPLETED,
    AUDIT_ACTION_EXECUTE_STEP_FAILED,
    RESOURCE_TYPE_WORKFLOW_RUN,
)
from app.workflows.schema import compute_run_hash, validate_definition, validate_parameters
from app.core.safe_dict import safe_normalize_stored_dict


def get_supabase_client(settings: Settings) -> Client:
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


def get_workflow_def(client: Client, org_id: str, workflow_id: str) -> dict | None:
    contract = (
        client.table("workflows")
        .select("*")
        .eq("id", workflow_id)
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    )
    if contract.data:
        return contract_row_to_legacy_def(dict(contract.data[0]))
    r = (
        client.table("workflow_defs")
        .select("*")
        .eq("id", workflow_id)
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    )
    if not r.data or len(r.data) == 0:
        return None
    return dict(r.data[0])


def list_workflows(client: Client, org_id: str) -> list[dict]:
    contract_rows: list[dict] = []
    try:
        contract_result = (
            client.table("workflows")
            .select("id, name, description, status, version, updated_at, created_at")
            .eq("org_id", org_id)
            .order("updated_at", desc=True)
            .execute()
        )
        contract_rows = [contract_row_to_legacy_def(dict(row)) for row in (contract_result.data or [])]
    except Exception as exc:
        message = str(exc).lower()
        if "42703" not in message and not ("column" in message and "does not exist" in message):
            raise

    contract_ids = {str(row.get("id")) for row in contract_rows if row.get("id")}
    base_columns = (
        "id, name, description, status, version, schema_version, "
        "run_count, success_rate, last_run_at, updated_at"
    )
    extended_columns = f"{base_columns}, goal, stage, next_run_at"
    legacy_rows: list[dict] = []
    for columns in (extended_columns, base_columns):
        try:
            r = (
                client.table("workflow_defs")
                .select(columns)
                .eq("org_id", org_id)
                .order("updated_at", desc=True)
                .execute()
            )
            legacy_rows = list(r.data) if r.data else []
            break
        except Exception as exc:
            message = str(exc).lower()
            if "42703" in message or ("column" in message and "does not exist" in message):
                continue
            raise

    merged = list(contract_rows)
    for row in legacy_rows:
        if str(row.get("id")) not in contract_ids:
            merged.append(dict(row))
    merged.sort(key=lambda item: str(item.get("updated_at") or ""), reverse=True)
    return merged


def list_workflow_versions(
    client: Client,
    org_id: str,
    workflow_id: str,
    environment_name: str,
) -> list[dict]:
    r = (
        client.table("workflow_versions")
        .select("id, version, created_at, created_by, schema_version")
        .eq("org_id", org_id)
        .eq("environment", environment_name)
        .eq("workflow_id", workflow_id)
        .order("version", desc=True)
        .execute()
    )
    return list(r.data) if r.data else []


def get_workflow_version(
    client: Client,
    org_id: str,
    workflow_id: str,
    environment_name: str,
    version_id: str,
) -> dict | None:
    r = (
        client.table("workflow_versions")
        .select("*")
        .eq("id", version_id)
        .eq("org_id", org_id)
        .eq("workflow_id", workflow_id)
        .eq("environment", environment_name)
        .limit(1)
        .execute()
    )
    if not r.data:
        return None
    return dict(r.data[0])


def get_next_workflow_version_number(
    client: Client,
    org_id: str,
    workflow_id: str,
    environment_name: str,
) -> int:
    r = (
        client.table("workflow_versions")
        .select("version")
        .eq("org_id", org_id)
        .eq("environment", environment_name)
        .eq("workflow_id", workflow_id)
        .order("version", desc=True)
        .limit(1)
        .execute()
    )
    if not r.data:
        return 1
    return int(r.data[0].get("version") or 0) + 1


def create_workflow_version(
    client: Client,
    org_id: str,
    workflow_id: str,
    environment_name: str,
    version: int,
    definition: dict,
    schema_version: str,
    created_by: str | None,
) -> dict:
    row = {
        "org_id": org_id,
        "environment": environment_name,
        "workflow_id": workflow_id,
        "version": version,
        "definition": definition,
        "schema_version": schema_version,
        "created_by": created_by,
    }
    r = client.table("workflow_versions").insert(row).execute()
    if not r.data or len(r.data) == 0:
        raise RuntimeError("workflow_versions insert returned no row")
    return dict(r.data[0])


def get_active_workflow_version(
    client: Client,
    org_id: str,
    workflow_id: str,
    environment_name: str,
) -> dict | None:
    r = (
        client.table("workflow_active_versions")
        .select("active_version_id")
        .eq("org_id", org_id)
        .eq("environment", environment_name)
        .eq("workflow_id", workflow_id)
        .limit(1)
        .execute()
    )
    if not r.data:
        return None
    version_id = r.data[0].get("active_version_id")
    if not version_id:
        return None
    v = (
        client.table("workflow_versions")
        .select("*")
        .eq("id", version_id)
        .eq("org_id", org_id)
        .eq("environment", environment_name)
        .eq("workflow_id", workflow_id)
        .limit(1)
        .execute()
    )
    if not v.data:
        return None
    return dict(v.data[0])


def set_active_workflow_version(
    client: Client,
    org_id: str,
    workflow_id: str,
    environment_name: str,
    version_id: str,
    updated_by: str | None,
) -> None:
    now_iso = datetime.now(timezone.utc).isoformat()
    row = {
        "org_id": org_id,
        "environment": environment_name,
        "workflow_id": workflow_id,
        "active_version_id": version_id,
        "updated_at": now_iso,
        "updated_by": updated_by,
    }
    client.table("workflow_active_versions").upsert(
        row,
        on_conflict="org_id,environment,workflow_id",
    ).execute()


def create_run(
    client: Client,
    org_id: str,
    triggered_by: str,
    definition_snapshot: dict,
    parameters: dict,
    run_hash: str,
    workflow_id: str | None = None,
    environment_name: str = "default",
    workflow_version_id: str | None = None,
    trigger_type: str = "manual",
    run_type: str = "dry_run",
) -> dict:
    row = {
        "org_id": org_id,
        "workflow_id": workflow_id,
        "run_type": run_type,
        "status": "running",
        "triggered_by": triggered_by,
        "definition_snapshot": definition_snapshot,
        "parameters": parameters,
        "run_hash": run_hash,
        "environment": environment_name,
        "trigger_type": trigger_type,
    }
    if workflow_version_id:
        row["workflow_version_id"] = workflow_version_id
    r = client.table("workflow_runs").insert(row).execute()
    if not r.data or len(r.data) == 0:
        raise RuntimeError("workflow_runs insert returned no row")
    created = dict(r.data[0])
    mirror_legacy_run_to_contract(client, str(created["id"]))
    return created


def update_run(
    client: Client,
    run_id: str,
    status: str,
    completed_at: str | None = None,
    error_message: str | None = None,
    approval_status: str | None = None,
    parameters: dict[str, Any] | None = None,
) -> None:
    payload: dict[str, Any] = {"status": status}
    if completed_at is not None:
        payload["completed_at"] = completed_at
    if error_message is not None:
        payload["error_message"] = error_message
    if approval_status is not None:
        payload["approval_status"] = approval_status
    if parameters is not None:
        payload["parameters"] = parameters
    patch_workflow_run(client, run_id, payload)


def patch_workflow_run(client: Client, run_id: str, payload: dict[str, Any]) -> None:
    """Update workflow_runs then always mirror into contract runs / run_steps."""
    client.table("workflow_runs").update(payload).eq("id", run_id).execute()
    mirror_legacy_run_to_contract(client, run_id)


def merge_run_parameters(client: Client, run_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    """Merge keys into workflow_runs.parameters (read-modify-write)."""
    row = client.table("workflow_runs").select("parameters").eq("id", run_id).limit(1).execute()
    current = safe_normalize_stored_dict((row.data or [{}])[0], key='parameters')
    current.update(patch)
    patch_workflow_run(client, run_id, {"parameters": current})
    return current


def try_mark_run_running(client: Client, run_id: str, org_id: str) -> bool:
    """Transition pending_approval -> running; returns True if claimed."""
    r = (
        client.table("workflow_runs")
        .update({"status": "running", "approval_status": "approved"})
        .eq("id", run_id)
        .eq("org_id", org_id)
        .eq("status", "pending_approval")
        .eq("approval_status", "pending_approval")
        .execute()
    )
    if r.data:
        # Always mirror after a successful claim so contract runs stay in sync.
        mirror_legacy_run_to_contract(client, run_id)
    return bool(r.data)


def create_execute_run(
    client: Client,
    org_id: str,
    workflow_id: str,
    triggered_by: str,
    definition_snapshot: dict,
    parameters: dict,
    run_hash: str,
    status: str,
    approval_status: str | None,
    required_approvals: int,
    approver_roles: list[str],
    environment_name: str = "default",
    workflow_version_id: str | None = None,
    trigger_type: str = "manual",
    schedule_id: str | None = None,
    rollback_of_run_id: str | None = None,
) -> dict:
    """Create execute run with approval snapshot. workflow_id required."""
    row: dict[str, Any] = {
        "org_id": org_id,
        "workflow_id": workflow_id,
        "run_type": "execute",
        "status": status,
        "triggered_by": triggered_by,
        "definition_snapshot": definition_snapshot,
        "parameters": parameters,
        "run_hash": run_hash,
        "required_approvals": required_approvals,
        "approver_roles": approver_roles,
        "environment": environment_name,
        "trigger_type": trigger_type,
    }
    if schedule_id:
        row["schedule_id"] = schedule_id
    if rollback_of_run_id:
        row["rollback_of_run_id"] = rollback_of_run_id
    if workflow_version_id:
        row["workflow_version_id"] = workflow_version_id
    if approval_status is not None:
        row["approval_status"] = approval_status
    r = client.table("workflow_runs").insert(row).execute()
    if not r.data or len(r.data) == 0:
        raise RuntimeError("workflow_runs insert returned no row")
    created = dict(r.data[0])
    mirror_legacy_run_to_contract(client, str(created["id"]))
    return created


def insert_run_approval(
    client: Client,
    run_id: str,
    org_id: str,
    approver_id: str,
    status: str,
    comment: str | None = None,
) -> dict:
    """
    Insert approval. Idempotent: if (run_id, approver_id) exists, return existing row.
    Returns inserted or existing row.
    """
    r = (
        client.table("run_approvals")
        .select("*")
        .eq("run_id", run_id)
        .eq("approver_id", approver_id)
        .limit(1)
        .execute()
    )
    if r.data and len(r.data) > 0:
        existing = dict(r.data[0])
        if str(existing.get("status") or "") == status:
            return existing
        updated = (
            client.table("run_approvals")
            .update({"status": status, "comment": comment})
            .eq("run_id", run_id)
            .eq("approver_id", approver_id)
            .execute()
        )
        if updated.data and len(updated.data) > 0:
            return dict(updated.data[0])
        return existing
    ins = client.table("run_approvals").insert({
        "run_id": run_id,
        "org_id": org_id,
        "approver_id": approver_id,
        "status": status,
        "comment": comment,
    }).execute()
    if not ins.data or len(ins.data) == 0:
        raise RuntimeError("run_approvals insert returned no row")
    return dict(ins.data[0])


def get_approval_counts(client: Client, run_id: str) -> tuple[int, bool]:
    """
    Returns (approved_count, has_rejected).
    Any rejection cancels the run per plan.
    """
    r = (
        client.table("run_approvals")
        .select("status")
        .eq("run_id", run_id)
        .execute()
    )
    if not r.data:
        return 0, False
    approved = sum(1 for x in r.data if x.get("status") == "approved")
    rejected = any(x.get("status") == "rejected" for x in r.data)
    return approved, rejected


def create_step(
    client: Client,
    run_id: str,
    org_id: str,
    step_id: str,
    step_index: int,
    step_name: str,
    step_type: str,
) -> dict:
    row = {
        "run_id": run_id,
        "org_id": org_id,
        "step_id": step_id,
        "step_index": step_index,
        "step_name": step_name,
        "step_type": step_type,
        "status": "pending",
    }
    r = client.table("workflow_steps").insert(row).execute()
    if not r.data or len(r.data) == 0:
        raise RuntimeError("workflow_steps insert returned no row")
    return dict(r.data[0])


def update_step(
    client: Client,
    step_uuid: str,
    status: str,
    output_snapshot: dict | None = None,
    input_snapshot: dict | None = None,
    logs: str | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
    is_retryable: bool = False,
    started_at: str | None = None,
    completed_at: str | None = None,
) -> None:
    payload: dict[str, Any] = {"status": status}
    if output_snapshot is not None:
        payload["output_snapshot"] = output_snapshot
    if input_snapshot is not None:
        payload["input_snapshot"] = input_snapshot
    if logs is not None:
        payload["logs"] = logs
    if error_code is not None:
        payload["error_code"] = error_code
    if error_message is not None:
        payload["error_message"] = error_message
    payload["is_retryable"] = is_retryable
    if started_at is not None:
        payload["started_at"] = started_at
    if completed_at is not None:
        payload["completed_at"] = completed_at
    client.table("workflow_steps").update(payload).eq("id", step_uuid).execute()


def set_step_running(client: Client, step_uuid: str, started_at: str) -> None:
    client.table("workflow_steps").update({
        "status": "running",
        "started_at": started_at,
    }).eq("id", step_uuid).execute()


def get_run_with_steps(
    client: Client,
    org_id: str,
    run_id: str,
    environment_name: str = "default",
) -> dict | None:
    r = (
        client.table("workflow_runs")
        .select("*")
        .eq("id", run_id)
        .eq("org_id", org_id)
        .eq("environment", environment_name)
        .limit(1)
        .execute()
    )
    if not r.data or len(r.data) == 0:
        return None
    run = dict(r.data[0])
    s = (
        client.table("workflow_steps")
        .select("*")
        .eq("run_id", run_id)
        .order("step_index")
        .execute()
    )
    run["steps"] = list(s.data) if s.data else []
    return run


def list_workflow_nodes(
    client: Client,
    org_id: str,
    workflow_id: str,
    environment_name: str = "default",
) -> list[dict]:
    r = (
        client.table("workflow_nodes")
        .select("*")
        .eq("org_id", org_id)
        .eq("workflow_id", workflow_id)
        .eq("environment", environment_name)
        .order("created_at", desc=False)
        .execute()
    )
    return list(r.data or [])


def get_workflow_node(
    client: Client,
    org_id: str,
    node_id: str,
    environment_name: str = "default",
) -> dict | None:
    r = (
        client.table("workflow_nodes")
        .select("*")
        .eq("id", node_id)
        .eq("org_id", org_id)
        .eq("environment", environment_name)
        .limit(1)
        .execute()
    )
    if not r.data:
        return None
    return dict(r.data[0])


def create_workflow_node(
    client: Client,
    org_id: str,
    workflow_id: str,
    environment_name: str,
    payload: dict,
    created_by: str | None,
) -> dict:
    row: dict[str, Any] = {
        "org_id": org_id,
        "workflow_id": workflow_id,
        "environment": environment_name,
        "node_type": payload["node_type"],
        "title": payload["title"],
        "name": payload.get("name"),
        "description": payload.get("description"),
        "instruction": payload.get("instruction"),
        "config": payload.get("config") or {},
        "operator_id": payload.get("operator_id"),
        "connector_id": payload.get("connector_id"),
        "source_id": payload.get("source_id"),
        "tool_type": payload.get("tool_type"),
        "tool_config": payload.get("tool_config"),
        "position": payload.get("position"),
        "position_x": payload.get("position_x") or 0,
        "position_y": payload.get("position_y") or 0,
        "order_index": payload.get("order_index") or 0,
        "metadata": payload.get("metadata"),
        "created_by": created_by,
    }
    optional_fields = (
        "system_icon",
        "system_name",
        "has_approval_gate",
        "inputs",
        "outputs",
        "guardrails",
        "status",
    )
    for key in optional_fields:
        if key in payload and payload[key] is not None:
            row[key] = payload[key]
    if payload.get("id"):
        row["id"] = payload["id"]
    r = client.table("workflow_nodes").insert(row).execute()
    if not r.data or len(r.data) == 0:
        detail = getattr(r, "error", None)
        message = str(detail) if detail else "workflow_nodes insert returned no row"
        raise ValueError(message)
    return dict(r.data[0])


def update_workflow_node(
    client: Client,
    org_id: str,
    node_id: str,
    environment_name: str,
    payload: dict,
    updated_by: str | None,
) -> dict | None:
    update: dict[str, Any] = {"updated_at": datetime.now(timezone.utc).isoformat()}
    for key in (
        "node_type",
        "title",
        "name",
        "description",
        "instruction",
        "config",
        "system_icon",
        "system_name",
        "has_approval_gate",
        "inputs",
        "outputs",
        "guardrails",
        "status",
        "operator_id",
        "connector_id",
        "source_id",
        "tool_type",
        "tool_config",
        "position",
        "position_x",
        "position_y",
        "order_index",
        "metadata",
    ):
        if key in payload:
            update[key] = payload[key]
    if updated_by:
        update["updated_by"] = updated_by
    r = (
        client.table("workflow_nodes")
        .update(update)
        .eq("id", node_id)
        .eq("org_id", org_id)
        .eq("environment", environment_name)
        .execute()
    )
    if not r.data:
        return None
    return dict(r.data[0])


def delete_workflow_node(client: Client, org_id: str, node_id: str, environment_name: str) -> bool:
    # Phase 1: cascade incident edges so incremental DELETE /nodes cannot leave ghosts.
    try:
        client.table("workflow_edges").delete().eq("org_id", org_id).eq(
            "environment", environment_name
        ).eq("from_node_id", node_id).execute()
        client.table("workflow_edges").delete().eq("org_id", org_id).eq(
            "environment", environment_name
        ).eq("to_node_id", node_id).execute()
    except Exception:  # noqa: BLE001
        pass
    r = (
        client.table("workflow_nodes")
        .delete()
        .eq("id", node_id)
        .eq("org_id", org_id)
        .eq("environment", environment_name)
        .execute()
    )
    return bool(r.data)


def list_workflow_edges(
    client: Client,
    org_id: str,
    workflow_id: str,
    environment_name: str = "default",
) -> list[dict]:
    r = (
        client.table("workflow_edges")
        .select("*")
        .eq("org_id", org_id)
        .eq("workflow_id", workflow_id)
        .eq("environment", environment_name)
        .order("created_at", desc=False)
        .execute()
    )
    return list(r.data or [])


def get_workflow_edge(
    client: Client,
    org_id: str,
    edge_id: str,
    environment_name: str = "default",
) -> dict | None:
    r = (
        client.table("workflow_edges")
        .select("*")
        .eq("id", edge_id)
        .eq("org_id", org_id)
        .eq("environment", environment_name)
        .limit(1)
        .execute()
    )
    if not r.data:
        return None
    return dict(r.data[0])


def create_workflow_edge(
    client: Client,
    org_id: str,
    workflow_id: str,
    environment_name: str,
    payload: dict,
    created_by: str | None,
) -> dict:
    row: dict[str, Any] = {
        "org_id": org_id,
        "workflow_id": workflow_id,
        "environment": environment_name,
        "from_node_id": payload["from_node_id"],
        "to_node_id": payload["to_node_id"],
        "edge_type": payload.get("edge_type") or "sequence",
        "condition": payload.get("condition"),
        "created_by": created_by,
    }
    r = client.table("workflow_edges").insert(row).execute()
    if not r.data or len(r.data) == 0:
        detail = getattr(r, "error", None)
        message = str(detail) if detail else "workflow_edges insert returned no row"
        raise ValueError(message)
    return dict(r.data[0])


def delete_workflow_edge(client: Client, org_id: str, edge_id: str, environment_name: str) -> bool:
    r = (
        client.table("workflow_edges")
        .delete()
        .eq("id", edge_id)
        .eq("org_id", org_id)
        .eq("environment", environment_name)
        .execute()
    )
    return bool(r.data)


def list_workflow_schedules(
    client: Client,
    org_id: str,
    workflow_id: str,
    environment_name: str = "default",
) -> list[dict]:
    r = (
        client.table("workflow_schedules")
        .select("*")
        .eq("org_id", org_id)
        .eq("workflow_id", workflow_id)
        .eq("environment", environment_name)
        .order("created_at", desc=True)
        .execute()
    )
    return list(r.data) if r.data else []


def list_org_workflow_schedules(
    client: Client,
    org_id: str,
    environment_name: str = "default",
    workflow_id: str | None = None,
) -> list[dict]:
    q = (
        client.table("workflow_schedules")
        .select("*")
        .eq("org_id", org_id)
        .eq("environment", environment_name)
        .order("created_at", desc=True)
    )
    if workflow_id:
        q = q.eq("workflow_id", workflow_id)
    r = q.execute()
    return list(r.data) if r.data else []


def workflow_names_for_ids(client: Client, org_id: str, workflow_ids: list[str]) -> dict[str, str]:
    if not workflow_ids:
        return {}
    names: dict[str, str] = {}
    primary = (
        client.table("workflows")
        .select("id, name")
        .eq("org_id", org_id)
        .in_("id", workflow_ids)
        .execute()
    )
    for row in primary.data or []:
        names[str(row["id"])] = row.get("name") or ""
    missing = [wid for wid in workflow_ids if not names.get(wid)]
    if missing:
        legacy = (
            client.table("workflow_defs")
            .select("id, name")
            .eq("org_id", org_id)
            .in_("id", missing)
            .execute()
        )
        for row in legacy.data or []:
            names[str(row["id"])] = row.get("name") or ""
    return names


def get_workflow_schedule(
    client: Client,
    org_id: str,
    schedule_id: str,
    environment_name: str = "default",
) -> dict | None:
    r = (
        client.table("workflow_schedules")
        .select("*")
        .eq("id", schedule_id)
        .eq("org_id", org_id)
        .eq("environment", environment_name)
        .limit(1)
        .execute()
    )
    if not r.data:
        return None
    return dict(r.data[0])


def create_workflow_schedule(
    client: Client,
    org_id: str,
    workflow_id: str,
    cron_expression: str,
    environment_name: str,
    enabled: bool,
    next_run_at: str | None,
    created_by: str | None,
    *,
    timezone_name: str = "UTC",
    schedule_type: str = "recurring",
    run_at: str | None = None,
    name: str | None = None,
    ends_at: str | None = None,
) -> dict:
    # Prod schema has `enabled` only (no `is_enabled`). Writing the alias
    # column makes PostgREST reject the insert (PGRST204) — empty calendar.
    row: dict[str, Any] = {
        "org_id": org_id,
        "workflow_id": workflow_id,
        "cron_expression": cron_expression,
        "environment": environment_name,
        "enabled": enabled,
        "next_run_at": next_run_at,
        "created_by": created_by,
        "timezone": timezone_name or "UTC",
        "schedule_type": schedule_type or "recurring",
        "run_at": run_at,
        "name": name,
        "ends_at": ends_at,
    }
    r = client.table("workflow_schedules").insert(row).execute()
    if not r.data or len(r.data) == 0:
        raise RuntimeError("workflow_schedules insert returned no row")
    return dict(r.data[0])


def update_workflow_schedule(
    client: Client,
    org_id: str,
    schedule_id: str,
    environment_name: str,
    cron_expression: str | None,
    enabled: bool | None,
    next_run_at: str | None,
    updated_by: str | None,
    *,
    timezone_name: str | None = None,
    schedule_type: str | None = None,
    run_at: str | None = None,
    name: str | None = None,
    ends_at: str | None = None,
    clear_run_at: bool = False,
    clear_ends_at: bool = False,
    clear_next_run_at: bool = False,
) -> dict | None:
    payload: dict[str, Any] = {"updated_at": datetime.now(timezone.utc).isoformat()}
    if cron_expression is not None:
        payload["cron_expression"] = cron_expression
    if enabled is not None:
        payload["enabled"] = enabled
    if clear_next_run_at:
        payload["next_run_at"] = None
    elif next_run_at is not None:
        payload["next_run_at"] = next_run_at
    if timezone_name is not None:
        payload["timezone"] = timezone_name or "UTC"
    if schedule_type is not None:
        payload["schedule_type"] = schedule_type
    if clear_run_at:
        payload["run_at"] = None
    elif run_at is not None:
        payload["run_at"] = run_at
    if name is not None:
        payload["name"] = name
    if clear_ends_at:
        payload["ends_at"] = None
    elif ends_at is not None:
        payload["ends_at"] = ends_at
    if updated_by:
        payload["updated_by"] = updated_by
    r = (
        client.table("workflow_schedules")
        .update(payload)
        .eq("id", schedule_id)
        .eq("org_id", org_id)
        .eq("environment", environment_name)
        .execute()
    )
    if not r.data:
        return None
    return dict(r.data[0])


def delete_workflow_schedule(client: Client, org_id: str, schedule_id: str, environment_name: str) -> bool:
    r = (
        client.table("workflow_schedules")
        .delete()
        .eq("id", schedule_id)
        .eq("org_id", org_id)
        .eq("environment", environment_name)
        .execute()
    )
    return bool(r.data)


def emit_dry_run_started(client: Client, org_id: str, actor_id: str, run_id: str) -> None:
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=actor_id,
        action=AUDIT_ACTION_DRY_RUN_STARTED,
        resource_type=RESOURCE_TYPE_WORKFLOW_RUN,
        resource_id=run_id,
        metadata={"run_type": "dry_run"},
    )


def emit_dry_run_step_completed(
    client: Client,
    org_id: str,
    actor_id: str,
    run_id: str,
    step_index: int,
    step_id: str,
) -> None:
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=actor_id,
        action=AUDIT_ACTION_DRY_RUN_STEP_COMPLETED,
        resource_type=RESOURCE_TYPE_WORKFLOW_RUN,
        resource_id=run_id,
        metadata={"step_index": step_index, "step_id": step_id, "status": "completed"},
    )


def emit_dry_run_step_failed(
    client: Client,
    org_id: str,
    actor_id: str,
    run_id: str,
    step_index: int,
    step_id: str,
    error_code: str,
) -> None:
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=actor_id,
        action=AUDIT_ACTION_DRY_RUN_STEP_FAILED,
        resource_type=RESOURCE_TYPE_WORKFLOW_RUN,
        resource_id=run_id,
        metadata={"step_index": step_index, "step_id": step_id, "error_code": error_code},
    )


def emit_dry_run_completed(
    client: Client,
    org_id: str,
    actor_id: str,
    run_id: str,
    status: str,
) -> None:
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=actor_id,
        action=AUDIT_ACTION_DRY_RUN_COMPLETED,
        resource_type=RESOURCE_TYPE_WORKFLOW_RUN,
        resource_id=run_id,
        metadata={"status": status},
    )


# --- BE-20 Execute audit helpers ---


def emit_execute_created(
    client: Client,
    org_id: str,
    actor_id: str,
    run_id: str,
    workflow_id: str,
) -> None:
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=actor_id,
        action=AUDIT_ACTION_EXECUTE_CREATED,
        resource_type=RESOURCE_TYPE_WORKFLOW_RUN,
        resource_id=run_id,
        metadata={"workflow_id": workflow_id},
    )


def emit_execute_pending_approval(
    client: Client,
    org_id: str,
    actor_id: str,
    run_id: str,
    workflow_id: str,
) -> None:
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=actor_id,
        action=AUDIT_ACTION_EXECUTE_PENDING_APPROVAL,
        resource_type=RESOURCE_TYPE_WORKFLOW_RUN,
        resource_id=run_id,
        metadata={"workflow_id": workflow_id},
    )


def emit_execute_approval_recorded(
    client: Client,
    org_id: str,
    actor_id: str,
    run_id: str,
    approval_status: str,
) -> None:
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=actor_id,
        action=AUDIT_ACTION_EXECUTE_APPROVAL_RECORDED,
        resource_type=RESOURCE_TYPE_WORKFLOW_RUN,
        resource_id=run_id,
        metadata={"approval_status": approval_status},
    )


def emit_execute_approved(
    client: Client,
    org_id: str,
    actor_id: str,
    run_id: str,
) -> None:
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=actor_id,
        action=AUDIT_ACTION_EXECUTE_APPROVED,
        resource_type=RESOURCE_TYPE_WORKFLOW_RUN,
        resource_id=run_id,
        metadata=None,
    )


def emit_execute_rejected(
    client: Client,
    org_id: str,
    actor_id: str,
    run_id: str,
) -> None:
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=actor_id,
        action=AUDIT_ACTION_EXECUTE_REJECTED,
        resource_type=RESOURCE_TYPE_WORKFLOW_RUN,
        resource_id=run_id,
        metadata=None,
    )


def emit_execute_started(
    client: Client,
    org_id: str,
    actor_id: str,
    run_id: str,
) -> None:
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=actor_id,
        action=AUDIT_ACTION_EXECUTE_STARTED,
        resource_type=RESOURCE_TYPE_WORKFLOW_RUN,
        resource_id=run_id,
        metadata=None,
    )


def emit_execute_step_completed(
    client: Client,
    org_id: str,
    actor_id: str,
    run_id: str,
    step_index: int,
    step_id: str,
) -> None:
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=actor_id,
        action=AUDIT_ACTION_EXECUTE_STEP_COMPLETED,
        resource_type=RESOURCE_TYPE_WORKFLOW_RUN,
        resource_id=run_id,
        metadata={"step_index": step_index, "step_id": step_id},
    )


def emit_execute_step_failed(
    client: Client,
    org_id: str,
    actor_id: str,
    run_id: str,
    step_index: int,
    step_id: str,
    error_code: str,
) -> None:
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=actor_id,
        action=AUDIT_ACTION_EXECUTE_STEP_FAILED,
        resource_type=RESOURCE_TYPE_WORKFLOW_RUN,
        resource_id=run_id,
        metadata={"step_index": step_index, "step_id": step_id, "error_code": error_code},
    )


def emit_execute_completed(
    client: Client,
    org_id: str,
    actor_id: str,
    run_id: str,
    status: str,
) -> None:
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=actor_id,
        action=AUDIT_ACTION_EXECUTE_COMPLETED,
        resource_type=RESOURCE_TYPE_WORKFLOW_RUN,
        resource_id=run_id,
        metadata={"status": status},
    )


def emit_execute_failed(
    client: Client,
    org_id: str,
    actor_id: str,
    run_id: str,
    error_message: str | None = None,
) -> None:
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=actor_id,
        action=AUDIT_ACTION_EXECUTE_FAILED,
        resource_type=RESOURCE_TYPE_WORKFLOW_RUN,
        resource_id=run_id,
        metadata={"error_message": (error_message or "")[:200]},
    )


def emit_execute_cancelled(
    client: Client,
    org_id: str,
    actor_id: str,
    run_id: str,
) -> None:
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=actor_id,
        action=AUDIT_ACTION_EXECUTE_CANCELLED,
        resource_type=RESOURCE_TYPE_WORKFLOW_RUN,
        resource_id=run_id,
        metadata=None,
    )
