"""Workflow schedule dispatch worker (STA-47)."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException

from app.config import Settings
from app.workflows.cron import compute_next_run_at, is_once_schedule

logger = logging.getLogger(__name__)


def schedule_window_key(schedule_id: str, fire_at: str) -> str:
    return f"{schedule_id}:{fire_at}"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


def _execute_scheduled_workflow(**kwargs: Any) -> dict[str, Any]:
    """Lazy wrapper so idempotent skip paths avoid router circular imports."""
    from app.routers.workflows import _execute_workflow_with_context

    return _execute_workflow_with_context(**kwargs)


def _schedule_enabled(schedule: dict[str, Any]) -> bool:
    if schedule.get("enabled") is False:
        return False
    if schedule.get("is_enabled") is False:
        return False
    return bool(schedule.get("enabled", schedule.get("is_enabled", True)))


def list_due_workflow_schedules(
    client: Any,
    *,
    now: datetime | None = None,
    org_id: str | None = None,
    environment_name: str | None = None,
) -> list[dict[str, Any]]:
    now = now or _now()
    query = (
        client.table("workflow_schedules")
        .select("*")
        .eq("enabled", True)
        .lte("next_run_at", now.isoformat())
        .not_.is_("next_run_at", "null")
    )
    if org_id:
        query = query.eq("org_id", org_id)
    if environment_name:
        query = query.eq("environment", environment_name)
    result = query.execute()
    rows = [dict(row) for row in (result.data or [])]
    return [row for row in rows if _schedule_enabled(row)]


def schedule_run_exists_for_window(
    client: Any,
    org_id: str,
    schedule_id: str,
    window_key: str,
) -> bool:
    result = (
        client.table("workflow_runs")
        .select("id")
        .eq("org_id", org_id)
        .eq("schedule_id", schedule_id)
        .eq("trigger_type", "schedule")
        .contains("parameters", {"schedule_window": window_key})
        .limit(1)
        .execute()
    )
    return bool(result.data)


def _advance_schedule(
    client: Any,
    schedule: dict[str, Any],
    *,
    now: datetime,
    last_run_at: str | None,
    updated_by: str | None,
) -> str | None:
    org_id = str(schedule["org_id"])
    schedule_id = str(schedule["id"])
    environment = str(schedule.get("environment") or "production")
    cron_expression = str(schedule.get("cron_expression") or "")
    schedule_type = str(schedule.get("schedule_type") or "recurring")
    tz_name = str(schedule.get("timezone") or "UTC")
    ends_at = schedule.get("ends_at")
    run_at = schedule.get("run_at")

    # One-shot: disable after fire (or after idempotent skip of the same window).
    if is_once_schedule(schedule_type=schedule_type, cron_expression=cron_expression):
        next_run_at = None
        enabled = False
    else:
        next_run_at = compute_next_run_at(
            cron_expression,
            now,
            tz_name=tz_name,
            ends_at=ends_at,
            schedule_type=schedule_type,
            run_at=run_at,
        )
        enabled = bool(next_run_at)

    payload: dict[str, Any] = {
        "updated_at": now.isoformat(),
        "next_run_at": next_run_at,
        "enabled": enabled,
        "is_enabled": enabled,
    }
    if last_run_at is not None:
        payload["last_run_at"] = last_run_at
    if updated_by:
        payload["updated_by"] = updated_by
    client.table("workflow_schedules").update(payload).eq("id", schedule_id).eq("org_id", org_id).eq(
        "environment", environment
    ).execute()
    return next_run_at


def dispatch_single_schedule(
    client: Any,
    settings: Settings,
    schedule: dict[str, Any],
    *,
    actor_id: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Dispatch one due schedule with idempotency per fire window."""
    now = now or _now()
    schedule_id = str(schedule["id"])
    org_id = str(schedule["org_id"])
    environment = str(schedule.get("environment") or "production")
    workflow_id = str(schedule["workflow_id"])
    fire_at = str(schedule.get("next_run_at") or "")
    window_key = schedule_window_key(schedule_id, fire_at)

    if schedule_run_exists_for_window(client, org_id, schedule_id, window_key):
        _advance_schedule(client, schedule, now=now, last_run_at=None, updated_by=actor_id)
        return {
            "schedule_id": schedule_id,
            "status": "skipped",
            "reason": "idempotent",
            "window": window_key,
        }

    run_actor = str(schedule.get("created_by") or actor_id)
    parameters = {"schedule_window": window_key}
    try:
        response = _execute_scheduled_workflow(
            client=client,
            settings=settings,
            org_id=org_id,
            environment_name=environment,
            workflow_id=workflow_id,
            parameters=parameters,
            actor_id=run_actor,
            trigger_type="schedule",
            schedule_id=schedule_id,
        )
        _advance_schedule(client, schedule, now=now, last_run_at=now.isoformat(), updated_by=actor_id)
        return {
            "schedule_id": schedule_id,
            "status": "ok",
            "run_id": response.get("run_id"),
            "workflow_status": response.get("status"),
            "window": window_key,
        }
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
        logger.warning(
            "workflow_schedule_dispatch_failed schedule_id=%s org_id=%s detail=%s",
            schedule_id,
            org_id,
            detail,
        )
        _advance_schedule(client, schedule, now=now, last_run_at=None, updated_by=actor_id)
        return {
            "schedule_id": schedule_id,
            "status": "error",
            "detail": detail,
            "window": window_key,
        }
    except Exception as exc:  # noqa: BLE001
        msg = str(exc)[:500]
        logger.warning(
            "workflow_schedule_dispatch_failed schedule_id=%s org_id=%s error=%s",
            schedule_id,
            org_id,
            msg,
        )
        _advance_schedule(client, schedule, now=now, last_run_at=None, updated_by=actor_id)
        return {
            "schedule_id": schedule_id,
            "status": "error",
            "detail": msg,
            "window": window_key,
        }


def dispatch_due_workflow_schedules(
    settings: Settings,
    *,
    client: Any | None = None,
    actor_id: str = "system",
    org_id: str | None = None,
    environment_name: str | None = None,
) -> dict[str, Any]:
    """Poll all due schedules and start workflow runs via the merged executor."""
    from supabase import create_client

    client = client or create_client(settings.supabase_url, settings.supabase_service_role_key)
    now = _now()
    due = list_due_workflow_schedules(
        client,
        now=now,
        org_id=org_id,
        environment_name=environment_name,
    )
    outcomes: list[dict[str, Any]] = []
    for schedule in due:
        outcomes.append(
            dispatch_single_schedule(
                client,
                settings,
                schedule,
                actor_id=actor_id,
                now=now,
            )
        )
    return {"due_count": len(due), "processed": len(outcomes), "outcomes": outcomes}


def dispatch_org_workflow_schedules(
    settings: Settings,
    *,
    org_id: str,
    environment_name: str,
    actor_id: str,
    client: Any | None = None,
) -> dict[str, Any]:
    return dispatch_due_workflow_schedules(
        settings,
        client=client,
        actor_id=actor_id,
        org_id=org_id,
        environment_name=environment_name,
    )
