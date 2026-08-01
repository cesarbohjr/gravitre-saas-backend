"""Agent lifecycle notifications (non-terminal). Module A remains sole terminal writer."""
from __future__ import annotations

from typing import Any


def notify_agent_started(
    client: Any,
    *,
    org_id: str,
    user_id: str,
    agent_id: str | None = None,
    job_id: str | None = None,
    run_id: str | None = None,
    title: str,
    body: str,
    result_url: str | None = None,
) -> str | None:
    """Emit run_started when an agent job/step begins (mid-flight, not Module A terminal)."""
    from app.services.notification_emitter import emit_notification

    entity_type = "agent_job" if job_id else ("agent" if agent_id else "workflow_run")
    entity_id = job_id or agent_id or run_id
    url = result_url
    if not url:
        if agent_id:
            url = f"/agents/{agent_id}"
        elif job_id:
            url = "/assignments"
        elif run_id:
            url = f"/runs/{run_id}"
    return emit_notification(
        client,
        org_id=org_id,
        user_id=user_id,
        event_type="run_started",
        title=title,
        body=body,
        entity_ref={
            "entity_type": entity_type,
            "entity_id": entity_id,
            "result_url": url,
            "agent_id": agent_id,
            "job_id": job_id,
            "run_id": run_id,
        },
        channel_hints={"bell": True, "email": False},
    )


def notify_agent_completed(
    client: Any,
    *,
    org_id: str,
    user_id: str,
    agent_id: str | None = None,
    job_id: str | None = None,
    run_id: str | None = None,
    title: str,
    body: str,
    result_url: str | None = None,
) -> str | None:
    """Mid-flight milestone via task_completed. Terminals stay Module A."""
    from app.services.notification_emitter import emit_notification

    entity_type = "agent_job" if job_id else ("agent" if agent_id else "workflow_run")
    entity_id = job_id or agent_id or run_id
    url = result_url
    if not url:
        if agent_id:
            url = f"/agents/{agent_id}"
        elif job_id:
            url = "/assignments"
        elif run_id:
            url = f"/runs/{run_id}"
    return emit_notification(
        client,
        org_id=org_id,
        user_id=user_id,
        event_type="task_completed",
        title=title,
        body=body,
        entity_ref={
            "entity_type": entity_type,
            "entity_id": entity_id,
            "result_url": url,
            "agent_id": agent_id,
            "job_id": job_id,
            "run_id": run_id,
        },
        channel_hints={"bell": True, "email": False},
    )


def notify_agent_needs_approval(
    client: Any,
    *,
    org_id: str,
    user_id: str,
    agent_id: str | None = None,
    job_id: str | None = None,
    run_id: str | None = None,
    title: str,
    body: str,
    result_url: str | None = None,
) -> str | None:
    """Emit approval_needed for agent-job human gates."""
    from app.services.notification_emitter import emit_notification

    entity_type = "agent_job" if job_id else ("agent" if agent_id else "operator")
    entity_id = job_id or agent_id or run_id
    url = result_url or "/approvals"
    return emit_notification(
        client,
        org_id=org_id,
        user_id=user_id,
        event_type="approval_needed",
        title=title,
        body=body,
        entity_ref={
            "entity_type": entity_type,
            "entity_id": entity_id,
            "result_url": url,
            "agent_id": agent_id,
            "job_id": job_id,
            "run_id": run_id,
        },
        channel_hints={"bell": True, "email": False},
    )
