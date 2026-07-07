"""Async agent-job endpoints: enqueue, status, cancel, retry.

Additive durable path for operator/agent execution (the synchronous operator
endpoint is unchanged). A job is enqueued here and processed by the in-process
worker (app/operators/agent_jobs.py). All endpoints are org-scoped via the
JWT-validated org context.
"""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
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
    model_config = ConfigDict(populate_by_name=True)

    task: str
    session_id: str | None = Field(default=None, alias="sessionId")
    agent_id: str | None = Field(default=None, alias="agentId")
    context: dict[str, Any] | None = None


class AssignmentDecisionRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    notes: str | None = None
    reason: str | None = None
    comment: str | None = None


class AssignmentDeliverableUpdateRequest(BaseModel):
    content: str = Field(..., min_length=1)


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
    agent_id = (body.agent_id or "").strip() or None
    context = dict(body.context or {})
    if agent_id:
        context.setdefault("agent_id", agent_id)
    kind = "agent_task" if agent_id else "operator_task"
    job = jobs.create_job(
        _client(settings),
        org_id,
        kind=kind,
        session_id=body.session_id,
        environment=environment,
        payload={"task": body.task, "context": context, "agent_id": agent_id},
        created_by=current_user.get("user_id"),
    )
    from app.workers.queue import enqueue_agent_execution_job

    try:
        await enqueue_agent_execution_job(job["id"])
    except Exception as exc:  # noqa: BLE001
        logger.warning("agent job enqueue failed job_id=%s error=%s", job.get("id"), str(exc))
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


@router.post("/{job_id}/pause")
async def pause(
    job_id: str,
    current_user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    from app.services.agent_interrupt_service import request_interrupt

    client = _client(settings)
    try:
        request_interrupt(
            client,
            org_id=org_id,
            target_type="agent_job",
            target_id=job_id,
            signal="pause",
            actor_id=current_user.get("user_id"),
            source="ui",
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    job = jobs.get_job(client, org_id, job_id)
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
    from app.services.agent_interrupt_service import request_interrupt

    client = _client(settings)
    try:
        request_interrupt(
            client,
            org_id=org_id,
            target_type="agent_job",
            target_id=job_id,
            signal="cancel",
            actor_id=current_user.get("user_id"),
            source="ui",
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    job = jobs.get_job(client, org_id, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
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


@router.post("/{job_id}/approve")
async def approve_job_endpoint(
    job_id: str,
    body: AssignmentDecisionRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    notes = (body.notes or body.comment or "").strip() or None
    job = jobs.approve_job(
        _client(settings),
        org_id,
        job_id,
        approver_id=current_user.get("user_id"),
        notes=notes,
    )
    if not job:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Job not found or not awaiting approval",
        )
    return _public(job)


@router.post("/{job_id}/reject")
async def reject_job_endpoint(
    job_id: str,
    body: AssignmentDecisionRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    reason = (body.reason or body.notes or body.comment or "").strip() or None
    job = jobs.reject_job(
        _client(settings),
        org_id,
        job_id,
        approver_id=current_user.get("user_id"),
        reason=reason,
    )
    if not job:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Job not found or not awaiting approval",
        )
    return _public(job)


@router.patch("/{job_id}/deliverable")
async def update_deliverable_endpoint(
    job_id: str,
    body: AssignmentDeliverableUpdateRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    job = jobs.update_job_deliverable(
        _client(settings),
        org_id,
        job_id,
        content=body.content,
    )
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return _public(job)


@router.post("/{job_id}/push")
async def push_deliverable_endpoint(
    job_id: str,
    current_user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    environment: Annotated[str, Depends(get_environment_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    if org_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization context required")
    try:
        payload = jobs.push_job_deliverable(
            _client(settings),
            org_id,
            job_id,
            user_id=current_user.get("user_id"),
            settings=settings,
            environment_name=environment,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return payload
