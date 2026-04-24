from __future__ import annotations

from typing import Any

from supabase import Client

from app.audit.query import query_audit_events
from app.config import Settings
from app.connectors.repository import get_connector
from app.rag.ingest import get_source
from app.workflows.repository import (
    get_active_workflow_version,
    get_approval_counts,
    get_run_with_steps,
    get_workflow_def,
    list_workflow_versions,
)


CONNECTOR_STEP_TYPE_MAP = {
    "slack_post_message": "slack",
    "email_send": "email",
    "webhook_post": "webhook",
}


def _safe_config_keys(config: dict | None) -> list[str]:
    if not isinstance(config, dict):
        return []
    return sorted([str(k) for k in config.keys()])


def _recent_runs(client: Client, org_id: str, environment: str, limit: int = 5, workflow_id: str | None = None) -> list[dict]:
    q = (
        client.table("workflow_runs")
        .select("id, status, created_at, workflow_id")
        .eq("org_id", org_id)
        .eq("environment", environment)
        .order("created_at", desc=True)
        .limit(limit)
    )
    if workflow_id:
        q = q.eq("workflow_id", workflow_id)
    r = q.execute()
    return list(r.data or [])


def _recent_workflow_defs(client: Client, org_id: str, limit: int = 20) -> list[dict]:
    r = (
        client.table("workflow_defs")
        .select("id, name, definition, updated_at")
        .eq("org_id", org_id)
        .order("updated_at", desc=True)
        .limit(limit)
        .execute()
    )
    return list(r.data or [])


def build_run_context(
    client: Client,
    settings: Settings,
    org_id: str,
    environment: str,
    run_id: str,
) -> dict | None:
    run = get_run_with_steps(client, org_id, run_id, environment_name=environment)
    if not run:
        return None
    steps = list(run.get("steps") or [])
    required = int(run.get("required_approvals") or 0)
    approvals_received, _ = get_approval_counts(client, run_id)
    approval_required = required > 0
    events, _ = query_audit_events(
        settings=settings,
        org_id=org_id,
        resource_type="workflow_run",
        resource_id=run_id,
        limit=5,
        cursor=None,
        action_prefix=None,
    )
    recent_runs = _recent_runs(client, org_id, environment, limit=5)
    return {
        "run": {
            "id": str(run["id"]),
            "workflow_id": str(run["workflow_id"]) if run.get("workflow_id") else None,
            "status": run.get("status") or "",
            "approval_status": run.get("approval_status"),
            "approval_required": approval_required,
            "required_approvals": required,
            "approvals_received": approvals_received,
            "created_at": run.get("created_at"),
            "environment": environment,
        },
        "steps": [
            {
                "step_index": int(step.get("step_index") or 0),
                "step_name": step.get("step_name") or "",
                "step_type": step.get("step_type") or "",
                "status": step.get("status") or "",
                "error_code": step.get("error_code"),
            }
            for step in steps
        ],
        "recent_runs": [
            {
                "id": str(r["id"]),
                "status": r.get("status") or "",
                "created_at": r.get("created_at"),
                "workflow_id": str(r["workflow_id"]) if r.get("workflow_id") else None,
            }
            for r in recent_runs
            if str(r.get("id")) != run_id
        ],
        "audit": {
            "total_events": len(events),
            "recent_events": [
                {"action": ev.get("action") or "", "created_at": ev.get("created_at") or ""}
                for ev in events
            ],
        },
    }


def build_workflow_context(
    client: Client,
    org_id: str,
    environment: str,
    workflow_id: str,
) -> dict | None:
    wf = get_workflow_def(client, org_id, workflow_id)
    if not wf:
        return None
    active = get_active_workflow_version(client, org_id, workflow_id, environment)
    versions = list_workflow_versions(client, org_id, workflow_id, environment)
    recent_runs = _recent_runs(client, org_id, environment, limit=5, workflow_id=workflow_id)
    step_types = []
    definition = (active or {}).get("definition") or wf.get("definition") or {}
    for step in definition.get("steps") or []:
        step_type = (step.get("type") or "").strip()
        if step_type:
            step_types.append(step_type)
    connector_refs: dict[str, set[str]] = {}
    for stype in step_types:
        connector = CONNECTOR_STEP_TYPE_MAP.get(stype)
        if not connector:
            continue
        connector_refs.setdefault(connector, set()).add(stype)
    return {
        "workflow": {
            "id": str(wf["id"]),
            "name": wf.get("name") or "",
            "description": wf.get("description"),
            "schema_version": wf.get("schema_version"),
            "updated_at": wf.get("updated_at"),
        },
        "active_version": (
            {
                "id": str(active["id"]),
                "version": int(active.get("version") or 0),
                "created_at": active.get("created_at"),
            }
            if active
            else None
        ),
        "recent_versions": [
            {
                "id": str(v["id"]),
                "version": int(v.get("version") or 0),
                "created_at": v.get("created_at"),
            }
            for v in list(versions or [])[:5]
        ],
        "recent_runs": [
            {
                "id": str(r["id"]),
                "status": r.get("status") or "",
                "created_at": r.get("created_at"),
                "workflow_id": str(r["workflow_id"]) if r.get("workflow_id") else None,
            }
            for r in recent_runs
        ],
        "linked_connectors": [
            {"type": key, "step_types": sorted(list(types))}
            for key, types in connector_refs.items()
        ],
    }


def build_connector_context(
    client: Client,
    org_id: str,
    environment: str,
    connector_id: str,
) -> dict | None:
    connector = get_connector(client, org_id, connector_id, environment_name=environment)
    if not connector:
        return None
    config_keys = _safe_config_keys(connector.get("config"))
    related: list[dict[str, Any]] = []
    target_step_type = None
    connector_type = (connector.get("type") or "").strip()
    for step_type, conn_type in CONNECTOR_STEP_TYPE_MAP.items():
        if conn_type == connector_type:
            target_step_type = step_type
            break
    if target_step_type:
        workflows = _recent_workflow_defs(client, org_id, limit=20)
        for wf in workflows:
            definition = wf.get("definition") or {}
            steps = definition.get("steps") or []
            if any((s.get("type") or "").strip() == target_step_type for s in steps):
                related.append({"id": str(wf["id"]), "name": wf.get("name") or ""})
            if len(related) >= 5:
                break
    return {
        "connector": {
            "id": str(connector["id"]),
            "type": connector.get("type") or "",
            "status": connector.get("status") or "",
            "updated_at": connector.get("updated_at"),
            "environment": connector.get("environment", environment),
        },
        "config_summary": {"keys": config_keys, "field_count": len(config_keys)},
        "related_workflows": related,
    }


def build_source_context(
    client: Client,
    org_id: str,
    environment: str,
    source_id: str,
) -> dict | None:
    source = get_source(client, org_id, source_id, environment_name=environment)
    if not source:
        return None
    docs = (
        client.table("rag_documents")
        .select("id, title, external_id, updated_at")
        .eq("org_id", org_id)
        .eq("source_id", source_id)
        .eq("is_active", True)
        .eq("environment", environment)
        .order("updated_at", desc=True)
        .limit(5)
        .execute()
    )
    ingest_jobs = (
        client.table("rag_ingest_jobs")
        .select("id, status, created_at, updated_at, error_code")
        .eq("org_id", org_id)
        .eq("source_id", source_id)
        .eq("environment", environment)
        .order("created_at", desc=True)
        .limit(3)
        .execute()
    )
    return {
        "source": {
            "id": str(source["id"]),
            "title": source.get("title") or "",
            "type": source.get("type") or "",
            "updated_at": source.get("updated_at"),
            "environment": source.get("environment", environment),
        },
        "recent_documents": [
            {
                "id": str(doc["id"]),
                "title": doc.get("title"),
                "external_id": doc.get("external_id"),
                "updated_at": doc.get("updated_at"),
            }
            for doc in list(docs.data or [])
        ],
        "ingest_jobs": [
            {
                "id": str(job["id"]),
                "status": job.get("status") or "",
                "created_at": job.get("created_at"),
                "updated_at": job.get("updated_at"),
                "error_code": job.get("error_code"),
            }
            for job in list(ingest_jobs.data or [])
        ],
    }
