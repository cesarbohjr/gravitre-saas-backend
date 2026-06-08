"""Multi-agent swarm coordinator (STA-119).

Parent agent spawns N sub-agents with scoped tools via the agent_jobs queue.
When all subtasks finish, results are aggregated through the council pattern.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from app.config import Settings
from app.services.council_service import DecisionMethod, get_council_service
from app.services.handoff_service import get_agent
from app.services.model_router import TaskType, get_model_router
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
        agents.append(
            {
                "name": agent.get("name") or "Sub-agent",
                "role": agent.get("role") or config.get("council_role") or "analyst",
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

        job = agent_jobs_mod.create_job(
            client,
            org_id,
            kind="swarm_subtask",
            environment=environment,
            payload={
                "swarmRunId": swarm_id,
                "subtaskId": str(subtask["id"]),
                "agentId": spec.agent_id,
                "task": spec.task.strip(),
                "scopedTools": spec.scoped_tools,
                "objective": objective.strip(),
                "parentAgentId": parent_agent_id,
            },
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
    return _serialize_swarm(swarm, serialized_subtasks)


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
        raise SwarmCoordinatorError("Swarm is already aggregating", code="CONFLICT")

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
    council = get_council_service()
    session = await council.start_council(
        org_id=org_id,
        workflow_id=f"swarm:{swarm_run_id}",
        run_id=swarm_run_id,
        objective=str(swarm["objective"]),
        options=options,
        agents=agents,
        evidence=evidence,
        decision_method=_decision_method(str(swarm.get("decision_method"))),
        max_rounds=2,
    )
    aggregate_result = {
        "councilSessionId": session.id,
        "finalRecommendation": session.final_recommendation,
        "finalConfidence": session.final_confidence,
        "dissentingOpinions": session.dissenting_opinions,
        "debateRounds": session.debate_rounds,
        "subtaskResults": [row.get("result") for row in subtasks],
    }
    updated = (
        client.table("agent_swarm_runs")
        .update(
            {
                "status": SWARM_COMPLETED,
                "council_session_id": session.id,
                "final_recommendation": session.final_recommendation,
                "final_confidence": session.final_confidence,
                "aggregate_result": aggregate_result,
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
        update["status"] = "completed"
        update["result"] = job.get("result") or {}
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
    """Execute a scoped sub-agent task and return structured findings for council aggregation."""
    payload = job.get("payload") or {}
    org_id = str(job["org_id"])
    agent_id = str(payload.get("agentId") or "")
    task = str(payload.get("task") or "").strip()
    objective = str(payload.get("objective") or "").strip()
    scoped_tools = payload.get("scopedTools") or []

    from app.workflows.repository import get_supabase_client

    client = get_supabase_client(settings)
    agent = get_agent(client, org_id, agent_id) if agent_id else None
    agent_name = str((agent or {}).get("name") or "Sub-agent")

    prompt = (
        f"Swarm objective: {objective}\n"
        f"Your sub-task: {task}\n"
        f"Allowed tools (read-only scope): {scoped_tools}\n"
        "Return ONLY strict JSON matching this schema:\n"
        '{"summary": "<short summary>", '
        '"finding": "<key finding>", '
        '"recommended_action": "<concise action label for council vote>", '
        '"confidence": <number 0.0-1.0>}'
    )
    fallback = SwarmSubtaskResult(
        agent_id=agent_id,
        agent_name=agent_name,
        summary=task[:200],
        finding="Completed with default assessment.",
        recommended_action="proceed",
        confidence=0.55,
        scoped_tools=list(scoped_tools) if isinstance(scoped_tools, list) else [],
    )
    router = get_model_router()
    try:
        response = await router.complete(
            task_type=TaskType.WORKFLOW_PLANNING,
            prompt=prompt,
            system_prompt=(
                f"You are {agent_name}, a scoped sub-agent in a multi-agent swarm. "
                "Stay within your assigned task and allowed tools."
            ),
            response_format=SwarmSubtaskResult,
            org_id=org_id,
            operator_id=agent_id or None,
        )
        if response.parsed:
            parsed = SwarmSubtaskResult.model_validate(response.parsed)
            parsed.agent_id = agent_id
            parsed.agent_name = agent_name
            parsed.scoped_tools = list(scoped_tools) if isinstance(scoped_tools, list) else []
            return {
                "agentId": agent_id,
                "agentName": agent_name,
                "summary": parsed.summary,
                "finding": parsed.finding,
                "recommendedAction": parsed.recommended_action,
                "confidence": parsed.confidence,
                "scopedTools": parsed.scoped_tools,
            }
    except Exception as exc:  # noqa: BLE001
        logger.warning("swarm subtask fallback job_id=%s error=%s", job.get("id"), str(exc))
    fb = fallback.model_dump()
    return {
        "agentId": fb["agent_id"],
        "agentName": fb["agent_name"],
        "summary": fb["summary"],
        "finding": fb["finding"],
        "recommendedAction": fb["recommended_action"],
        "confidence": fb["confidence"],
        "scopedTools": fb["scoped_tools"],
    }
