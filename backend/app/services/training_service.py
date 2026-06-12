"""Resilient training hub queries (schema-safe for partial prod migrations)."""
from __future__ import annotations

from typing import Any


def is_schema_unavailable_error(error: Exception | None) -> bool:
    """True when Supabase/Postgres schema is missing tables or columns."""
    if error is None:
        return False
    text = str(error).lower()
    if "column" in text and "does not exist" in text:
        return False
    markers = (
        "does not exist",
        "could not find the table",
        "schema cache",
        "pgrst205",
        "pgrst204",
        "42703",
        "42p01",
        "undefined table",
        "relation",
    )
    return any(marker in text for marker in markers)


def is_missing_column_error(error: Exception | None) -> bool:
    if error is None:
        return False
    text = str(error).lower()
    return "column" in text and "does not exist" in text


def execute_or_empty(client: Any, builder: Any, *, resource: str) -> list[dict[str, Any]]:
    """Run a select builder; return [] when schema is unavailable."""
    try:
        response = builder.execute()
    except Exception as exc:  # noqa: BLE001
        if is_schema_unavailable_error(exc):
            return []
        raise
    if is_schema_unavailable_error(getattr(response, "error", None)):
        return []
    if response.error:
        raise RuntimeError(f"{resource}: {response.error}")
    return list(response.data or [])


def list_training_datasets(client: Any, org_id: str) -> list[dict[str, Any]]:
    return execute_or_empty(
        client,
        client.table("training_datasets")
        .select("id, name, description, type, status, record_count, created_by, created_at, updated_at")
        .eq("org_id", org_id)
        .order("created_at", desc=True),
        resource="training_datasets",
    )


def list_training_jobs(client: Any, org_id: str) -> list[dict[str, Any]]:
    return execute_or_empty(
        client,
        client.table("training_jobs")
        .select("id, dataset_id, model_base, status, progress, metrics, started_at, completed_at, error, created_at")
        .eq("org_id", org_id)
        .order("created_at", desc=True),
        resource="training_jobs",
    )


def list_custom_instructions(client: Any, org_id: str) -> list[dict[str, Any]]:
    rows = execute_or_empty(
        client,
        client.table("custom_instructions")
        .select("id, agent_id, name, content, is_active, created_at, updated_at")
        .eq("org_id", org_id)
        .order("updated_at", desc=True),
        resource="custom_instructions",
    )
    agent_ids = sorted({str(row["agent_id"]) for row in rows if row.get("agent_id")})
    agent_names: dict[str, str] = {}
    if agent_ids:
        try:
            agents_resp = (
                client.table("agents")
                .select("id, name")
                .eq("org_id", org_id)
                .in_("id", agent_ids)
                .execute()
            )
            if not agents_resp.error:
                agent_names = {
                    str(row["id"]): str(row.get("name") or "Agent")
                    for row in (agents_resp.data or [])
                }
        except Exception:  # noqa: BLE001
            pass
    for row in rows:
        agent_id = row.get("agent_id")
        if agent_id:
            row["agent_name"] = agent_names.get(str(agent_id))
    return rows


def list_workflow_agents(client: Any, org_id: str) -> list[dict[str, Any]]:
    select_with_ft = "id, name, role, model, status, trained_model_id"
    select_base = "id, name, role, model, status"
    for columns in (select_with_ft, select_base):
        try:
            response = (
                client.table("agents")
                .select(columns)
                .eq("org_id", org_id)
                .order("name")
                .execute()
            )
        except Exception as exc:  # noqa: BLE001
            if is_missing_column_error(exc) and columns == select_with_ft:
                continue
            if is_schema_unavailable_error(exc):
                return []
            raise
        if is_schema_unavailable_error(getattr(response, "error", None)):
            return []
        if response.error:
            if is_missing_column_error(response.error) and columns == select_with_ft:
                continue
            if is_schema_unavailable_error(response.error):
                return []
            raise RuntimeError(str(response.error))
        return [
            {
                "id": str(row["id"]),
                "name": row.get("name"),
                "role": row.get("role"),
                "model": row.get("model"),
                "status": row.get("status"),
                "trainedModelId": row.get("trained_model_id"),
            }
            for row in (response.data or [])
        ]
    return []
