"""Multi-agent swarm coordinator (STA-119).

Parent agent spawns N sub-agents with scoped tools via the agent_jobs queue.
When all subtasks finish, results are aggregated through the council pattern.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from app.config import Settings
from app.services.confidence_honesty import CONFIDENCE_SOURCE_HEURISTIC, label_confidence, estimated_confidence
from app.services.council_service import DecisionMethod, coerce_council_agent_role, get_council_service
from app.services.handoff_service import get_agent
from app.services.notification_emitter import emit_notification
from app.workflows.audit import write_audit_event

logger = logging.getLogger(__name__)

AUDIT_SWARM_STARTED = "swarm.started"
AUDIT_SWARM_AGGREGATED = "swarm.aggregated"
AUDIT_SWARM_CANCELLED = "swarm.cancelled"

SWARM_PENDING = "pending"
SWARM_RUNNING = "running"
SWARM_AGGREGATING = "aggregating"
SWARM_COMPLETED = "completed"
SWARM_FAILED = "failed"
SWARM_CANCELLED = "cancelled"

SUBTASK_TERMINAL = {"completed", "failed", "cancelled"}
MAX_SUBTASKS = 10
AGGREGATING_STALE_SECONDS = 90
COUNCIL_AGGREGATE_TIMEOUT_SECONDS = 120


def _parse_ts(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _aggregating_stale(swarm: dict[str, Any], *, seconds: int = AGGREGATING_STALE_SECONDS) -> bool:
    if str(swarm.get("status") or "") != SWARM_AGGREGATING:
        return False
    updated = _parse_ts(swarm.get("updated_at"))
    if updated is None:
        return True
    return (datetime.now(timezone.utc) - updated).total_seconds() > seconds


class SwarmCoordinatorError(Exception):
    code = "SWARM_ERROR"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        if code:
            self.code = code


class SwarmSubtaskSpec(BaseModel):
    agent_id: str = Field(..., alias="agentId")
    task: str = Field(..., min_length=1)
    scoped_tools: list[dict[str, Any]] = Field(default_factory=list, alias="scopedTools")

    model_config = {"populate_by_name": True}


class SwarmSubtaskResult(BaseModel):
    agent_id: str
    agent_name: str
    summary: str
    finding: str
    recommended_action: str
    confidence: float = Field(ge=0.0, le=1.0)
    scoped_tools: list[dict[str, Any]] = Field(default_factory=list)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _serialize_subtask(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "swarmRunId": str(row["swarm_run_id"]),
        "agentId": str(row["agent_id"]),
        "taskPrompt": row["task_prompt"],
        "scopedTools": row.get("scoped_tools") or [],
        "sortOrder": int(row.get("sort_order") or 0),
        "status": row["status"],
        "agentJobId": str(row["agent_job_id"]) if row.get("agent_job_id") else None,
        "result": row.get("result"),
        "errorMessage": row.get("error_message"),
        "executionVerified": bool(row.get("execution_verified")),
        "createdAt": row.get("created_at"),
        "completedAt": row.get("completed_at"),
    }


def _serialize_swarm(row: dict[str, Any], subtasks: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    payload = {
        "id": str(row["id"]),
        "orgId": str(row["org_id"]),
        "parentAgentId": str(row["parent_agent_id"]) if row.get("parent_agent_id") else None,
        "objective": row["objective"],
        "status": row["status"],
        "decisionMethod": row.get("decision_method") or DecisionMethod.MAJORITY_VOTE.value,
        "councilSessionId": row.get("council_session_id"),
        "finalRecommendation": row.get("final_recommendation"),
        "finalConfidence": row.get("final_confidence"),
        "aggregateResult": row.get("aggregate_result") or {},
        "errorMessage": row.get("error_message"),
        "executionVerified": bool(row.get("execution_verified")),
        "createdAt": row.get("created_at"),
        "updatedAt": row.get("updated_at"),
        "completedAt": row.get("completed_at"),
    }
    if subtasks is not None:
        payload["subtasks"] = subtasks
    return payload


def _load_subtasks(client: Any, swarm_run_id: str) -> list[dict[str, Any]]:
    result = (
        client.table("agent_swarm_subtasks")
        .select("*")
        .eq("swarm_run_id", swarm_run_id)
        .order("sort_order")
        .execute()
    )
    return [dict(row) for row in (result.data or [])]


def _get_swarm_row(client: Any, org_id: str, swarm_run_id: str) -> dict[str, Any]:
    result = (
        client.table("agent_swarm_runs")
        .select("*")
        .eq("id", swarm_run_id)
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise SwarmCoordinatorError("Swarm run not found", code="NOT_FOUND")
    return dict(result.data[0])


def _decision_method(value: str | None) -> DecisionMethod:
    try:
        return DecisionMethod(value or DecisionMethod.MAJORITY_VOTE.value)
    except ValueError as exc:
        raise SwarmCoordinatorError(f"Invalid decision method: {value}", code="VALIDATION_ERROR") from exc


def _council_agents_from_subtasks(client: Any, org_id: str, subtasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    agents: list[dict[str, Any]] = []
    for row in subtasks:
        agent = get_agent(client, org_id, str(row["agent_id"]))
        if not agent:
            continue
        config = agent.get("config") if isinstance(agent.get("config"), dict) else {}
        council_role = coerce_council_agent_role(
            str(agent.get("role") or config.get("council_role") or "analyst")
        )
        agents.append(
            {
                "name": agent.get("name") or "Sub-agent",
                "role": council_role.value,
                "weight": float(config.get("council_weight") or 1.0),
            }
        )
    return agents or [{"name": "Coordinator", "role": "strategist", "weight": 1.0}]


def _options_from_subtask_results(subtasks: list[dict[str, Any]]) -> list[str]:
    options: list[str] = []
    for row in subtasks:
        result = row.get("result") if isinstance(row.get("result"), dict) else {}
        action = str(result.get("recommendedAction") or result.get("recommended_action") or "").strip()
        summary = str(result.get("summary") or row.get("task_prompt") or "").strip()
        label = action or summary or f"subtask-{row.get('sort_order', 0)}"
        options.append(label[:240])
    return options or ["defer"]


def _swarm_execution_verified(scoped_tools: Any, tool_calls: list[dict[str, Any]]) -> bool:
    if not isinstance(scoped_tools, list) or not scoped_tools:
        return False
    if not tool_calls:
        return False
    return any((call.get("result") or {}).get("success") for call in tool_calls)


def _swarm_run_execution_verified(subtasks: list[dict[str, Any]]) -> bool:
    scoped_rows = [row for row in subtasks if row.get("scoped_tools")]
    if not scoped_rows:
        return False
    return all(bool(row.get("execution_verified")) for row in scoped_rows)


def _swarm_recommended_action(recommended_actions: list[str]) -> str:
    if recommended_actions:
        return recommended_actions[0][:240]
    return "proceed"


def _fallback_swarm_result(
    *,
    agent_id: str,
    agent_name: str,
    task: str,
    scoped_tools: list[Any],
) -> dict[str, Any]:
    fb_confidence = float(
        estimated_confidence(0.55, source=CONFIDENCE_SOURCE_HEURISTIC)["confidence"]
    )
    fb = SwarmSubtaskResult(
        agent_id=agent_id,
        agent_name=agent_name,
        summary=task[:200],
        finding="Completed with default assessment.",
        recommended_action="proceed",
        confidence=fb_confidence,
        scoped_tools=list(scoped_tools) if isinstance(scoped_tools, list) else [],
    )
    return {
        "agentId": fb.agent_id,
        "agentName": fb.agent_name,
        "summary": fb.summary,
        "finding": fb.finding,
        "recommendedAction": fb.recommended_action,
        **label_confidence(fb_confidence, source=CONFIDENCE_SOURCE_HEURISTIC, is_estimate=True),
        "scopedTools": fb.scoped_tools,
        "executionVerified": False,
        "executionMode": "degraded",
        "toolsAvailable": 0,
        "toolCallCount": 0,
    }


async def start_swarm(
    client: Any,
    *,
    org_id: str,
    parent_agent_id: str,
    objective: str,
    subtasks: list[SwarmSubtaskSpec],
    actor_id: str,
    decision_method: str = DecisionMethod.MAJORITY_VOTE.value,
    environment: str = "production",
    settings: Settings | None = None,
) -> dict[str, Any]:
    if not objective.strip():
        raise SwarmCoordinatorError("Objective is required", code="VALIDATION_ERROR")
    if not subtasks:
        raise SwarmCoordinatorError("At least one subtask is required", code="VALIDATION_ERROR")
    if len(subtasks) > MAX_SUBTASKS:
        raise SwarmCoordinatorError(f"Maximum {MAX_SUBTASKS} subtasks per swarm", code="VALIDATION_ERROR")

    parent = get_agent(client, org_id, parent_agent_id)
    if not parent:
        raise SwarmCoordinatorError("Parent agent not found", code="NOT_FOUND")
    _decision_method(decision_method)

    for spec in subtasks:
        agent = get_agent(client, org_id, spec.agent_id)
        if not agent:
            raise SwarmCoordinatorError(f"Sub-agent {spec.agent_id} not found", code="NOT_FOUND")

    from app.operators import agent_jobs as agent_jobs_mod

    swarm_insert = client.table("agent_swarm_runs").insert(
        {
            "org_id": org_id,
            "parent_agent_id": parent_agent_id,
            "objective": objective.strip(),
            "status": SWARM_RUNNING,
            "decision_method": decision_method,
            "created_by": actor_id,
        }
    ).execute()
    if not swarm_insert.data:
        raise RuntimeError("agent_swarm_runs insert returned no row")
    swarm = dict(swarm_insert.data[0])
    swarm_id = str(swarm["id"])

    serialized_subtasks: list[dict[str, Any]] = []

    for idx, spec in enumerate(subtasks):
        subtask_row = {
            "swarm_run_id": swarm_id,
            "org_id": org_id,
            "agent_id": spec.agent_id,
            "task_prompt": spec.task.strip(),
            "scoped_tools": spec.scoped_tools,
            "sort_order": idx,
            "status": "queued",
        }
        sub_insert = client.table("agent_swarm_subtasks").insert(subtask_row).execute()
        if not sub_insert.data:
            raise RuntimeError("agent_swarm_subtasks insert returned no row")
        subtask = dict(sub_insert.data[0])

        job_payload: dict[str, Any] = {
            "swarmRunId": swarm_id,
            "subtaskId": str(subtask["id"]),
            "agentId": spec.agent_id,
            "task": spec.task.strip(),
            "scopedTools": spec.scoped_tools,
            "objective": objective.strip(),
            "parentAgentId": parent_agent_id,
        }

        job = agent_jobs_mod.create_job(
            client,
            org_id,
            kind="swarm_subtask",
            environment=environment,
            payload=job_payload,
            created_by=actor_id,
        )
        job_id = str(job["id"])
        updated = (
            client.table("agent_swarm_subtasks")
            .update({"agent_job_id": job_id, "updated_at": _now()})
            .eq("id", subtask["id"])
            .execute()
        )
        subtask = dict((updated.data or [subtask])[0])
        serialized_subtasks.append(_serialize_subtask(subtask))

        from app.workers.queue import enqueue_agent_execution_job

        try:
            await enqueue_agent_execution_job(job_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("swarm subtask enqueue failed job_id=%s error=%s", job_id, str(exc))

    write_audit_event(
        client,
        org_id=org_id,
        actor_id=actor_id,
        action=AUDIT_SWARM_STARTED,
        resource_type="agent_swarm_run",
        resource_id=swarm_id,
        metadata={"subtaskCount": len(subtasks), "parentAgentId": parent_agent_id},
    )
    result = _serialize_swarm(swarm, serialized_subtasks)
    return result


def list_swarm_runs(client: Any, org_id: str, *, limit: int = 20) -> list[dict[str, Any]]:
    result = (
        client.table("agent_swarm_runs")
        .select("*")
        .eq("org_id", org_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return [_serialize_swarm(dict(row)) for row in (result.data or [])]


def get_swarm_run(client: Any, org_id: str, swarm_run_id: str) -> dict[str, Any]:
    swarm = _get_swarm_row(client, org_id, swarm_run_id)
    subtasks = [_serialize_subtask(row) for row in _load_subtasks(client, swarm_run_id)]
    return _serialize_swarm(swarm, subtasks)


async def aggregate_swarm_run(client: Any, org_id: str, swarm_run_id: str) -> dict[str, Any]:
    swarm = _get_swarm_row(client, org_id, swarm_run_id)
    if swarm["status"] in {SWARM_COMPLETED, SWARM_CANCELLED}:
        return get_swarm_run(client, org_id, swarm_run_id)
    if swarm["status"] == SWARM_AGGREGATING:
        if not _aggregating_stale(swarm):
            raise SwarmCoordinatorError("Swarm is already aggregating", code="CONFLICT")
        logger.warning("retrying stale aggregating swarm org_id=%s swarm_run_id=%s", org_id, swarm_run_id)

    subtasks = _load_subtasks(client, swarm_run_id)
    if not subtasks:
        raise SwarmCoordinatorError("Swarm has no subtasks", code="VALIDATION_ERROR")
    if not all(row["status"] in SUBTASK_TERMINAL for row in subtasks):
        raise SwarmCoordinatorError("All subtasks must finish before aggregation", code="CONFLICT")
    if any(row["status"] == "failed" for row in subtasks) and not any(
        row["status"] == "completed" for row in subtasks
    ):
        failed = (
            client.table("agent_swarm_runs")
            .update(
                {
                    "status": SWARM_FAILED,
                    "error_message": "All subtasks failed",
                    "updated_at": _now(),
                    "completed_at": _now(),
                }
            )
            .eq("id", swarm_run_id)
            .execute()
        )
        row = dict((failed.data or [swarm])[0])
        return _serialize_swarm(row, [_serialize_subtask(s) for s in subtasks])

    client.table("agent_swarm_runs").update({"status": SWARM_AGGREGATING, "updated_at": _now()}).eq(
        "id", swarm_run_id
    ).execute()

    options = _options_from_subtask_results(subtasks)
    agents = _council_agents_from_subtasks(client, org_id, subtasks)

    council = get_council_service()
    decision = _decision_method(str(swarm.get("decision_method")))
    evidence = {
        "subtasks": [
            {
                "agentId": str(row["agent_id"]),
                "task": row["task_prompt"],
                "result": row.get("result"),
                "status": row["status"],
            }
            for row in subtasks
        ]
    }
    council_kwargs = {
        "org_id": org_id,
        "workflow_id": f"swarm:{swarm_run_id}",
        "run_id": swarm_run_id,
        "objective": str(swarm["objective"]),
        "options": options,
        "agents": agents,
        "decision_method": decision,
        "max_rounds": 2,
    }

    try:
        council_call = council.start_council(evidence=evidence, **council_kwargs)
        session = await asyncio.wait_for(council_call, timeout=COUNCIL_AGGREGATE_TIMEOUT_SECONDS)
    except asyncio.TimeoutError as exc:
        logger.warning("swarm council aggregate timed out swarm_run_id=%s", swarm_run_id)
        client.table("agent_swarm_runs").update(
            {
                "status": SWARM_FAILED,
                "error_message": f"Council aggregation timed out after {COUNCIL_AGGREGATE_TIMEOUT_SECONDS}s",
                "updated_at": _now(),
                "completed_at": _now(),
            }
        ).eq("id", swarm_run_id).execute()
        raise SwarmCoordinatorError(
            f"Swarm council aggregation timed out after {COUNCIL_AGGREGATE_TIMEOUT_SECONDS}s",
            code="SWARM_ERROR",
        ) from exc
    except Exception as exc:  # noqa: BLE001
        logger.warning("swarm council aggregate failed swarm_run_id=%s error=%s", swarm_run_id, str(exc))
        failed = (
            client.table("agent_swarm_runs")
            .update(
                {
                    "status": SWARM_FAILED,
                    "error_message": str(exc)[:500],
                    "updated_at": _now(),
                    "completed_at": _now(),
                }
            )
            .eq("id", swarm_run_id)
            .execute()
        )
        row = dict((failed.data or [swarm])[0])
        raise SwarmCoordinatorError(
            f"Swarm council aggregation failed: {exc}",
            code="SWARM_ERROR",
        ) from exc
    aggregate_result = {
        "councilSessionId": session.id,
        "finalRecommendation": session.final_recommendation,
        "finalConfidence": session.final_confidence,
        "dissentingOpinions": session.dissenting_opinions,
        "debateRounds": session.debate_rounds,
        "subtaskResults": [row.get("result") for row in subtasks],
    }
    run_execution_verified = _swarm_run_execution_verified(subtasks)
    updated = (
        client.table("agent_swarm_runs")
        .update(
            {
                "status": SWARM_COMPLETED,
                "council_session_id": session.id,
                "final_recommendation": session.final_recommendation,
                "final_confidence": session.final_confidence,
                "aggregate_result": aggregate_result,
                "execution_verified": run_execution_verified,
                "updated_at": _now(),
                "completed_at": _now(),
            }
        )
        .eq("id", swarm_run_id)
        .execute()
    )
    row = dict((updated.data or [swarm])[0])
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=str(swarm.get("created_by") or ""),
        action=AUDIT_SWARM_AGGREGATED,
        resource_type="agent_swarm_run",
        resource_id=swarm_run_id,
        metadata={
            "finalRecommendation": session.final_recommendation,
            "finalConfidence": session.final_confidence,
        },
    )
    created_by = str(swarm.get("created_by") or "")
    if created_by:
        recommendation = (session.final_recommendation or "Swarm finished.").strip()
        confidence_note = (
            f" Council confidence: {int(session.final_confidence * 100)}%."
            if session.final_confidence is not None
            else ""
        )
        dissent = session.dissenting_opinions or []
        dissent_note = ""
        if dissent:
            dissent_note = f" {len(dissent)} alternate view(s) recorded."
        emit_notification(
            client,
            org_id=org_id,
            user_id=created_by,
            event_type="run_completed",
            title="Multi-agent run complete",
            body=f"{recommendation[:480]}{confidence_note}{dissent_note}",
            entity_ref={
                "entity_type": "agent_swarm_run",
                "entity_id": swarm_run_id,
                "result_url": f"/agents/swarm?runId={swarm_run_id}",
            },
            channel_hints={"bell": True, "email": True},
            email_context={
                "kind": "swarm_completion",
                "swarm_run_id": swarm_run_id,
                "objective": str(swarm.get("objective") or "Multi-agent run"),
                "final_recommendation": session.final_recommendation,
                "final_confidence": session.final_confidence,
                "decision_method": str(swarm.get("decision_method") or "majority_vote"),
                "subtasks": subtasks,
                "dissenting_opinions": session.dissenting_opinions,
            },
        )
    return _serialize_swarm(row, [_serialize_subtask(s) for s in subtasks])


def cancel_swarm_run(client: Any, org_id: str, swarm_run_id: str, actor_id: str) -> dict[str, Any]:
    swarm = _get_swarm_row(client, org_id, swarm_run_id)
    if swarm["status"] in {SWARM_COMPLETED, SWARM_CANCELLED, SWARM_FAILED}:
        raise SwarmCoordinatorError(f"Swarm is terminal (status={swarm['status']})", code="CONFLICT")

    subtasks = _load_subtasks(client, swarm_run_id)
    from app.services.agent_interrupt_service import request_interrupt

    for row in subtasks:
        if row.get("agent_job_id") and row["status"] in {"pending", "queued", "running"}:
            try:
                request_interrupt(
                    client,
                    org_id=org_id,
                    target_type="agent_job",
                    target_id=str(row["agent_job_id"]),
                    signal="cancel",
                    actor_id=actor_id,
                    source="swarm_cancel",
                )
            except ValueError:
                pass
        client.table("agent_swarm_subtasks").update(
            {"status": "cancelled", "updated_at": _now(), "completed_at": _now()}
        ).eq("id", row["id"]).execute()

    updated = (
        client.table("agent_swarm_runs")
        .update({"status": SWARM_CANCELLED, "updated_at": _now(), "completed_at": _now()})
        .eq("id", swarm_run_id)
        .execute()
    )
    row = dict((updated.data or [swarm])[0])
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=actor_id,
        action=AUDIT_SWARM_CANCELLED,
        resource_type="agent_swarm_run",
        resource_id=swarm_run_id,
        metadata={},
    )
    return get_swarm_run(client, org_id, swarm_run_id)


def _sync_subtask_from_job(client: Any, job: dict[str, Any], *, failed: bool = False) -> dict[str, Any] | None:
    payload = job.get("payload") or {}
    subtask_id = payload.get("subtaskId")
    if not subtask_id:
        return None
    result = (
        client.table("agent_swarm_subtasks")
        .select("*")
        .eq("id", str(subtask_id))
        .limit(1)
        .execute()
    )
    if not result.data:
        return None
    subtask = dict(result.data[0])
    update: dict[str, Any] = {"updated_at": _now(), "completed_at": _now()}
    if failed:
        update["status"] = "failed"
        update["error_message"] = job.get("error")
    else:
        result_payload = job.get("result") or {}
        update["status"] = "completed"
        update["result"] = result_payload
        update["execution_verified"] = bool(result_payload.get("executionVerified"))
    client.table("agent_swarm_subtasks").update(update).eq("id", subtask_id).execute()
    subtask.update(update)
    return subtask


async def handle_swarm_subtask_job_completed(client: Any, job: dict[str, Any]) -> None:
    if (job.get("kind") or "") != "swarm_subtask":
        return
    payload = job.get("payload") or {}
    swarm_run_id = payload.get("swarmRunId")
    if not swarm_run_id:
        return

    failed = job.get("status") == "failed"
    subtask = _sync_subtask_from_job(client, job, failed=failed)
    if not subtask:
        return

    subtasks = _load_subtasks(client, str(swarm_run_id))
    if not all(row["status"] in SUBTASK_TERMINAL for row in subtasks):
        return

    swarm = (
        client.table("agent_swarm_runs")
        .select("*")
        .eq("id", str(swarm_run_id))
        .limit(1)
        .execute()
    )
    if not swarm.data:
        return
    row = dict(swarm.data[0])
    if row["status"] not in {SWARM_RUNNING, SWARM_PENDING}:
        return

    await aggregate_swarm_run(client, str(row["org_id"]), str(swarm_run_id))


async def run_swarm_subtask_job(settings: Settings, job: dict[str, Any]) -> dict[str, Any]:
    """Execute a scoped sub-agent via ExecutionCore (ReAct + scoped tools) for council aggregation."""
    payload = job.get("payload") or {}
    org_id = str(job["org_id"])
    agent_id = str(payload.get("agentId") or "")
    task = str(payload.get("task") or "").strip()
    objective = str(payload.get("objective") or "").strip()
    scoped_tools = payload.get("scopedTools") or []
    scoped_list = list(scoped_tools) if isinstance(scoped_tools, list) else []

    from app.operators.agent_intelligence import AgentIntelligence, resolve_agent_record
    from app.workflows.repository import get_supabase_client

    client = get_supabase_client(settings)
    agent = resolve_agent_record(client, org_id, agent_id) if agent_id else None
    if not agent:
        agent = get_agent(client, org_id, agent_id) if agent_id else None
    agent_name = str((agent or {}).get("name") or "Sub-agent")

    if not agent or not task:
        return _fallback_swarm_result(
            agent_id=agent_id,
            agent_name=agent_name,
            task=task or "Subtask",
            scoped_tools=scoped_list,
        )

    intelligence = AgentIntelligence(settings=settings)

    task_parameters: dict[str, Any] = {
        "surface": "swarm",
        "subtask_spec": {
            "task": task,
            "objective": objective,
            "scopedTools": scoped_list,
            "subtaskId": payload.get("subtaskId"),
            "swarmRunId": payload.get("swarmRunId"),
        },
        "include_task_history": False,
    }

    try:
        agent_result = await intelligence.execute_task(
            settings=settings,
            org_id=org_id,
            agent=agent,
            task=task,
            parameters=task_parameters,
            actor_id=str(job.get("created_by") or agent_id or "system"),
            task_id=str(job.get("id") or ""),
            client=client,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("swarm subtask execution failed job_id=%s error=%s", job.get("id"), str(exc))
        return _fallback_swarm_result(
            agent_id=agent_id,
            agent_name=agent_name,
            task=task,
            scoped_tools=scoped_list,
        )

    execution_verified = agent_result.execution_verified
    finding = (agent_result.answer or agent_result.summary or "").strip()
    if not finding:
        finding = "Completed subtask analysis."
    confidence = max(0.0, min(1.0, agent_result.confidence / 100.0))

    return {
        "agentId": agent_id,
        "agentName": agent_name,
        "summary": (agent_result.summary or agent_result.answer or task)[:2000],
        "finding": finding[:2000],
        "recommendedAction": _swarm_recommended_action(agent_result.recommended_actions),
        "confidence": confidence,
        "scopedTools": scoped_list,
        "executionVerified": execution_verified,
        "executionMode": agent_result.execution_mode,
        "toolsAvailable": agent_result.tools_available,
        "toolCallCount": agent_result.tool_call_count,
        "reactStatus": agent_result.react_status,
    }
