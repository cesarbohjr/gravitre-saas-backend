"""Durable async agent-job queue: repository, operator handler, in-process worker.

Additive to the synchronous operator endpoint. Jobs live in the agent_jobs table
(survives restarts); a background worker (started in the FastAPI lifespan) claims
queued jobs, runs them through the governed ModelRouter, and records
status/result. Cancel + retry are supported.

The worker runs in-process (same pattern as the usage scheduler). DB writes use
the service-role client. Claiming uses `claim_agent_job()` / `claim_agent_job_by_id()` RPCs (SKIP LOCKED)
for safe multi-instance workers; falls back to optimistic updates when RPCs are absent.
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from typing import Any

from app.billing.service import (
    apply_usage_with_overage,
    build_ai_usage_metadata,
    get_current_period,
    get_plan_for_org,
)
from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.workflows.repository import get_supabase_client

logger = get_logger(__name__)

ACTIVE_STATUSES = ("queued", "running", "paused")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Repository (service-role client passed in)
# ---------------------------------------------------------------------------


def create_job(
    client: Any,
    org_id: str,
    *,
    kind: str = "operator_task",
    session_id: str | None = None,
    environment: str = "production",
    payload: dict[str, Any] | None = None,
    created_by: str | None = None,
    timeout_seconds: int = 300,
    max_attempts: int = 3,
) -> dict[str, Any]:
    """Insert a queued agent job row."""
    now = datetime.now(timezone.utc)
    timeout_at = now + timedelta(seconds=timeout_seconds)
    row = {
        "org_id": org_id,
        "kind": kind,
        "session_id": session_id,
        "environment": environment,
        "payload": payload or {},
        "status": "queued",
        "created_by": created_by,
        "max_attempts": max_attempts,
        "queued_at": now.isoformat(),
        "timeout_at": timeout_at.isoformat(),
        "retry_count": 0,
    }
    resp = client.table("agent_jobs").insert(row).execute()
    return resp.data[0] if resp.data else row


def get_job(client: Any, org_id: str, job_id: str) -> dict[str, Any] | None:
    rows = (
        client.table("agent_jobs").select("*").eq("org_id", org_id).eq("id", job_id).limit(1).execute().data
        or []
    )
    return rows[0] if rows else None


def list_jobs(client: Any, org_id: str, *, limit: int = 20, status: str | None = None) -> list[dict[str, Any]]:
    """Most-recent jobs for an org (optionally filtered by status)."""
    q = client.table("agent_jobs").select("*").eq("org_id", org_id)
    if status:
        q = q.eq("status", status)
    return q.order("created_at", desc=True).limit(limit).execute().data or []


def _rpc_claim_rows(client: Any, fn_name: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    try:
        resp = client.rpc(fn_name, params or {}).execute()
    except Exception:
        return []
    data = resp.data
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    if isinstance(data, dict):
        return [data]
    return []


def _legacy_claim_job_by_id(client: Any, job_id: str) -> dict[str, Any] | None:
    rows = (
        client.table("agent_jobs").select("*").eq("id", job_id).eq("status", "queued").limit(1).execute().data
        or []
    )
    if not rows:
        return None
    job = rows[0]
    upd = (
        client.table("agent_jobs")
        .update(
            {
                "status": "running",
                "started_at": _now(),
                "attempts": int(job.get("attempts") or 0) + 1,
                "updated_at": _now(),
            }
        )
        .eq("id", job_id)
        .eq("status", "queued")
        .execute()
    )
    return upd.data[0] if upd.data else None


def _legacy_claim_next_job(client: Any) -> dict[str, Any] | None:
    rows = (
        client.table("agent_jobs").select("*").eq("status", "queued").order("created_at").limit(1).execute().data
        or []
    )
    if not rows:
        return None
    job = rows[0]
    upd = (
        client.table("agent_jobs")
        .update(
            {
                "status": "running",
                "started_at": _now(),
                "attempts": int(job.get("attempts") or 0) + 1,
                "updated_at": _now(),
            }
        )
        .eq("id", job["id"])
        .eq("status", "queued")
        .execute()
    )
    if not upd.data:
        return None
    return upd.data[0]


def claim_job_by_id(client: Any, job_id: str) -> dict[str, Any] | None:
    """Claim a specific queued job (queued -> running). Returns it or None."""
    rows = _rpc_claim_rows(client, "claim_agent_job_by_id", {"p_job_id": job_id})
    if rows:
        return rows[0]
    return _legacy_claim_job_by_id(client, job_id)


def claim_next_job(client: Any) -> dict[str, Any] | None:
    """Claim the oldest queued job (queued -> running). Returns it or None."""
    rows = _rpc_claim_rows(client, "claim_agent_job")
    if rows:
        return rows[0]
    return _legacy_claim_next_job(client)


def complete_job(client: Any, job_id: str, result: dict[str, Any]) -> None:
    client.table("agent_jobs").update(
        {"status": "completed", "result": result, "error": None, "finished_at": _now(), "updated_at": _now()}
    ).eq("id", job_id).execute()


def fail_or_requeue_job(client: Any, job: dict[str, Any], error: str) -> None:
    attempts = int(job.get("attempts") or 0)
    max_attempts = int(job.get("max_attempts") or 3)
    retry_count = int(job.get("retry_count") or 0) + 1
    if attempts < max_attempts:
        client.table("agent_jobs").update(
            {
                "status": "queued",
                "error": error,
                "retry_count": retry_count,
                "updated_at": _now(),
            }
        ).eq("id", job["id"]).execute()
    else:
        client.table("agent_jobs").update(
            {
                "status": "failed",
                "error": error,
                "retry_count": retry_count,
                "finished_at": _now(),
                "updated_at": _now(),
            }
        ).eq("id", job["id"]).execute()


def pause_job(client: Any, org_id: str, job_id: str) -> dict[str, Any] | None:
    """Pause a queued/running job for this org."""
    job = get_job(client, org_id, job_id)
    if not job or job.get("status") not in ("queued", "running"):
        return None
    upd = (
        client.table("agent_jobs")
        .update({"status": "paused", "updated_at": _now()})
        .eq("id", job_id)
        .eq("org_id", org_id)
        .execute()
    )
    return upd.data[0] if upd.data else None


def cancel_job(client: Any, org_id: str, job_id: str) -> dict[str, Any] | None:
    """Cancel a queued/running job for this org. Returns the row or None."""
    job = get_job(client, org_id, job_id)
    if not job or job.get("status") not in ACTIVE_STATUSES:
        return None
    upd = (
        client.table("agent_jobs")
        .update({"status": "cancelled", "finished_at": _now(), "updated_at": _now()})
        .eq("id", job_id)
        .eq("org_id", org_id)
        .execute()
    )
    return upd.data[0] if upd.data else None


def retry_job(client: Any, org_id: str, job_id: str) -> dict[str, Any] | None:
    """Re-enqueue a failed/cancelled job for this org. Returns the row or None."""
    job = get_job(client, org_id, job_id)
    if not job or job.get("status") not in ("failed", "cancelled", "paused"):
        return None
    upd = (
        client.table("agent_jobs")
        .update({"status": "queued", "attempts": 0, "error": None, "finished_at": None, "updated_at": _now()})
        .eq("id", job_id)
        .eq("org_id", org_id)
        .execute()
    )
    return upd.data[0] if upd.data else None


def _job_result(job: dict[str, Any]) -> dict[str, Any]:
    result = job.get("result")
    return dict(result) if isinstance(result, dict) else {}


def job_pending_approval(job: dict[str, Any]) -> bool:
    """True when a completed job still awaits human approval."""
    if job.get("status") != "completed":
        return False
    result = _job_result(job)
    if result.get("approval_status") in ("approved", "rejected"):
        return False
    return bool(result.get("requires_approval") or result.get("needs_human_input"))


def approve_job(
    client: Any,
    org_id: str,
    job_id: str,
    *,
    approver_id: str | None = None,
    notes: str | None = None,
) -> dict[str, Any] | None:
    """Record approval on a completed job awaiting review. Idempotent when already approved."""
    job = get_job(client, org_id, job_id)
    if not job:
        return None
    result = _job_result(job)
    if result.get("approval_status") == "approved":
        return job
    if not job_pending_approval(job):
        return None
    result["approval_status"] = "approved"
    result["requires_approval"] = False
    result["needs_human_input"] = False
    result["approved_at"] = _now()
    if approver_id:
        result["approved_by"] = approver_id
    if notes:
        result["approval_notes"] = notes.strip()
    upd = (
        client.table("agent_jobs")
        .update({"result": result, "updated_at": _now()})
        .eq("id", job_id)
        .eq("org_id", org_id)
        .execute()
    )
    from app.services.approval_record_service import finalize_contract_approval

    finalize_contract_approval(
        client,
        org_id=org_id,
        agent_job_id=job_id,
        status="approved",
        reviewed_by=approver_id,
    )
    return upd.data[0] if upd.data else None


def reject_job(
    client: Any,
    org_id: str,
    job_id: str,
    *,
    approver_id: str | None = None,
    reason: str | None = None,
) -> dict[str, Any] | None:
    """Reject a completed job awaiting review."""
    job = get_job(client, org_id, job_id)
    if not job:
        return None
    result = _job_result(job)
    if result.get("approval_status") == "rejected":
        return job
    if not job_pending_approval(job):
        return None
    result["approval_status"] = "rejected"
    result["requires_approval"] = False
    result["needs_human_input"] = False
    result["rejected_at"] = _now()
    result["rejection_reason"] = (reason or "Rejected by reviewer").strip()[:2000]
    if approver_id:
        result["rejected_by"] = approver_id
    upd = (
        client.table("agent_jobs")
        .update(
            {
                "result": result,
                "status": "cancelled",
                "error": result["rejection_reason"],
                "updated_at": _now(),
            }
        )
        .eq("id", job_id)
        .eq("org_id", org_id)
        .execute()
    )
    from app.services.approval_record_service import finalize_contract_approval

    finalize_contract_approval(
        client,
        org_id=org_id,
        agent_job_id=job_id,
        status="rejected",
        reviewed_by=approver_id,
    )
    return upd.data[0] if upd.data else None


def update_job_deliverable(
    client: Any,
    org_id: str,
    job_id: str,
    *,
    content: str,
) -> dict[str, Any] | None:
    job = get_job(client, org_id, job_id)
    if not job:
        return None
    trimmed = content.strip()
    if not trimmed:
        return None
    result = _job_result(job)
    result["report_content"] = trimmed
    result["reportContent"] = trimmed
    handoff = result.get("handoff")
    if isinstance(handoff, dict):
        handoff["report"] = trimmed
    upd = (
        client.table("agent_jobs")
        .update({"result": result, "updated_at": _now()})
        .eq("id", job_id)
        .eq("org_id", org_id)
        .execute()
    )
    return upd.data[0] if upd.data else None


def push_job_deliverable(
    client: Any,
    org_id: str,
    job_id: str,
    *,
    user_id: str | None,
    settings: Any,
    environment_name: str = "production",
) -> dict[str, Any]:
    job = get_job(client, org_id, job_id)
    if not job:
        raise ValueError("Job not found")
    result = _job_result(job)
    content = str(
        result.get("report_content")
        or result.get("reportContent")
        or result.get("final_recommendation")
        or ""
    ).strip()
    if not content:
        raise ValueError("No deliverable content to push")
    destination = str(result.get("destination") or result.get("push_destination") or "").strip().lower()
    if not destination:
        raise ValueError("No push destination configured on this assignment")

    from app.services.tool_service import invoke_tool
    from app.services.tool_types import ToolContext

    ctx = ToolContext(
        org_id=org_id,
        actor_id=user_id or "system",
        settings=settings,
        environment_name=environment_name,
    )
    if "slack" in destination:
        channel = str(result.get("slack_channel") or result.get("channel") or "general").lstrip("#")
        invoke_tool(
            ctx,
            "slack.post_message",
            {"channel": channel, "message": content[:3000]},
        )
    elif "hubspot" in destination or "crm" in destination:
        invoke_tool(
            ctx,
            "hubspot.notes.create",
            {"body": content[:2000], "contact_id": result.get("contact_id")},
        )
    else:
        raise ValueError(f"Destination '{destination}' is not supported for push yet")

    result["pushed_at"] = _now()
    result["push_status"] = "sent"
    client.table("agent_jobs").update({"result": result, "updated_at": _now()}).eq("id", job_id).eq("org_id", org_id).execute()
    return {"ok": True, "destination": destination, "pushed_at": result["pushed_at"]}

def _assert_job_runnable(client: Any, org_id: str, job_id: str) -> None:
    from app.services.agent_interrupt_service import AgentExecutionInterrupted, enforce_interrupt

    try:
        enforce_interrupt(client, org_id, "agent_job", job_id)
    except AgentExecutionInterrupted:
        raise
    job = get_job(client, org_id, job_id)
    if not job:
        raise AgentExecutionInterrupted("cancel", "agent_job", job_id)
    if job.get("status") in ("cancelled", "paused"):
        raise AgentExecutionInterrupted("pause" if job.get("status") == "paused" else "cancel", "agent_job", job_id)


async def run_operator_job(settings: Settings, job: dict[str, Any]) -> dict[str, Any]:
    """Execute an operator_task job via AgentIntelligence + ReAct personas (STA-174)."""
    from app.operators.agent_intelligence import get_agent_intelligence, resolve_agent_record
    from app.operators.agent_prompts import build_synthetic_agent_for_task
    from app.services.plain_english_formatter import format_plain_english

    payload = job.get("payload") or {}
    org_id = job["org_id"]
    environment = job.get("environment") or "production"
    summary = (payload.get("task") or "Automation task").strip()
    context = payload.get("context") if isinstance(payload.get("context"), dict) else {}
    plan_defaults = {
        "analysis_summary": f"Prepared an execution plan for: {summary}",
        "finding_description": "Key steps identified and ready for execution.",
        "action_title": "Run workflow",
        "action_description": "Execute the recommended workflow steps.",
        "confidence": 75,
        "requires_approval": False,
    }

    client = get_supabase_client(settings)
    await asyncio.to_thread(_assert_job_runnable, client, job["org_id"], str(job["id"]))

    operator_id = payload.get("operator_id")
    agent: dict[str, Any] | None = None
    if operator_id:
        agent = resolve_agent_record(client, org_id, str(operator_id), environment_name=environment)
    if not agent:
        agent = build_synthetic_agent_for_task(summary, context=context)

    ai_degraded = False
    ai_degraded_reason: str | None = None
    agent_result = None
    try:
        parameters = dict(context)
        parameters.setdefault("include_task_history", False)
        agent_result = await get_agent_intelligence().execute_task(
            settings=settings,
            org_id=org_id,
            agent=agent,
            task=summary,
            parameters=parameters,
            actor_id=str(job.get("created_by") or agent.get("id") or "system"),
            task_id=str(job["id"]),
            environment_name=environment,
            client=client,
        )
    except Exception as exc:  # noqa: BLE001
        ai_degraded = True
        ai_degraded_reason = getattr(exc, "code", None) or "ai_unavailable"
        logger.warning(
            "operator job AI fallback job_id=%s reason=%s error=%s",
            job.get("id"),
            ai_degraded_reason,
            str(exc),
        )

    if agent_result and not agent_result.error:
        handoff = agent_result.to_handoff_dict()
        finding = format_plain_english(
            _trace_finding_description(agent_result.react_trace) or plan_defaults["finding_description"],
            fallback=plan_defaults["finding_description"],
        )
        action_description = format_plain_english(
            agent_result.recommended_actions[0]
            if agent_result.recommended_actions
            else plan_defaults["action_description"],
            fallback=plan_defaults["action_description"],
        )
        ai_status = "ok"
        if agent_result.react_status == "error":
            ai_status = "degraded"
        result: dict[str, Any] = {
            **handoff,
            "task": {"description": summary, "status": "planned"},
            "aiStatus": ai_status,
            "analysis_summary": format_plain_english(
                agent_result.summary or plan_defaults["analysis_summary"],
                fallback=plan_defaults["analysis_summary"],
            ).strip()[:2000],
            "finding_description": str(finding).strip()[:2000],
            "action_title": plan_defaults["action_title"],
            "action_description": str(action_description).strip()[:2000],
            "confidence": int(agent_result.confidence or plan_defaults["confidence"]),
            "requires_approval": bool(agent_result.needs_human_input or plan_defaults["requires_approval"]),
            "provider": agent_result.provider,
            "model": agent_result.model,
        }
        result["recommended_actions"] = [
            format_plain_english(item, fallback=str(item)).strip()[:500]
            for item in (result.get("recommended_actions") or [])
            if item
        ]
    else:
        result = {
            "task": {"description": summary, "status": "planned"},
            "aiStatus": "degraded",
            "analysis_summary": plan_defaults["analysis_summary"],
            "finding_description": plan_defaults["finding_description"],
            "action_title": plan_defaults["action_title"],
            "action_description": plan_defaults["action_description"],
            "confidence": plan_defaults["confidence"],
            "requires_approval": plan_defaults["requires_approval"],
            "react_trace": [],
            "persona": None,
            "tool_calls": [],
            "execution_mode": "degraded",
            "executionMode": "degraded",
            "tools_available": 0,
            "toolsAvailable": 0,
            "tool_call_count": 0,
            "toolCallCount": 0,
            "execution_verified": False,
            "executionVerified": False,
        }
        if ai_degraded:
            result["aiDegradedReason"] = ai_degraded_reason or "ai_unavailable"
        elif agent_result and agent_result.error:
            result["error"] = agent_result.error
            result["aiDegradedReason"] = agent_result.error

    if ai_degraded_reason and ai_degraded:
        result["aiDegradedReason"] = ai_degraded_reason

    # Record AI-credit + operator usage (best-effort; never fails the job).
    try:
        client = get_supabase_client(settings)
        plan = get_plan_for_org(client, org_id)
        period_start, period_end = get_current_period()
        source_id = str(job["id"])
        ai_meta = build_ai_usage_metadata(
            [summary],
            [result.get("analysis_summary") or summary],
            result.get("model"),
            "model_call",
            source_id,
        )
        apply_usage_with_overage(
            client=client, org_id=org_id, environment=environment, metric_type="ai_credits",
            quantity=int(ai_meta["credits"]), plan=plan, period_start=period_start, period_end=period_end,
            metadata=ai_meta,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("agent job usage record skipped job_id=%s error=%s", job.get("id"), str(exc))

    return result


def _trace_finding_description(react_trace: list[dict[str, Any]]) -> str:
    for step in react_trace:
        observation = step.get("observation")
        if observation:
            return str(observation)[:500]
        thought = step.get("thought")
        if thought:
            return str(thought)[:500]
        tool_name = step.get("toolName") or step.get("action")
        if tool_name:
            if step.get("toolSuccess"):
                return f"Executed {tool_name} successfully."
            return f"Attempted {tool_name}."
    return ""


async def run_agent_task_job(settings: Settings, job: dict[str, Any]) -> dict[str, Any]:
    """Execute an agent-scoped task via AgentIntelligence + ReAct (STA-165)."""
    from app.operators.agent_intelligence import get_agent_intelligence, resolve_agent_record

    payload = job.get("payload") or {}
    org_id = str(job["org_id"])
    environment = job.get("environment") or "default"
    task = str(payload.get("task") or "").strip()
    if not task:
        raise ValueError("agent_task requires payload.task")

    agent_id = str(payload.get("agent_id") or payload.get("agentId") or "")
    if not agent_id:
        raise ValueError("agent_task requires payload.agent_id")

    client = get_supabase_client(settings)
    await asyncio.to_thread(_assert_job_runnable, client, org_id, str(job["id"]))

    agent = resolve_agent_record(client, org_id, agent_id, environment_name=environment)
    if not agent:
        raise ValueError(f"Agent not found: {agent_id}")
    if (agent.get("status") or "active") != "active":
        raise ValueError(f"Agent is not active: {agent_id}")

    context = payload.get("context") or {}
    parameters = dict(context) if isinstance(context, dict) else {}
    if parameters.get("include_agent_memory") is None and parameters.get("useTrainingKnowledge") is not None:
        parameters["include_agent_memory"] = bool(parameters.get("useTrainingKnowledge"))

    briefing_raw = payload.get("briefing") or payload.get("handoff_briefing")
    briefing = briefing_raw if isinstance(briefing_raw, dict) else None

    result = await get_agent_intelligence().execute_task(
        settings=settings,
        org_id=org_id,
        agent=agent,
        task=task,
        briefing=briefing,
        parameters=parameters,
        actor_id=str(job.get("created_by") or agent_id),
        task_id=str(job["id"]),
        environment_name=environment,
        client=client,
    )
    output = result.to_handoff_dict()
    output["aiStatus"] = "ok" if not result.error else "error"
    output["task"] = {"description": task, "status": result.status}
    return output


async def _notify_swarm_job_finished(settings: Settings, client: Any, job: dict[str, Any]) -> None:
    try:
        from app.services.swarm_coordinator_service import handle_swarm_subtask_job_completed

        refreshed = get_job(client, job["org_id"], str(job["id"])) or job
        await handle_swarm_subtask_job_completed(client, refreshed)
    except Exception as exc:  # noqa: BLE001
        logger.warning("swarm job notify failed job_id=%s error=%s", job.get("id"), str(exc))


async def _notify_operator_job_finished(
    settings: Settings,
    client: Any,
    job: dict[str, Any],
    result: dict[str, Any],
) -> None:
    user_id = str(job.get("created_by") or "").strip()
    org_id = str(job.get("org_id") or "").strip()
    if not user_id or not org_id:
        return
    from app.services.entity_link_service import build_entity_url
    from app.services.notification_service import create_user_notification

    payload = job.get("payload") or {}
    session_id = str(payload.get("session_id") or payload.get("sessionId") or "").strip()
    url = (
        build_entity_url("approval", str(job["id"]))
        if result.get("requires_approval")
        else (f"/ai?session={session_id}" if session_id else "/ai")
    )
    task = str(payload.get("task") or job.get("kind") or "operator task").strip()
    notification_type = "task_completed" if job.get("status") == "completed" else "run_failed"
    create_user_notification(
        client,
        org_id=org_id,
        user_id=user_id,
        notification_type=notification_type,
        title="Operator task completed" if notification_type == "task_completed" else "Operator task failed",
        body=f"Finished: {task[:160]}. Open Gravitre to review the result.",
        url=url,
        entity_type="agent_job",
        entity_id=str(job.get("id") or ""),
    )
    try:
        from app.services.notification_email_service import send_assignment_completion_email

        send_assignment_completion_email(
            client,
            settings,
            org_id=org_id,
            user_id=user_id,
            job_id=str(job.get("id") or ""),
            task_title=task[:120] or "Assignment",
            requires_approval=bool(result.get("requires_approval")),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("assignment completion email skipped job_id=%s error=%s", job.get("id"), str(exc))


from app.services.swarm_coordinator_service import run_swarm_subtask_job

_HANDLERS = {
    "operator_task": run_operator_job,
    "agent_task": run_agent_task_job,
    "swarm_subtask": run_swarm_subtask_job,
}


# ---------------------------------------------------------------------------
# In-process worker
# ---------------------------------------------------------------------------


async def _process_job_id(settings: Settings, job_id: str) -> bool:
    """Claim and process a job by id. Returns True if handled."""
    client = get_supabase_client(settings)
    job = await asyncio.to_thread(claim_job_by_id, client, job_id)
    if not job:
        return False
    handler = _HANDLERS.get(job.get("kind") or "")
    timeout_s = int((job.get("payload") or {}).get("timeout_seconds") or 300)
    from app.services.agent_interrupt_service import AgentExecutionInterrupted

    try:
        if handler is None:
            raise ValueError(f"no handler for kind={job.get('kind')}")
        result = await asyncio.wait_for(handler(settings, job), timeout=timeout_s)
        await asyncio.to_thread(_assert_job_runnable, client, job["org_id"], str(job["id"]))
        await asyncio.to_thread(complete_job, client, job["id"], result)
        from app.services.approval_record_service import maybe_create_agent_job_approval

        await asyncio.to_thread(maybe_create_agent_job_approval, client, job, result)
        refreshed = get_job(client, job["org_id"], str(job["id"])) or job
        await _notify_swarm_job_finished(settings, client, refreshed)
        await _notify_operator_job_finished(settings, client, refreshed, result if isinstance(result, dict) else {})
        logger.info("agent_job_completed id=%s kind=%s", job["id"], job.get("kind"))
    except AgentExecutionInterrupted as exc:
        if exc.signal == "pause":
            await asyncio.to_thread(pause_job, client, job["org_id"], str(job["id"]))
        else:
            await asyncio.to_thread(cancel_job, client, job["org_id"], str(job["id"]))
        logger.info("agent_job_interrupted id=%s signal=%s", job.get("id"), exc.signal)
    except TimeoutError:
        await asyncio.to_thread(fail_or_requeue_job, client, job, "execution_timeout")
        refreshed = get_job(client, job["org_id"], str(job["id"])) or job
        if refreshed.get("status") == "failed":
            await _notify_swarm_job_finished(settings, client, refreshed)
        logger.warning("agent_job_timeout id=%s timeout_s=%s", job.get("id"), timeout_s)
    except Exception as exc:  # noqa: BLE001
        logger.warning("agent_job_failed id=%s error=%s", job.get("id"), str(exc))
        await asyncio.to_thread(fail_or_requeue_job, client, job, str(exc))
        refreshed = get_job(client, job["org_id"], str(job["id"])) or job
        if refreshed.get("status") == "failed":
            await _notify_swarm_job_finished(settings, client, refreshed)
    return True


async def _process_one(settings: Settings) -> bool:
    """Claim and process a single job. Returns True if a job was handled."""
    from app.services.agent_interrupt_service import AgentExecutionInterrupted

    client = get_supabase_client(settings)
    job = await asyncio.to_thread(claim_next_job, client)
    if not job:
        return False
    handler = _HANDLERS.get(job.get("kind") or "")
    try:
        if handler is None:
            raise ValueError(f"no handler for kind={job.get('kind')}")
        result = await handler(settings, job)
        await asyncio.to_thread(_assert_job_runnable, client, job["org_id"], str(job["id"]))
        await asyncio.to_thread(complete_job, client, job["id"], result)
        from app.services.approval_record_service import maybe_create_agent_job_approval

        await asyncio.to_thread(maybe_create_agent_job_approval, client, job, result)
        refreshed = get_job(client, job["org_id"], str(job["id"])) or job
        await _notify_swarm_job_finished(settings, client, refreshed)
        await _notify_operator_job_finished(settings, client, refreshed, result if isinstance(result, dict) else {})
        logger.info("agent_job_completed id=%s kind=%s", job["id"], job.get("kind"))
    except AgentExecutionInterrupted as exc:
        if exc.signal == "pause":
            await asyncio.to_thread(pause_job, client, job["org_id"], str(job["id"]))
        else:
            await asyncio.to_thread(cancel_job, client, job["org_id"], str(job["id"]))
        logger.info("agent_job_interrupted id=%s signal=%s", job.get("id"), exc.signal)
    except Exception as exc:  # noqa: BLE001
        logger.warning("agent_job_failed id=%s error=%s", job.get("id"), str(exc))
        await asyncio.to_thread(fail_or_requeue_job, client, job, str(exc))
        refreshed = get_job(client, job["org_id"], str(job["id"])) or job
        if refreshed.get("status") == "failed":
            await _notify_swarm_job_finished(settings, client, refreshed)
    return True


async def _worker_loop(poll_seconds: int, settings: Settings) -> None:
    from app.workers.queue import dequeue_agent_execution_job

    while True:
        try:
            raw = await dequeue_agent_execution_job(timeout_seconds=poll_seconds)
            if raw:
                job_id = raw
                if raw.startswith("{"):
                    job_id = str(json.loads(raw).get("job_id") or raw)
                handled = await _process_job_id(settings, job_id)
                if handled:
                    continue
            handled = await _process_one(settings)
        except Exception as exc:  # noqa: BLE001 - never let the loop die
            logger.warning("agent_job_worker tick error: %s", str(exc))
            handled = False
        if not handled:
            await asyncio.sleep(poll_seconds)


def start_agent_job_worker() -> asyncio.Task | None:
    try:
        settings = get_settings()
        if not bool(getattr(settings, "agent_job_worker_enabled", True)):
            logger.info("agent job worker disabled")
            return None
        poll = int(getattr(settings, "agent_job_poll_seconds", 5) or 5)
    except Exception as exc:  # noqa: BLE001
        logger.warning("agent job worker not started: %s", str(exc))
        return None
    logger.info("agent job worker started poll=%ss", poll)
    return asyncio.create_task(_worker_loop(poll, settings))


async def stop_agent_job_worker(task: asyncio.Task | None) -> None:
    if task is None:
        return
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    except Exception as exc:  # noqa: BLE001
        logger.warning("agent job worker stop error: %s", str(exc))
