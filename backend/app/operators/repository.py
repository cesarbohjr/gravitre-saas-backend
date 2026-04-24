from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from supabase import Client


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def list_operators(client: Client, org_id: str) -> list[dict]:
    r = (
        client.table("operators")
        .select(
            "id, org_id, name, description, status, system_prompt, allowed_environments, "
            "requires_admin, requires_approval, approval_roles, role, capabilities, config, "
            "active_version_id, environment_id, total_runs, success_rate, avg_duration, icon, avatar_color, "
            "created_at, updated_at"
        )
        .eq("org_id", org_id)
        .is_("deleted_at", "null")
        .order("created_at", desc=True)
        .execute()
    )
    return list(r.data or [])


def get_operator(client: Client, org_id: str, operator_id: str) -> dict | None:
    r = (
        client.table("operators")
        .select(
            "id, org_id, name, description, status, system_prompt, allowed_environments, "
            "requires_admin, requires_approval, approval_roles, role, capabilities, config, "
            "active_version_id, environment_id, total_runs, success_rate, avg_duration, icon, avatar_color, "
            "created_at, updated_at"
        )
        .eq("org_id", org_id)
        .eq("id", operator_id)
        .is_("deleted_at", "null")
        .limit(1)
        .execute()
    )
    if not r.data:
        return None
    return dict(r.data[0])


def create_operator(
    client: Client,
    org_id: str,
    payload: dict,
    created_by: str | None,
) -> dict:
    row = {
        "org_id": org_id,
        "name": payload["name"],
        "description": payload.get("description"),
        "status": payload.get("status") or "draft",
        "system_prompt": payload.get("system_prompt"),
        "role": payload.get("role"),
        "capabilities": payload.get("capabilities") or [],
        "config": payload.get("config") or {},
        "allowed_environments": payload.get("allowed_environments") or [],
        "requires_admin": bool(payload.get("requires_admin")),
        "requires_approval": bool(payload.get("requires_approval")),
        "approval_roles": payload.get("approval_roles") or [],
        "created_by": created_by,
    }
    if payload.get("environment_id"):
        row["environment_id"] = payload.get("environment_id")
    if payload.get("icon") is not None:
        row["icon"] = payload.get("icon")
    if payload.get("avatar_color") is not None:
        row["avatar_color"] = payload.get("avatar_color")
    r = client.table("operators").insert(row).execute()
    if not r.data:
        raise RuntimeError("operators insert returned no row")
    return dict(r.data[0])


def update_operator(
    client: Client,
    org_id: str,
    operator_id: str,
    payload: dict,
) -> dict | None:
    update: dict = {"updated_at": _now_iso()}
    nullable_fields = {"icon", "avatar_color"}
    for key in (
        "name",
        "description",
        "status",
        "system_prompt",
        "role",
        "capabilities",
        "config",
        "allowed_environments",
        "requires_admin",
        "requires_approval",
        "approval_roles",
        "environment_id",
        "icon",
        "avatar_color",
    ):
        if key in payload and (payload[key] is not None or key in nullable_fields):
            update[key] = payload[key]
    if len(update.keys()) == 1:
        return get_operator(client, org_id, operator_id)
    r = (
        client.table("operators")
        .update(update)
        .eq("org_id", org_id)
        .eq("id", operator_id)
        .execute()
    )
    if not r.data:
        return None
    return dict(r.data[0])


def list_operator_bindings(
    client: Client,
    org_id: str,
    operator_ids: Iterable[str],
) -> list[dict]:
    op_ids = list(operator_ids)
    if not op_ids:
        return []
    r = (
        client.table("operator_connector_bindings")
        .select("operator_id, connector_id")
        .eq("org_id", org_id)
        .in_("operator_id", op_ids)
        .execute()
    )
    return list(r.data or [])


def list_active_versions(
    client: Client,
    org_id: str,
    operator_ids: Iterable[str],
    environment_name: str,
) -> list[dict]:
    op_ids = list(operator_ids)
    if not op_ids:
        return []
    r = (
        client.table("operator_active_versions")
        .select("operator_id, active_version_id, environment, updated_at")
        .eq("org_id", org_id)
        .eq("environment", environment_name)
        .in_("operator_id", op_ids)
        .execute()
    )
    return list(r.data or [])


def get_next_operator_version_number(
    client: Client,
    org_id: str,
    operator_id: str,
    environment_name: str,
) -> int:
    r = (
        client.table("operator_versions")
        .select("version")
        .eq("org_id", org_id)
        .eq("operator_id", operator_id)
        .eq("environment", environment_name)
        .order("version", desc=True)
        .limit(1)
        .execute()
    )
    if not r.data:
        return 1
    return int(r.data[0].get("version") or 0) + 1


def list_operator_versions(
    client: Client,
    org_id: str,
    operator_id: str,
    environment_name: str,
) -> list[dict]:
    r = (
        client.table("operator_versions")
        .select(
            "id, operator_id, environment, version, name, description, system_prompt, "
            "allowed_environments, requires_admin, requires_approval, approval_roles, "
            "connector_ids, role, capabilities, config, created_at, created_by"
        )
        .eq("org_id", org_id)
        .eq("operator_id", operator_id)
        .eq("environment", environment_name)
        .order("version", desc=True)
        .execute()
    )
    return list(r.data or [])


def list_operator_versions_by_ids(
    client: Client,
    org_id: str,
    version_ids: list[str],
) -> list[dict]:
    if not version_ids:
        return []
    r = (
        client.table("operator_versions")
        .select("id, operator_id, environment, version, name, description, role, capabilities, config, created_at")
        .eq("org_id", org_id)
        .in_("id", version_ids)
        .execute()
    )
    return list(r.data or [])


def get_operator_version(
    client: Client,
    org_id: str,
    operator_id: str,
    environment_name: str,
    version_id: str,
) -> dict | None:
    r = (
        client.table("operator_versions")
        .select("*")
        .eq("org_id", org_id)
        .eq("operator_id", operator_id)
        .eq("environment", environment_name)
        .eq("id", version_id)
        .limit(1)
        .execute()
    )
    if not r.data:
        return None
    return dict(r.data[0])


def create_operator_version(
    client: Client,
    org_id: str,
    operator_id: str,
    environment_name: str,
    payload: dict,
    created_by: str | None,
) -> dict:
    version = payload["version"]
    row = {
        "org_id": org_id,
        "operator_id": operator_id,
        "environment": environment_name,
        "version": version,
        "name": payload["name"],
        "description": payload.get("description"),
        "system_prompt": payload.get("system_prompt"),
        "allowed_environments": payload.get("allowed_environments") or [],
        "requires_admin": bool(payload.get("requires_admin")),
        "requires_approval": bool(payload.get("requires_approval")),
        "approval_roles": payload.get("approval_roles") or [],
        "connector_ids": payload.get("connector_ids") or [],
        "role": payload.get("role"),
        "capabilities": payload.get("capabilities") or [],
        "config": payload.get("config") or {},
        "created_by": created_by,
    }
    r = client.table("operator_versions").insert(row).execute()
    if not r.data:
        raise RuntimeError("operator_versions insert returned no row")
    return dict(r.data[0])


def get_active_operator_version(
    client: Client,
    org_id: str,
    operator_id: str,
    environment_name: str,
) -> dict | None:
    r = (
        client.table("operator_active_versions")
        .select("active_version_id")
        .eq("org_id", org_id)
        .eq("operator_id", operator_id)
        .eq("environment", environment_name)
        .limit(1)
        .execute()
    )
    if not r.data:
        return None
    version_id = r.data[0].get("active_version_id")
    if not version_id:
        return None
    v = (
        client.table("operator_versions")
        .select("*")
        .eq("org_id", org_id)
        .eq("operator_id", operator_id)
        .eq("environment", environment_name)
        .eq("id", version_id)
        .limit(1)
        .execute()
    )
    if not v.data:
        return None
    return dict(v.data[0])


def set_active_operator_version(
    client: Client,
    org_id: str,
    operator_id: str,
    environment_name: str,
    version_id: str,
    updated_by: str | None,
) -> None:
    row = {
        "org_id": org_id,
        "operator_id": operator_id,
        "environment": environment_name,
        "active_version_id": version_id,
        "updated_at": _now_iso(),
        "updated_by": updated_by,
    }
    client.table("operator_active_versions").upsert(
        row, on_conflict="org_id,operator_id,environment"
    ).execute()


def set_operator_connectors(
    client: Client,
    org_id: str,
    operator_id: str,
    connector_ids: list[str],
) -> None:
    client.table("operator_connector_bindings").delete().eq("org_id", org_id).eq("operator_id", operator_id).execute()
    if not connector_ids:
        return
    rows = [
        {"org_id": org_id, "operator_id": operator_id, "connector_id": connector_id}
        for connector_id in connector_ids
    ]
    client.table("operator_connector_bindings").insert(rows).execute()


def list_connectors_by_ids(
    client: Client,
    org_id: str,
    connector_ids: list[str],
    environment_name: str,
) -> list[dict]:
    if not connector_ids:
        return []
    r = (
        client.table("connectors")
        .select("id, name, vendor, type, status, config, environment, updated_at")
        .eq("org_id", org_id)
        .eq("environment", environment_name)
        .in_("id", connector_ids)
        .execute()
    )
    return list(r.data or [])


def list_operator_sessions(
    client: Client,
    org_id: str,
    operator_id: str,
    environment_name: str,
    created_by: str | None = None,
) -> list[dict]:
    q = (
        client.table("operator_sessions")
        .select("id, operator_id, operator_version_id, title, status, environment, current_task, created_at, updated_at, created_by")
        .eq("org_id", org_id)
        .eq("operator_id", operator_id)
        .eq("environment", environment_name)
        .order("updated_at", desc=True)
    )
    if created_by:
        q = q.eq("created_by", created_by)
    r = q.execute()
    return list(r.data or [])


def list_sessions_for_user(
    client: Client,
    org_id: str,
    environment_name: str,
    created_by: str | None = None,
) -> list[dict]:
    q = (
        client.table("operator_sessions")
        .select(
            "id, operator_id, operator_version_id, title, status, environment, current_task, "
            "context_entity_type, context_entity_id, created_at, updated_at, created_by"
        )
        .eq("org_id", org_id)
        .eq("environment", environment_name)
        .order("updated_at", desc=True)
    )
    if created_by:
        q = q.eq("created_by", created_by)
    r = q.execute()
    return list(r.data or [])


def create_operator_session(
    client: Client,
    org_id: str,
    operator_id: str,
    environment_name: str,
    operator_version_id: str,
    title: str,
    current_task: str | None,
    context_entity_type: str | None,
    context_entity_id: str | None,
    created_by: str | None,
) -> dict:
    row = {
        "org_id": org_id,
        "operator_id": operator_id,
        "operator_version_id": operator_version_id,
        "environment": environment_name,
        "title": title,
        "status": "planning",
        "current_task": current_task,
        "context_entity_type": context_entity_type,
        "context_entity_id": context_entity_id,
        "created_by": created_by,
    }
    r = client.table("operator_sessions").insert(row).execute()
    if not r.data:
        raise RuntimeError("operator_sessions insert returned no row")
    return dict(r.data[0])


def get_operator_session(client: Client, org_id: str, session_id: str) -> dict | None:
    r = (
        client.table("operator_sessions")
        .select("id, operator_id, operator_version_id, title, status, environment, current_task, created_at, updated_at, created_by")
        .eq("org_id", org_id)
        .eq("id", session_id)
        .limit(1)
        .execute()
    )
    if not r.data:
        return None
    return dict(r.data[0])


def update_operator_session_status(
    client: Client,
    org_id: str,
    session_id: str,
    status: str,
) -> None:
    client.table("operator_sessions").update(
        {"status": status, "updated_at": _now_iso()}
    ).eq("org_id", org_id).eq("id", session_id).execute()


def create_operator_action_plan(
    client: Client,
    org_id: str,
    operator_id: str,
    session_id: str,
    operator_version_id: str,
    environment_name: str,
    title: str,
    summary: str,
    prompt: str | None,
    primary_context: dict,
    related_contexts: list[dict],
    steps: list[dict],
    guardrails: dict,
    created_by: str | None,
) -> dict:
    row = {
        "org_id": org_id,
        "operator_id": operator_id,
        "session_id": session_id,
        "operator_version_id": operator_version_id,
        "environment": environment_name,
        "title": title,
        "summary": summary,
        "prompt": prompt,
        "primary_context": primary_context,
        "related_contexts": related_contexts,
        "steps": steps,
        "guardrails": guardrails,
        "status": "draft",
        "created_by": created_by,
    }
    r = client.table("operator_action_plans").insert(row).execute()
    if not r.data:
        raise RuntimeError("operator_action_plans insert returned no row")
    return dict(r.data[0])


def get_latest_action_plan(client: Client, org_id: str, session_id: str) -> dict | None:
    r = (
        client.table("operator_action_plans")
        .select("*")
        .eq("org_id", org_id)
        .eq("session_id", session_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    if not r.data:
        return None
    return dict(r.data[0])


def update_action_plan_status(
    client: Client,
    org_id: str,
    plan_id: str,
    status: str,
) -> None:
    client.table("operator_action_plans").update(
        {"status": status, "updated_at": _now_iso()}
    ).eq("org_id", org_id).eq("id", plan_id).execute()


def list_operator_actions(client: Client, org_id: str, session_id: str) -> list[dict]:
    r = (
        client.table("operator_actions")
        .select("*")
        .eq("org_id", org_id)
        .eq("session_id", session_id)
        .order("created_at", desc=True)
        .execute()
    )
    return list(r.data or [])


def create_operator_action(
    client: Client,
    org_id: str,
    operator_id: str,
    session_id: str,
    plan_id: str,
    operator_version_id: str,
    step_id: str,
    action_type: str,
    status: str,
    workflow_run_id: str | None,
    created_by: str | None,
) -> dict:
    row = {
        "org_id": org_id,
        "operator_id": operator_id,
        "session_id": session_id,
        "plan_id": plan_id,
        "operator_version_id": operator_version_id,
        "step_id": step_id,
        "action_type": action_type,
        "status": status,
        "workflow_run_id": workflow_run_id,
        "created_by": created_by,
    }
    r = client.table("operator_actions").insert(row).execute()
    if not r.data:
        raise RuntimeError("operator_actions insert returned no row")
    return dict(r.data[0])


def list_operator_links(
    client: Client,
    org_id: str,
    operator_id: str,
    environment_name: str,
    direction: str = "outgoing",
) -> list[dict]:
    if direction == "incoming":
        r = (
            client.table("operator_links")
            .select(
                "id, from_operator_id, to_operator_id, environment, link_type, task, notes, created_by, created_at"
            )
            .eq("org_id", org_id)
            .eq("environment", environment_name)
            .eq("to_operator_id", operator_id)
            .order("created_at", desc=True)
            .execute()
        )
        return list(r.data or [])
    if direction == "all":
        outgoing = list_operator_links(client, org_id, operator_id, environment_name, "outgoing")
        incoming = list_operator_links(client, org_id, operator_id, environment_name, "incoming")
        return outgoing + incoming
    r = (
        client.table("operator_links")
        .select(
            "id, from_operator_id, to_operator_id, environment, link_type, task, notes, created_by, created_at"
        )
        .eq("org_id", org_id)
        .eq("environment", environment_name)
        .eq("from_operator_id", operator_id)
        .order("created_at", desc=True)
        .execute()
    )
    return list(r.data or [])


def create_operator_link(
    client: Client,
    org_id: str,
    environment_name: str,
    from_operator_id: str,
    to_operator_id: str,
    link_type: str,
    task: str | None,
    notes: str | None,
    created_by: str | None,
) -> dict:
    row = {
        "org_id": org_id,
        "environment": environment_name,
        "from_operator_id": from_operator_id,
        "to_operator_id": to_operator_id,
        "link_type": link_type,
        "task": task,
        "notes": notes,
        "created_by": created_by,
    }
    r = client.table("operator_links").insert(row).execute()
    if not r.data:
        raise RuntimeError("operator_links insert returned no row")
    return dict(r.data[0])


def delete_operator_link(client: Client, org_id: str, link_id: str) -> bool:
    r = (
        client.table("operator_links")
        .delete()
        .eq("org_id", org_id)
        .eq("id", link_id)
        .execute()
    )
    return bool(r.data)
