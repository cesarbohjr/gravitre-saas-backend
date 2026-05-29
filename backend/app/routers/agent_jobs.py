"""Async agent-job endpoints: enqueue, status, cancel, retry.

Additive durable path for operator/agent execution (the synchronous operator
endpoint is unchanged). A job is enqueued here and processed by the in-process
worker (app/operators/agent_jobs.py). All endpoints are org-scoped via the
JWT-validated org context.
"""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from supabase import create_client

from app.auth.dependencies import get_current_user, get_environment_context, get_org_context
from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.operators import agent_jobs as jobs

logger = get_logger(__name__)

router = APIRouter(prefix="/api/agent-jobs", tags=["agent-jobs"])


def _client(settings: Settings):
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


class EnqueueJobRequest(BaseModel):
    task: str
    session_id: str | None = None
    context: dict[str, Any] | None = None


def _public(job: dict[str, Any]) -> dict[str, Any]:
    return {
        "jobId": job.get("id"),
        "kind": job.get("kind"),
        "status": job.get("status"),
        "sessionId": job.get("session_id"),
        "result": job.get("result"),
        "error": job.get("error"),
        "attempts": job.get("attempts"),
        "createdAt": job.get("created_at"),
        "finishedAt": job.get("finished_at"),
    }


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def enqueue_job(
    body: EnqueueJobRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    environment: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    if not (body.task or "").strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="task is required")
    job = jobs.create_job(
        _client(settings),
        org_id,
        kind="operator_task",
        session_id=body.session_id,
        environment=environment,
        payload={"task": body.task, "context": body.context or {}},
        created_by=current_user.get("user_id"),
    )
    return _public(job)


@router.get("")
async def list_jobs_endpoint(
    current_user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> dict[str, Any]:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    rows = jobs.list_jobs(_client(settings), org_id, limit=limit, status=status_filter)
    return {"jobs": [_public(r) for r in rows]}


@router.get("/{job_id}")
async def get_job_status(
    job_id: str,
    current_user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    job = jobs.get_job(_client(settings), org_id, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return _public(job)


@router.post("/{job_id}/cancel")
async def cancel(
    job_id: str,
    current_user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    job = jobs.cancel_job(_client(settings), org_id, job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Job not found or not cancellable (must be queued/running)",
        )
    return _public(job)


@router.post("/{job_id}/retry")
async def retry(
    job_id: str,
    current_user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    job = jobs.retry_job(_client(settings), org_id, job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Job not found or not retryable (must be failed/cancelled)",
        )
    return _public(job)
