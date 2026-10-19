"""Phase 15: Environments API."""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from supabase import create_client
from app.core.db import shared_service_client

from app.auth.dependencies import get_current_user, get_org_context, require_admin
from app.config import Settings, get_settings
from app.workflows.audit import write_audit_event
from app.billing.service import get_plan_for_org, require_limit
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/environments", tags=["environments"])


class EnvironmentCreateRequest(BaseModel):
    name: str = Field(..., min_length=1)


class EnvironmentUpdateRequest(BaseModel):
    is_active: bool | None = Field(default=None, alias="isActive")


_ALLOWED_ENVIRONMENT_NAMES = frozenset({"production", "staging", "development"})


_STAGE_ORDER = ("development", "staging", "production")
# Legacy orgs (phase 7 migration) may only have a "default" row; it plays the production role.
_DEFAULT_NAMES = frozenset({"production", "default"})


def _count_rows(client, table: str, org_id: str, column: str, value: str, *, soft_delete: bool) -> int | None:
    """Exact row count scoped to one environment, or None when the table cannot be counted."""
    try:
        query = (
            client.table(table)
            .select("id", count="exact", head=True)
            .eq("org_id", org_id)
            .eq(column, value)
        )
        if soft_delete:
            query = query.is_("deleted_at", "null")
        response = query.execute()
    except Exception as exc:  # noqa: BLE001 — a missing column/table means "not reported"
        logger.debug("environment count failed table=%s column=%s: %s", table, column, exc)
        return None
    count = getattr(response, "count", None)
    return int(count) if isinstance(count, int) else None


def _environment_resources(client, org_id: str, env: dict) -> dict:
    env_id = str(env.get("id") or "")
    name = str(env.get("name") or "").strip().lower()
    return {
        # workflow_defs / operators link by environment_id (phase 15 columns).
        "workflows": _count_rows(client, "workflow_defs", org_id, "environment_id", env_id, soft_delete=False)
        if env_id
        else None,
        "agents": _count_rows(client, "operators", org_id, "environment_id", env_id, soft_delete=True)
        if env_id
        else None,
        # connectors / rag_sources carry the environment name (phase 7 columns).
        "connectors": _count_rows(client, "connectors", org_id, "environment", name, soft_delete=True)
        if name
        else None,
        "sources": _count_rows(client, "rag_sources", org_id, "environment", name, soft_delete=True)
        if name
        else None,
    }


def _shape_environment(client, org_id: str, env: dict, *, default_id: str | None) -> dict:
    name = str(env.get("name") or "").strip().lower()
    return {
        "id": env.get("id"),
        "name": name,
        "slug": name,
        "is_active": env.get("is_active") is not False,
        "is_default": bool(default_id) and str(env.get("id")) == default_id,
        "created_at": env.get("created_at"),
        "resources": _environment_resources(client, org_id, env),
    }


def _default_environment_id(rows: list[dict]) -> str | None:
    by_name = {str(row.get("name") or "").strip().lower(): row for row in rows}
    for name in ("production", "default"):
        row = by_name.get(name)
        if row and row.get("id"):
            return str(row["id"])
    return None


@router.get("")
def list_environments(
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    client = shared_service_client(settings, create_client)
    from app.services.org_membership import ensure_default_production_environment

    ensure_default_production_environment(client, org_id)
    r = client.table("environments").select("id, name, is_active, created_at").eq("org_id", org_id).execute()
    rows = [row for row in (r.data or []) if isinstance(row, dict)]
    default_id = _default_environment_id(rows)
    environments = [_shape_environment(client, org_id, row, default_id=default_id) for row in rows]
    order = {name: index for index, name in enumerate(_STAGE_ORDER)}
    environments.sort(key=lambda env: order.get("production" if env["name"] == "default" else env["name"], 99))
    limit: int | None = None
    try:
        raw_limit = get_plan_for_org(client, org_id).get("environments_limit")
        limit = int(raw_limit) if raw_limit is not None else None
    except Exception as exc:  # noqa: BLE001 — the limit is advisory; create still enforces it
        logger.debug("environments plan limit lookup failed: %s", exc)
    return {"environments": environments, "stages": list(_STAGE_ORDER), "environmentsLimit": limit}


@router.post("", status_code=status.HTTP_201_CREATED)
def create_environment(
    body: EnvironmentCreateRequest,
    _admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    _user, org_id = _admin
    name = body.name.strip().lower()
    if name not in _ALLOWED_ENVIRONMENT_NAMES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid environment name (use production, staging, or development)",
        )
    client = shared_service_client(settings, create_client)
    existing = client.table("environments").select("id, name").eq("org_id", org_id).execute()
    existing_names = {
        str(row.get("name") or "").strip().lower() for row in (existing.data or []) if isinstance(row, dict)
    }
    if name in existing_names or (name == "production" and "default" in existing_names):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"The {name} environment already exists",
        )
    plan = get_plan_for_org(client, org_id)
    count = client.table("environments").select("id", count="exact").eq("org_id", org_id).execute()
    current = count.count or 0 if hasattr(count, "count") else len(count.data or [])
    require_limit(current, plan.get("environments_limit"), "environments")
    r = client.table("environments").insert({"org_id": org_id, "name": name, "is_active": True}).execute()
    if not r.data:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Environment create failed")
    env_id = str(r.data[0]["id"])
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=_user["user_id"],
        action="environment.created",
        resource_type="environment",
        resource_id=env_id,
        metadata={"name": name},
    )
    return {"id": env_id, "name": name}


@router.patch("/{env_id}")
def update_environment(
    env_id: UUID,
    body: EnvironmentUpdateRequest,
    _admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    _user, org_id = _admin
    payload: dict = {}
    if body.is_active is not None:
        payload["is_active"] = body.is_active
    if not payload:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No changes provided")
    client = shared_service_client(settings, create_client)
    updated = client.table("environments").update(payload).eq("org_id", org_id).eq("id", str(env_id)).execute()
    if not updated.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Environment not found")
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=_user["user_id"],
        action="environment.updated",
        resource_type="environment",
        resource_id=str(env_id),
        metadata={"fields": list(payload.keys())},
    )
    return {"id": str(env_id), **payload}


@router.delete("/{env_id}")
def delete_environment(
    env_id: UUID,
    _admin: Annotated[tuple, Depends(require_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """Remove a non-default environment. Linked workflows/agents keep running (FKs set null)."""
    _user, org_id = _admin
    client = shared_service_client(settings, create_client)
    found = (
        client.table("environments")
        .select("id, name")
        .eq("org_id", org_id)
        .eq("id", str(env_id))
        .limit(1)
        .execute()
    )
    rows = [row for row in (found.data or []) if isinstance(row, dict)]
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Environment not found")
    name = str(rows[0].get("name") or "").strip().lower()
    if name in _DEFAULT_NAMES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The production environment cannot be deleted",
        )
    client.table("environments").delete().eq("org_id", org_id).eq("id", str(env_id)).execute()
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=_user["user_id"],
        action="environment.deleted",
        resource_type="environment",
        resource_id=str(env_id),
        metadata={"name": name},
    )
    return {"id": str(env_id), "deleted": True}
