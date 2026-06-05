"""Internal workflow schedule dispatch endpoint.

POST /api/internal/workflows/schedules/dispatch-due — cron-triggered; dispatches due workflow
schedules for all orgs. Protected by the INTERNAL_API_SECRET shared secret (X-Internal-Secret
header), NOT a user JWT, so an external scheduler (e.g. GitHub Actions cron) can call it.
"""
from __future__ import annotations

import hmac
from datetime import datetime, timezone
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, status

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.billing.service import get_supabase_client

logger = get_logger(__name__)

internal_router = APIRouter(prefix="/api/internal/workflows", tags=["workflows-internal"])


async def require_internal_secret(
    settings: Annotated[Settings, Depends(get_settings)],
    x_internal_secret: Annotated[str | None, Header()] = None,
) -> None:
    """Validate the X-Internal-Secret header against INTERNAL_API_SECRET."""
    secret = (settings.internal_api_secret or "").strip()
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="INTERNAL_API_SECRET is not configured",
        )
    if not x_internal_secret or not hmac.compare_digest(x_internal_secret, secret):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid internal secret")


def _dispatch_schedule(client: Any, schedule: dict, settings: Settings) -> dict:
    """Dispatch a single workflow schedule by creating a workflow run."""
    schedule_id = schedule["id"]
    workflow_id = schedule["workflow_id"]
    org_id = schedule["org_id"]
    environment = schedule.get("environment", "production")
    
    try:
        # Get the workflow to run
        workflow_resp = (
            client.table("workflows")
            .select("*")
            .eq("id", workflow_id)
            .eq("org_id", org_id)
            .single()
            .execute()
        )
        workflow = workflow_resp.data
        if not workflow:
            return {"schedule_id": schedule_id, "status": "skipped", "reason": "workflow_not_found"}
        
        # Create a workflow run
        run_id = str(uuid4())
        now = datetime.now(timezone.utc).isoformat()
        run_data = {
            "id": run_id,
            "workflow_id": workflow_id,
            "org_id": org_id,
            "environment": environment,
            "status": "pending",
            "trigger_type": "schedule",
            "trigger_id": schedule_id,
            "created_at": now,
            "updated_at": now,
        }
        client.table("workflow_runs").insert(run_data).execute()
        
        # Calculate and update next_run_at based on cron expression
        cron_expression = schedule.get("cron_expression", "0 * * * *")
        next_run = _calculate_next_run(cron_expression)
        
        client.table("workflow_schedules").update({
            "last_run_at": now,
            "next_run_at": next_run,
            "updated_at": now,
        }).eq("id", schedule_id).execute()
        
        logger.info(
            "dispatched_workflow_schedule",
            extra={
                "schedule_id": schedule_id,
                "workflow_id": workflow_id,
                "run_id": run_id,
                "org_id": org_id,
            },
        )
        return {"schedule_id": schedule_id, "status": "dispatched", "run_id": run_id}
        
    except Exception as exc:
        logger.error(
            "workflow_schedule_dispatch_failed",
            extra={
                "schedule_id": schedule_id,
                "workflow_id": workflow_id,
                "error": str(exc),
            },
        )
        return {"schedule_id": schedule_id, "status": "error", "error": str(exc)}


def _calculate_next_run(cron_expression: str) -> str:
    """Calculate the next run time based on cron expression.
    
    This is a simplified implementation that adds 1 hour for hourly crons
    or uses the default interval. For production, use a proper cron parser.
    """
    from datetime import timedelta
    
    now = datetime.now(timezone.utc)
    
    # Simple parsing for common patterns
    parts = cron_expression.split()
    if len(parts) >= 5:
        minute, hour, day, month, weekday = parts[:5]
        
        # Every N minutes: */N * * * *
        if minute.startswith("*/"):
            try:
                interval = int(minute[2:])
                next_run = now + timedelta(minutes=interval)
                return next_run.isoformat()
            except ValueError:
                pass
        
        # Every hour at minute M: M * * * *
        if minute.isdigit() and hour == "*":
            next_run = now + timedelta(hours=1)
            return next_run.replace(minute=int(minute), second=0, microsecond=0).isoformat()
    
    # Default: add 1 hour
    return (now + timedelta(hours=1)).isoformat()


@internal_router.post("/schedules/dispatch-due")
async def dispatch_due_workflow_schedules(
    _: Annotated[None, Depends(require_internal_secret)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """Dispatch all workflow schedules that are due.
    
    Called by external cron (GitHub Actions) with X-Internal-Secret header.
    Finds all enabled schedules where next_run_at <= now and dispatches them.
    """
    client = get_supabase_client(settings)
    now_iso = datetime.now(timezone.utc).isoformat()
    
    # Find all due schedules across all orgs
    response = (
        client.table("workflow_schedules")
        .select("*")
        .eq("enabled", True)
        .lte("next_run_at", now_iso)
        .execute()
    )
    schedules = list(response.data or [])
    
    if not schedules:
        logger.info("no_due_workflow_schedules", extra={"checked_at": now_iso})
        return {"dispatched": 0, "results": []}
    
    results = []
    for schedule in schedules:
        result = _dispatch_schedule(client, schedule, settings)
        results.append(result)
    
    dispatched_count = sum(1 for r in results if r["status"] == "dispatched")
    logger.info(
        "workflow_schedules_dispatch_complete",
        extra={
            "total_due": len(schedules),
            "dispatched": dispatched_count,
            "checked_at": now_iso,
        },
    )
    
    return {"dispatched": dispatched_count, "results": results}
