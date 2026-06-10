"""Durable async agent-job queue: repository, operator handler, in-process worker.

Additive to the synchronous operator endpoint. Jobs live in the agent_jobs table
(survives restarts); a background worker (started in the FastAPI lifespan) claims
queued jobs, runs them through the governed ModelRouter, and records
status/result. Cancel + retry are supported.

The worker runs in-process (same pattern as the usage scheduler). DB writes use
the service-role client. Claiming is guarded (update ... where status='queued')
so it's safe under the single prod instance; for many instances add SKIP LOCKED.
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from typing import Any

from app.operators.services.auto_execute_service import get_operator_system_prompt
from app.services.autonomous_budget_service import is_autonomous_operator
from app.billing.service import (
    apply_usage_with_overage,
    build_ai_usage_metadata,
    build_ai_usage_metadata_from_tokens,
    get_current_period,
    get_plan_for_org,
)
from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.services.model_router import TaskType, get_model_router
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


def claim_job_by_id(client: Any, job_id: str) -> dict[str, Any] | None:
    """Claim a specific queued job (queued -> running). Returns it or None."""
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


def claim_next_job(client: Any) -> dict[str, Any] | None:
    """Claim the oldest queued job (queued -> running). Returns it or None."""
    rows = (
        client.table("agent_jobs").select("*").eq("status", "queued").order("created_at").limit(1).execute().data
        or []
    )
    if not rows:
        return None
    job = rows[0]
    upd = (
        client.table("agent_jobs")
        .update({"status": "running", "started_at": _now(), "attempts": int(job.get("attempts") or 0) + 1, "updated_at": _now()})
        .eq("id", job["id"])
        .eq("status", "queued")
        .execute()
    )
    if not upd.data:
        return None  # lost the race to another worker
    return upd.data[0]


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


# ---------------------------------------------------------------------------
# Operator job handler (governed AI call + result + usage)
# ---------------------------------------------------------------------------

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
    """Execute an operator_task job: governed completion + result + usage record."""
    from app.operators.router import OperatorTaskPlan  # lazy import avoids cycle

    payload = job.get("payload") or {}
    org_id = job["org_id"]
    environment = job.get("environment") or "production"
    summary = (payload.get("task") or "Automation task").strip()
    prompt = (
        "Generate an operator task plan for the task below.\n"
        f"<task>{summary}</task>\n"
        f"<context>{payload.get('context') or {}}</context>"
    )
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
    operator_row = None
    operator_id = payload.get("operator_id")
    if operator_id:
        op_resp = (
            client.table("operators")
            .select("id, execution_mode, auto_execute_trusted_scopes")
            .eq("org_id", org_id)
            .eq("id", str(operator_id))
            .limit(1)
            .execute()
        )
        operator_row = op_resp.data[0] if op_resp.data else None

    router = get_model_router()
    autonomous_run = bool(operator_row and is_autonomous_operator(operator_row))
    ai_degraded = False
    ai_degraded_reason: str | None = None
    parsed: dict[str, Any] = {}
    ai_result = None
    try:
        ai_result = await router.complete(
            task_type=TaskType.WORKFLOW_PLANNING,
            prompt=prompt,
            system_prompt=get_operator_system_prompt(operator_row or {}),
            response_format=OperatorTaskPlan,
            org_id=org_id,
            operator_id=str(operator_id) if operator_id else None,
            autonomous_run=autonomous_run,
        )
        parsed = ai_result.parsed or {}
    except Exception as exc:  # noqa: BLE001
        ai_degraded = True
        ai_degraded_reason = getattr(exc, "code", None) or "ai_unavailable"
        logger.warning(
            "operator job AI fallback job_id=%s reason=%s error=%s",
            job.get("id"),
            ai_degraded_reason,
            str(exc),
        )

    result = {
        "task": {"description": summary, "status": "planned"},
        "aiStatus": "degraded" if ai_degraded else "ok",
        "analysis_summary": str(parsed.get("analysis_summary") or plan_defaults["analysis_summary"]).strip(),
        "finding_description": str(
            parsed.get("finding_description") or plan_defaults["finding_description"]
        ).strip(),
        "action_title": str(parsed.get("action_title") or plan_defaults["action_title"]).strip(),
        "action_description": str(
            parsed.get("action_description") or plan_defaults["action_description"]
        ).strip(),
        "confidence": int(parsed.get("confidence") or plan_defaults["confidence"]),
        "requires_approval": bool(parsed.get("requires_approval") or plan_defaults["requires_approval"]),
        "provider": ai_result.provider if ai_result else None,
        "model": ai_result.model if ai_result else None,
    }
    if ai_degraded_reason:
        result["aiDegradedReason"] = ai_degraded_reason

    # Record AI-credit + operator usage (best-effort; never fails the job).
    try:
        client = get_supabase_client(settings)
        plan = get_plan_for_org(client, org_id)
        period_start, period_end = get_current_period()
        source_id = (ai_result.model_call_id if ai_result else None) or job["id"]
        if ai_result and ai_result.model:
            ai_meta = build_ai_usage_metadata_from_tokens(
                ai_result.input_tokens, ai_result.output_tokens, ai_result.model, "model_call", source_id
            )
        else:
            ai_meta = build_ai_usage_metadata(
                [summary],
                [result["analysis_summary"]],
                None,
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
        await _notify_swarm_job_finished(settings, client, job)
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
        await _notify_swarm_job_finished(settings, client, job)
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
