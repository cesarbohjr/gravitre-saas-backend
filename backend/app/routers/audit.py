"""Audit API with listing, summary, detail, and export."""
from __future__ import annotations

import csv
import io
import time
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse, Response
from supabase import create_client

from app.auth.dependencies import get_current_user, get_org_context
from app.billing.service import get_plan_for_org, require_feature
from app.config import Settings, get_settings
from app.core.errors import error_detail
from app.core.logging import get_logger, request_id_ctx

logger = get_logger(__name__)

router = APIRouter(prefix="/api/audit", tags=["audit"])

LIMIT_DEFAULT = 50
LIMIT_MAX = 200
FETCH_MAX = 2000


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if normalized.endswith("Z"):
        normalized = normalized.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _range_start(range_value: str | None) -> datetime | None:
    if not range_value:
        return None
    now = datetime.now(timezone.utc)
    if range_value == "24h":
        return now - timedelta(hours=24)
    if range_value == "7d":
        return now - timedelta(days=7)
    if range_value == "30d":
        return now - timedelta(days=30)
    return None


def _to_iso_or_none(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def _normalize_log(row: dict) -> dict:
    details = row.get("details")
    if not isinstance(details, dict):
        details = {}

    created_at = row.get("created_at") or row.get("timestamp")
    entity_type = row.get("entity_type") or row.get("resource_type") or "unknown"
    entity_id = row.get("entity_id") or row.get("resource_id") or row.get("id") or ""
    actor = row.get("actor")
    user_name = row.get("user_name") or actor
    user_email = row.get("user_email")
    if not user_email and isinstance(actor, str) and "@" in actor:
        user_email = actor

    return {
        "id": str(row.get("id") or ""),
        "user_id": row.get("user_id") or row.get("actor_id"),
        "user_name": user_name,
        "user_email": user_email,
        "agent_id": row.get("agent_id") or details.get("agent_id"),
        "agent_name": row.get("agent_name") or details.get("agent_name"),
        "action": row.get("action") or "update",
        "entity_type": str(entity_type),
        "entity_id": str(entity_id),
        "entity_name": row.get("entity_name") or row.get("resource"),
        "details": details,
        "ip_address": row.get("ip_address") or details.get("ip"),
        "user_agent": row.get("user_agent"),
        "created_at": created_at,
    }


def _fetch_rows(client, org_id: str, action: str | None):
    table = client.table("audit_logs")
    query = table.select("*").eq("org_id", org_id)
    if action:
        query = query.eq("action", action)

    created_query = query.order("created_at", desc=True).range(0, FETCH_MAX - 1).execute()
    if not created_query.error:
        return list(created_query.data or [])

    timestamp_query = query.order("timestamp", desc=True).range(0, FETCH_MAX - 1).execute()
    if timestamp_query.error:
        raise HTTPException(status_code=500, detail=str(timestamp_query.error))
    return list(timestamp_query.data or [])


def _filter_logs(
    logs: list[dict],
    *,
    user_id: str | None,
    entity_type: str | None,
    from_dt: datetime | None,
    to_dt: datetime | None,
) -> list[dict]:
    filtered: list[dict] = []
    for log in logs:
        if user_id and log.get("user_id") != user_id:
            continue
        if entity_type and log.get("entity_type") != entity_type:
            continue
        created_at = _parse_iso(str(log.get("created_at") or ""))
        if from_dt and (created_at is None or created_at < from_dt):
            continue
        if to_dt and (created_at is None or created_at > to_dt):
            continue
        filtered.append(log)
    return filtered


@router.get("")
async def list_audit_logs(
    *,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
    user_id: Annotated[str | None, Query()] = None,
    entity_type: Annotated[str | None, Query()] = None,
    action: Annotated[str | None, Query()] = None,
    from_ts: Annotated[str | None, Query(alias="from")] = None,
    to_ts: Annotated[str | None, Query(alias="to")] = None,
    limit: Annotated[int, Query(ge=1, le=LIMIT_MAX)] = LIMIT_DEFAULT,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict:
    if org_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=error_detail("Organization context required", "UNAUTHORIZED"),
        )

    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    require_feature(get_plan_for_org(client, org_id), "audit_logs")
    start = time.perf_counter()

    rows = _fetch_rows(client, org_id, action)
    logs = [_normalize_log(row) for row in rows]
    logs = _filter_logs(
        logs,
        user_id=user_id,
        entity_type=entity_type,
        from_dt=_parse_iso(from_ts),
        to_dt=_parse_iso(to_ts),
    )

    total = len(logs)
    paginated = logs[offset : offset + limit]
    has_more = offset + len(paginated) < total

    latency_ms = int((time.perf_counter() - start) * 1000)
    logger.info(
        "audit_query request_id=%s org_id=%s item_count=%s latency_ms=%s",
        request_id_ctx.get(),
        org_id,
        len(paginated),
        latency_ms,
        extra={
            "request_id": request_id_ctx.get(),
            "org_id": org_id,
            "item_count": len(paginated),
            "latency_ms": latency_ms,
        },
    )
    return {"logs": paginated, "total": total, "hasMore": has_more}


@router.get("/summary")
async def audit_summary(
    *,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
    range_value: Annotated[str | None, Query(alias="range")] = None,
) -> dict:
    if org_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=error_detail("Organization context required", "UNAUTHORIZED"),
        )

    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    require_feature(get_plan_for_org(client, org_id), "audit_logs")
    rows = _fetch_rows(client, org_id, action=None)
    logs = [_normalize_log(row) for row in rows]
    from_dt = _range_start(range_value)
    logs = _filter_logs(logs, user_id=None, entity_type=None, from_dt=from_dt, to_dt=None)

    by_action: dict[str, int] = {}
    by_entity_type: dict[str, int] = {}
    by_user: dict[str, dict] = {}

    for log in logs:
        action_key = str(log.get("action") or "unknown")
        by_action[action_key] = by_action.get(action_key, 0) + 1

        entity_key = str(log.get("entity_type") or "unknown")
        by_entity_type[entity_key] = by_entity_type.get(entity_key, 0) + 1

        user_key = str(log.get("user_id") or "system")
        user_name = str(log.get("user_name") or "System")
        current = by_user.get(user_key)
        if current is None:
            by_user[user_key] = {"user_id": user_key, "user_name": user_name, "count": 1}
        else:
            current["count"] += 1

    by_user_list = sorted(by_user.values(), key=lambda item: item["count"], reverse=True)[:10]
    return {"byAction": by_action, "byUser": by_user_list, "byEntityType": by_entity_type}


@router.get("/export")
async def export_audit(
    *,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
    format: Annotated[str, Query(pattern="^(csv|json)$")] = "csv",
    from_ts: Annotated[str | None, Query(alias="from")] = None,
    to_ts: Annotated[str | None, Query(alias="to")] = None,
) -> Response:
    if org_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=error_detail("Organization context required", "UNAUTHORIZED"),
        )

    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    require_feature(get_plan_for_org(client, org_id), "audit_logs")
    rows = _fetch_rows(client, org_id, action=None)
    logs = [_normalize_log(row) for row in rows]
    logs = _filter_logs(
        logs,
        user_id=None,
        entity_type=None,
        from_dt=_parse_iso(from_ts),
        to_dt=_parse_iso(to_ts),
    )

    if format == "json":
        return JSONResponse(content={"logs": logs})

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "id",
            "created_at",
            "action",
            "user_id",
            "user_name",
            "user_email",
            "entity_type",
            "entity_id",
            "entity_name",
            "ip_address",
        ]
    )
    for log in logs:
        writer.writerow(
            [
                log.get("id"),
                log.get("created_at"),
                log.get("action"),
                log.get("user_id"),
                log.get("user_name"),
                log.get("user_email"),
                log.get("entity_type"),
                log.get("entity_id"),
                log.get("entity_name"),
                log.get("ip_address"),
            ]
        )

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="audit-export.csv"'},
    )


@router.get("/{log_id}")
async def get_audit_log(
    log_id: str,
    *,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=error_detail("Organization context required", "UNAUTHORIZED"),
        )

    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    require_feature(get_plan_for_org(client, org_id), "audit_logs")
    response = client.table("audit_logs").select("*").eq("org_id", org_id).eq("id", log_id).limit(1).execute()
    if response.error:
        raise HTTPException(status_code=500, detail=str(response.error))
    if not response.data:
        raise HTTPException(status_code=404, detail="Audit log not found")
    return _normalize_log(dict(response.data[0]))
