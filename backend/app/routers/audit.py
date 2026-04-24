"""BE-12: Read-only audit query API. GET /api/audit; auth + org required."""
import time
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from supabase import create_client

from app.auth.dependencies import get_current_user, get_org_context
from app.config import Settings, get_settings
from app.core.logging import get_logger, request_id_ctx
from app.core.errors import error_detail
from app.billing.service import get_plan_for_org, require_feature

logger = get_logger(__name__)

router = APIRouter(prefix="/api/audit", tags=["audit"])

LIMIT_DEFAULT = 50
LIMIT_MAX = 200


@router.get("")
async def get_audit(
    date_from: Annotated[str | None, Query(alias="dateFrom")] = None,
    date_to: Annotated[str | None, Query(alias="dateTo")] = None,
    action: Annotated[str | None, Query(alias="action")] = None,
    actor: Annotated[str | None, Query(alias="actor")] = None,
    resource_type: Annotated[str | None, Query(min_length=1, alias="resourceType")] = None,
    environment: Annotated[str | None, Query(alias="environment")] = None,
    page: Annotated[int | None, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=LIMIT_MAX)] = LIMIT_DEFAULT,
    _user: Annotated[dict, Depends(get_current_user)] = None,
    org_id: Annotated[str | None, Depends(get_org_context)] = None,
    settings: Annotated[Settings, Depends(get_settings)] = None,
):
    """Query audit log with filters. Org-scoped."""
    if org_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=error_detail("Organization context required", "UNAUTHORIZED"),
        )
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    require_feature(get_plan_for_org(client, org_id), "audit_logs")
    start = time.perf_counter()
    offset = ((page or 1) - 1) * limit
    q = (
        client.table("audit_logs")
        .select("id, timestamp, action, action_label, actor, resource, resource_type, severity, details")
        .eq("org_id", org_id)
        .order("timestamp", desc=True)
    )
    if action:
        q = q.eq("action", action)
    if actor:
        q = q.eq("actor", actor)
    if resource_type:
        q = q.eq("resource_type", resource_type)
    if date_from:
        q = q.gte("timestamp", date_from)
    if date_to:
        q = q.lte("timestamp", date_to)
    rows = q.range(offset, offset + limit - 1).execute().data or []
    count_q = client.table("audit_logs").select("id", count="exact").eq("org_id", org_id)
    if action:
        count_q = count_q.eq("action", action)
    if actor:
        count_q = count_q.eq("actor", actor)
    if resource_type:
        count_q = count_q.eq("resource_type", resource_type)
    if date_from:
        count_q = count_q.gte("timestamp", date_from)
    if date_to:
        count_q = count_q.lte("timestamp", date_to)
    count_result = count_q.execute()
    total = count_result.count or 0 if hasattr(count_result, "count") else 0
    events = []
    for it in rows:
        details = it.get("details") or {}
        env_value = details.get("environment") if isinstance(details, dict) else None
        if environment and env_value and env_value != environment:
            continue
        events.append(
            {
                "id": str(it["id"]),
                "timestamp": it["timestamp"],
                "action": it["action"],
                "actionLabel": it.get("action_label") or "",
                "actor": it.get("actor"),
                "resource": it.get("resource"),
                "resourceType": it.get("resource_type"),
                "environment": env_value,
                "severity": it.get("severity") or "info",
                "details": details,
            }
        )
    latency_ms = int((time.perf_counter() - start) * 1000)
    logger.info(
        "audit_query request_id=%s org_id=%s item_count=%s latency_ms=%s",
        request_id_ctx.get(),
        org_id,
        len(events),
        latency_ms,
        extra={
            "request_id": request_id_ctx.get(),
            "org_id": org_id,
            "item_count": len(events),
            "latency_ms": latency_ms,
        },
    )
    return {"events": events, "total": total}
