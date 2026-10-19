"""Audit API with listing, summary, detail, and export."""
from __future__ import annotations

import csv
import io
import time
from datetime import datetime, timedelta, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse, Response
from supabase import create_client
from app.core.db import shared_service_client

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


# Action groups for the Audit trail "Action" filter. Matched on the real action
# names that write_audit_event and the tool runtime record (see
# app/workflows/audit.py and app/services/tool_service.py). Order matters: the
# first matching group wins.
AUDIT_CATEGORIES = ("sync", "run", "approve", "agent", "member", "setting", "chat")

_SETTING_FIRST_PREFIXES = ("settings.", "setting.")
_CHAT_PREFIXES = ("tool.invoke", "chat.", "assistant.", "extension.chat", "write_action.")
_RUN_PREFIXES = (
    "workflow.run",
    "workflow.execute",
    "workflow.executed",
    "workflow_run",
    "play.run",
    "run.",
    "runs.",
    "schedule.run",
)
_SYNC_PREFIXES = ("source.", "sources.", "rag.", "connector.", "connectors.", "source_sync.")
_AGENT_PREFIXES = ("agent.", "agents.", "operator.", "operators.")
_MEMBER_PREFIXES = (
    "member.",
    "members.",
    "department_member.",
    "org.member",
    "organization.member",
    "org_member.",
    "invite",
    "invitation.",
    "team.",
    "user.",
    "role.",
    "lite_seat.",
    "seat.",
)
_SETTING_PREFIXES = (
    "model_policy.",
    "source_governance.",
    "hitl_policy.",
    "memory_entity_embeddings.",
    "environment.",
    "org.settings",
    "organization.updated",
    "org.updated",
    "api_key.",
    "security.",
    "sso.",
    "policy.",
)
_ERROR_SEGMENTS = frozenset(
    {"failed", "failure", "error", "errored", "timeout", "timed_out", "refused", "expired", "rejected_by_provider"}
)
_ERROR_STATUSES = frozenset({"failed", "failure", "error", "errored", "timeout", "timed_out"})
_ERROR_MESSAGE_KEYS = ("error_message", "errorMessage", "error", "failure_reason", "failureReason", "reason")


def audit_category(action: str | None, entity_type: str | None = None) -> str | None:
    """Map an audit action to one of AUDIT_CATEGORIES (None when no group fits)."""
    act = str(action or "").strip().lower()
    entity = str(entity_type or "").strip().lower()
    if act.startswith(_SETTING_FIRST_PREFIXES):
        return "setting"
    segments = [part for part in act.replace("_", ".").split(".") if part]
    if any(part.startswith("approv") for part in segments) or entity in {"approval", "approval_request"}:
        return "approve"
    if act.startswith(_CHAT_PREFIXES):
        return "chat"
    if act.startswith(_RUN_PREFIXES) or act == "workflow.executed":
        return "run"
    if act.startswith(_SYNC_PREFIXES) or ".sync" in act:
        return "sync"
    if act.startswith(_AGENT_PREFIXES):
        return "agent"
    if act.startswith(_MEMBER_PREFIXES):
        return "member"
    if act.startswith(_SETTING_PREFIXES):
        return "setting"
    return None


def _status_text(value: object) -> str:
    return str(value).strip().lower() if isinstance(value, str) else ""


def audit_error_message(log: dict) -> str | None:
    details = log.get("details") if isinstance(log.get("details"), dict) else {}
    for key in _ERROR_MESSAGE_KEYS:
        value = details.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()[:500]
        if isinstance(value, dict):
            nested = value.get("message") or value.get("detail")
            if isinstance(nested, str) and nested.strip():
                return nested.strip()[:500]
    return None


def audit_outcome(log: dict) -> str:
    """Return error when the action name or its recorded status says it failed, else success."""
    action = str(log.get("action") or "").strip().lower()
    segments = {part for part in action.split(".") if part}
    if segments & _ERROR_SEGMENTS:
        return "error"
    details = log.get("details") if isinstance(log.get("details"), dict) else {}
    for key in ("status", "outcome", "result", "state"):
        if _status_text(details.get(key)) in _ERROR_STATUSES:
            return "error"
    if details.get("success") is False or details.get("ok") is False:
        return "error"
    error_value = details.get("error") or details.get("error_message") or details.get("errorMessage")
    if isinstance(error_value, (str, dict)) and error_value:
        return "error"
    return "success"


def _annotate(log: dict) -> dict:
    log["category"] = audit_category(log.get("action"), log.get("entity_type"))
    log["outcome"] = audit_outcome(log)
    log["error_message"] = audit_error_message(log) if log["outcome"] == "error" else None
    return log


def _search_text(log: dict) -> str:
    details = log.get("details") if isinstance(log.get("details"), dict) else {}
    parts = [
        log.get("action"),
        log.get("user_name"),
        log.get("user_email"),
        log.get("entity_type"),
        log.get("entity_name"),
        log.get("entity_id"),
        log.get("agent_name"),
        log.get("error_message"),
    ]
    for key in ("description", "message", "summary", "vendor", "action", "connector", "name"):
        value = details.get(key)
        if isinstance(value, str):
            parts.append(value)
    text = " ".join(str(part) for part in parts if part)
    return text.lower().replace(".", " ").replace("_", " ")


def _is_uuid_text(value: object) -> bool:
    try:
        UUID(str(value))
    except (TypeError, ValueError):
        return False
    return True


def _resolve_actor_names(client, logs: list[dict]) -> None:
    """Fill user_name / user_email from the users table for actor ids. Best effort."""
    ids: list[str] = []
    seen: set[str] = set()
    for log in logs:
        uid = log.get("user_id")
        name = log.get("user_name")
        if not uid or not _is_uuid_text(uid):
            continue
        if name and str(name) != str(uid) and not _is_uuid_text(name):
            continue
        key = str(uid)
        if key not in seen:
            seen.add(key)
            ids.append(key)
    if not ids:
        return
    names: dict[str, dict] = {}
    try:
        response = (
            client.table("users")
            .select("auth_user_id, full_name, email")
            .in_("auth_user_id", ids[:500])
            .execute()
        )
        for row in response.data or []:
            if isinstance(row, dict) and row.get("auth_user_id"):
                names[str(row["auth_user_id"])] = row
    except Exception as exc:  # noqa: BLE001 — names are a nicety; never fail the list
        logger.debug("audit actor name lookup failed: %s", exc)
        return
    for log in logs:
        row = names.get(str(log.get("user_id") or ""))
        if not row:
            continue
        full_name = str(row.get("full_name") or "").strip()
        email = str(row.get("email") or "").strip()
        if full_name or email:
            log["user_name"] = full_name or email
        if email and not log.get("user_email"):
            log["user_email"] = email


def _apply_view_filters(
    logs: list[dict],
    *,
    category: str | None,
    outcome: str | None,
    q: str | None,
) -> list[dict]:
    cat = (category or "").strip().lower() or None
    out = (outcome or "").strip().lower() or None
    needle = " ".join((q or "").strip().lower().replace(".", " ").replace("_", " ").split())
    filtered: list[dict] = []
    for log in logs:
        if cat and cat != "all" and log.get("category") != cat:
            continue
        if out in {"ok", "success", "succeeded"} and log.get("outcome") != "success":
            continue
        if out in {"err", "error", "errors"} and log.get("outcome") != "error":
            continue
        if needle and needle not in _search_text(log):
            continue
        filtered.append(log)
    return filtered


def _distinct_actor_count(logs: list[dict]) -> int:
    return len({str(log.get("user_id")) for log in logs if log.get("user_id")})


def _prepare_logs(
    client,
    org_id: str,
    *,
    action: str | None,
    user_id: str | None,
    entity_type: str | None,
    from_dt: datetime | None,
    to_dt: datetime | None,
    category: str | None,
    outcome: str | None,
    q: str | None,
) -> tuple[list[dict], bool]:
    rows = _fetch_rows(client, org_id, action, from_dt=from_dt)
    truncated = len(rows) >= FETCH_MAX
    logs = [_annotate(_normalize_log(row)) for row in rows]
    logs = _filter_logs(logs, user_id=user_id, entity_type=entity_type, from_dt=from_dt, to_dt=to_dt)
    _resolve_actor_names(client, logs)
    logs = _apply_view_filters(logs, category=category, outcome=outcome, q=q)
    return logs, truncated


def _fetch_rows(client, org_id: str, action: str | None, *, from_dt: datetime | None = None):
    def _query(order_col: str):
        # Build a fresh query per attempt: postgrest builders mutate in place.
        query = client.table("audit_logs").select("*").eq("org_id", org_id)
        if action:
            query = query.eq("action", action)
        if from_dt is not None:
            query = query.gte(order_col, from_dt.isoformat())
        return query.order(order_col, desc=True).range(0, FETCH_MAX - 1)

    last_error: Exception | None = None
    for order_col in ("created_at", "timestamp"):
        try:
            response = _query(order_col).execute()
            return list(response.data or [])
        except Exception as exc:  # noqa: BLE001 — postgrest APIError on missing columns
            last_error = exc
            message = str(exc).lower()
            if order_col == "created_at" and (
                "42703" in str(exc) or "does not exist" in message
            ):
                continue
            break

    if last_error is not None:
        raise HTTPException(status_code=500, detail=str(last_error)) from last_error
    return []


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


def _require_org(org_id: str | None) -> str:
    if org_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=error_detail("Organization context required", "UNAUTHORIZED"),
        )
    return org_id


def _resolve_from(from_ts: str | None, range_value: str | None) -> datetime | None:
    return _parse_iso(from_ts) or _range_start(range_value)


@router.get("")
def list_audit_logs(
    *,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
    user_id: Annotated[str | None, Query()] = None,
    entity_type: Annotated[str | None, Query()] = None,
    action: Annotated[str | None, Query()] = None,
    category: Annotated[str | None, Query(pattern="^(all|sync|run|approve|agent|member|setting|chat)$")] = None,
    outcome: Annotated[str | None, Query(pattern="^(all|ok|err)$")] = None,
    q: Annotated[str | None, Query(max_length=200)] = None,
    from_ts: Annotated[str | None, Query(alias="from")] = None,
    to_ts: Annotated[str | None, Query(alias="to")] = None,
    range_value: Annotated[str | None, Query(alias="range")] = None,
    limit: Annotated[int, Query(ge=1, le=LIMIT_MAX)] = LIMIT_DEFAULT,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict:
    org_id = _require_org(org_id)
    client = shared_service_client(settings, create_client)
    require_feature(get_plan_for_org(client, org_id), "audit_logs")
    start = time.perf_counter()

    logs, truncated = _prepare_logs(
        client,
        org_id,
        action=action,
        user_id=user_id,
        entity_type=entity_type,
        from_dt=_resolve_from(from_ts, range_value),
        to_dt=_parse_iso(to_ts),
        category=category,
        outcome=outcome,
        q=q,
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
    return {
        "logs": paginated,
        "total": total,
        "hasMore": has_more,
        # Totals for the whole filtered result, not just this page.
        "actors": _distinct_actor_count(logs),
        "errors": sum(1 for log in logs if log.get("outcome") == "error"),
        # True when the scan hit FETCH_MAX rows: totals cover the newest FETCH_MAX events.
        "truncated": truncated,
        "scanLimit": FETCH_MAX,
    }


@router.get("/summary")
def audit_summary(
    *,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
    range_value: Annotated[str | None, Query(alias="range")] = None,
) -> dict:
    org_id = _require_org(org_id)
    client = shared_service_client(settings, create_client)
    require_feature(get_plan_for_org(client, org_id), "audit_logs")
    from_dt = _range_start(range_value)
    rows = _fetch_rows(client, org_id, action=None, from_dt=from_dt)
    logs = [_annotate(_normalize_log(row)) for row in rows]
    logs = _filter_logs(logs, user_id=None, entity_type=None, from_dt=from_dt, to_dt=None)
    _resolve_actor_names(client, logs)

    by_action: dict[str, int] = {}
    by_entity_type: dict[str, int] = {}
    by_category: dict[str, int] = {}
    by_user: dict[str, dict] = {}

    for log in logs:
        action_key = str(log.get("action") or "unknown")
        by_action[action_key] = by_action.get(action_key, 0) + 1

        entity_key = str(log.get("entity_type") or "unknown")
        by_entity_type[entity_key] = by_entity_type.get(entity_key, 0) + 1

        category_key = log.get("category")
        if category_key:
            by_category[category_key] = by_category.get(category_key, 0) + 1

        user_key = str(log.get("user_id") or "system")
        user_name = str(log.get("user_name") or "System")
        current = by_user.get(user_key)
        if current is None:
            by_user[user_key] = {"user_id": user_key, "user_name": user_name, "count": 1}
        else:
            current["count"] += 1

    by_user_list = sorted(by_user.values(), key=lambda item: item["count"], reverse=True)[:10]
    return {
        "byAction": by_action,
        "byUser": by_user_list,
        "byEntityType": by_entity_type,
        "byCategory": by_category,
    }


@router.get("/export")
def export_audit(
    *,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
    format: Annotated[str, Query(pattern="^(csv|json)$")] = "csv",
    user_id: Annotated[str | None, Query()] = None,
    entity_type: Annotated[str | None, Query()] = None,
    action: Annotated[str | None, Query()] = None,
    category: Annotated[str | None, Query(pattern="^(all|sync|run|approve|agent|member|setting|chat)$")] = None,
    outcome: Annotated[str | None, Query(pattern="^(all|ok|err)$")] = None,
    q: Annotated[str | None, Query(max_length=200)] = None,
    from_ts: Annotated[str | None, Query(alias="from")] = None,
    to_ts: Annotated[str | None, Query(alias="to")] = None,
    range_value: Annotated[str | None, Query(alias="range")] = None,
) -> Response:
    org_id = _require_org(org_id)
    client = shared_service_client(settings, create_client)
    require_feature(get_plan_for_org(client, org_id), "audit_logs")
    logs, truncated = _prepare_logs(
        client,
        org_id,
        action=action,
        user_id=user_id,
        entity_type=entity_type,
        from_dt=_resolve_from(from_ts, range_value),
        to_dt=_parse_iso(to_ts),
        category=category,
        outcome=outcome,
        q=q,
    )

    if format == "json":
        return JSONResponse(
            content={"logs": logs, "total": len(logs), "truncated": truncated},
            headers={"Content-Disposition": 'attachment; filename="audit-export.json"'},
        )

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
            "category",
            "outcome",
            "error_message",
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
                log.get("category"),
                log.get("outcome"),
                log.get("error_message"),
            ]
        )

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="audit-export.csv"'},
    )


@router.get("/{log_id}")
def get_audit_log(
    log_id: str,
    *,
    _user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    org_id = _require_org(org_id)
    client = shared_service_client(settings, create_client)
    require_feature(get_plan_for_org(client, org_id), "audit_logs")
    response = client.table("audit_logs").select("*").eq("org_id", org_id).eq("id", log_id).limit(1).execute()
    if not response.data:
        raise HTTPException(status_code=404, detail="Audit log not found")
    log = _annotate(_normalize_log(dict(response.data[0])))
    _resolve_actor_names(client, [log])
    return log
