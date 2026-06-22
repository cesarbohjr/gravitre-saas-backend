"""Cross-agent handoff data bus (STA-17 / STA-18)."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from app.config import Settings
from app.workflows.audit import write_audit_event
from app.workflows.repository import get_supabase_client
from app.workflows.constants import RESOURCE_TYPE_WORKFLOW_RUN

logger = logging.getLogger(__name__)

BRIEFING_ARTIFACT_MAX_BYTES = 4000


class HandoffBriefing(BaseModel):
    contact: dict[str, Any] | None = None
    deal: dict[str, Any] | None = None
    decision: dict[str, Any] | None = None
    artifacts: list[dict[str, Any]] = Field(default_factory=list)


class AgentTaskResult(BaseModel):
    summary: str = ""
    decision: dict[str, Any] | None = None
    recommended_actions: list[str] = Field(default_factory=list)
    confidence: int = Field(default=0, ge=0, le=100)


def _truncate_json(value: Any, max_bytes: int = BRIEFING_ARTIFACT_MAX_BYTES) -> Any:
    raw = json.dumps(value, separators=(",", ":"), default=str)
    if len(raw.encode("utf-8")) <= max_bytes:
        return value
    return {"truncated": True, "preview": raw[: max_bytes // 2]}


def build_handoff_briefing(
    *,
    parameters: dict[str, Any],
    source_output: dict[str, Any] | None = None,
    step_outputs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build briefing JSON from workflow context and source agent output."""
    contact = parameters.get("contact")
    if not isinstance(contact, dict):
        contact = None
    deal = parameters.get("deal")
    if not isinstance(deal, dict):
        deal = None

    decision: dict[str, Any] | None = None
    if isinstance(parameters.get("decision"), dict):
        decision = dict(parameters["decision"])
    elif source_output and isinstance(source_output.get("decision"), dict):
        decision = dict(source_output["decision"])
    elif source_output and source_output.get("summary"):
        decision = {
            "summary": str(source_output.get("summary") or ""),
            "confidence": source_output.get("confidence"),
        }

    artifacts: list[dict[str, Any]] = []
    hubspot = parameters.get("hubspot_event")
    if isinstance(hubspot, dict):
        artifacts.append({"type": "hubspot_event", "data": _truncate_json(hubspot)})
    if source_output:
        artifacts.append({"type": "source_agent_output", "data": _truncate_json(source_output)})
    for step_id, output in (step_outputs or {}).items():
        artifacts.append(
            {
                "type": "prior_step_output",
                "step_id": step_id,
                "data": _truncate_json(output),
            }
        )

    briefing = HandoffBriefing(
        contact=contact,
        deal=deal,
        decision=decision,
        artifacts=artifacts,
    )
    return briefing.model_dump(exclude_none=True)


def get_agent(client: Any, org_id: str, agent_id: str) -> dict[str, Any] | None:
    result = (
        client.table("agents")
        .select("id,org_id,name,purpose,role,model,systems,status,config,trained_model_id")
        .eq("id", agent_id)
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        return None
    return dict(result.data[0])


def create_handoff(
    client: Any,
    *,
    org_id: str,
    from_agent_id: str,
    to_agent_id: str,
    briefing: dict[str, Any],
    workflow_run_id: str | None = None,
    workflow_step_id: str | None = None,
    source_output: dict[str, Any] | None = None,
    actor_id: str,
) -> dict[str, Any]:
    row = {
        "org_id": org_id,
        "from_agent_id": from_agent_id,
        "to_agent_id": to_agent_id,
        "briefing": briefing,
        "workflow_run_id": workflow_run_id,
        "workflow_step_id": workflow_step_id,
        "source_output": source_output,
        "status": "pending",
    }
    result = client.table("agent_handoffs").insert(row).execute()
    if not result.data:
        raise RuntimeError("agent_handoffs insert returned no row")
    handoff = dict(result.data[0])
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=actor_id,
        action="agent.handoff.created",
        resource_type=RESOURCE_TYPE_WORKFLOW_RUN,
        resource_id=workflow_run_id or handoff["id"],
        metadata={
            "handoff_id": str(handoff["id"]),
            "from_agent_id": from_agent_id,
            "to_agent_id": to_agent_id,
            "workflow_step_id": workflow_step_id,
        },
    )
    return handoff


def complete_handoff(
    client: Any,
    *,
    org_id: str,
    handoff_id: str,
    actor_id: str,
    status: str = "completed",
    error_message: str | None = None,
) -> None:
    payload: dict[str, Any] = {
        "status": status,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }
    if error_message:
        payload["error_message"] = error_message
    client.table("agent_handoffs").update(payload).eq("id", handoff_id).eq("org_id", org_id).execute()
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=actor_id,
        action="agent.handoff.completed" if status == "completed" else "agent.handoff.failed",
        resource_type="agent_handoff",
        resource_id=handoff_id,
        metadata={"status": status},
    )


async def run_agent_task(
    settings: Settings,
    *,
    org_id: str,
    agent: dict[str, Any],
    task: str,
    briefing: dict[str, Any] | None = None,
    parameters: dict[str, Any] | None = None,
    actor_id: str | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Execute an agent task through the universal AgentIntelligence layer (STA-137)."""
    from app.operators.agent_intelligence import get_agent_intelligence

    client = get_supabase_client(settings)
    result = await get_agent_intelligence().execute_task(
        settings=settings,
        org_id=org_id,
        agent=agent,
        task=task,
        briefing=briefing,
        parameters=parameters,
        actor_id=actor_id,
        run_id=run_id,
        task_id=run_id,
        client=client,
    )
    return result.to_handoff_dict()


async def execute_agent_step_with_handoff(
    settings: Settings,
    *,
    org_id: str,
    user_id: str,
    run_id: str,
    step_id: str,
    step_def: dict[str, Any],
    parameters: dict[str, Any],
    step_outputs: dict[str, Any],
    client: Any,
) -> dict[str, Any]:
    """Run source agent; route to next_agent_id with briefing when configured (STA-18)."""
    agent_id, next_agent_id, task = resolve_step_agent_metadata(step_def)
    if not agent_id:
        raise ValueError("agent step requires metadata.agent_id or config.agent_id")
    if not task:
        task = "Complete assigned workflow task"

    source_agent = get_agent(client, org_id, agent_id)
    if not source_agent:
        raise ValueError(f"Agent not found: {agent_id}")
    if (source_agent.get("status") or "active") != "active":
        raise ValueError(f"Agent is not active: {agent_id}")

    metadata = step_def.get("metadata") if isinstance(step_def.get("metadata"), dict) else {}
    config = step_def.get("config") if isinstance(step_def.get("config"), dict) else {}
    briefing_from_steps = bool(
        metadata.get("briefing_from_steps") or config.get("briefing_from_steps")
    )

    source_briefing = None
    if briefing_from_steps and step_outputs:
        source_briefing = build_handoff_briefing(
            parameters=parameters,
            step_outputs=step_outputs,
        )

    source_output = await run_agent_task(
        settings,
        org_id=org_id,
        agent=source_agent,
        task=task,
        briefing=source_briefing,
        parameters=parameters,
        actor_id=user_id,
        run_id=run_id,
    )

    output: dict[str, Any] = {
        "source_agent_id": agent_id,
        "source_output": source_output,
        "handoff": None,
        "receiver_output": None,
    }

    if not next_agent_id:
        output["summary"] = source_output.get("summary")
        return output

    receiver_agent = get_agent(client, org_id, next_agent_id)
    if not receiver_agent:
        raise ValueError(f"Next agent not found: {next_agent_id}")

    briefing = build_handoff_briefing(
        parameters=parameters,
        source_output=source_output,
        step_outputs=step_outputs,
    )
    handoff = create_handoff(
        client,
        org_id=org_id,
        from_agent_id=agent_id,
        to_agent_id=next_agent_id,
        briefing=briefing,
        workflow_run_id=run_id,
        workflow_step_id=step_id,
        source_output=source_output,
        actor_id=user_id,
    )

    receiver_task = (
        (step_def.get("metadata") or {}).get("receiver_task")
        or (step_def.get("config") or {}).get("receiver_task")
        or "Continue workflow using the handoff briefing"
    )
    try:
        receiver_output = await run_agent_task(
            settings,
            org_id=org_id,
            agent=receiver_agent,
            task=str(receiver_task),
            briefing=briefing,
            parameters=parameters,
            actor_id=user_id,
            run_id=run_id,
        )
        complete_handoff(
            client,
            org_id=org_id,
            handoff_id=str(handoff["id"]),
            actor_id=user_id,
            status="completed",
        )
        output["handoff"] = {
            "id": str(handoff["id"]),
            "from_agent_id": agent_id,
            "to_agent_id": next_agent_id,
            "briefing": briefing,
        }
        output["receiver_output"] = receiver_output
        output["summary"] = receiver_output.get("summary") or source_output.get("summary")
        output["next_agent_id"] = next_agent_id
        return output
    except Exception as exc:
        complete_handoff(
            client,
            org_id=org_id,
            handoff_id=str(handoff["id"]),
            actor_id=user_id,
            status="failed",
            error_message=str(exc),
        )
        raise


def resolve_step_agent_metadata(step_def: dict[str, Any]) -> tuple[str | None, str | None, str | None]:
    """Return (agent_id, next_agent_id, task) from step config/metadata."""
    metadata = step_def.get("metadata") if isinstance(step_def.get("metadata"), dict) else {}
    config = step_def.get("config") if isinstance(step_def.get("config"), dict) else {}
    agent_id = metadata.get("agent_id") or config.get("agent_id")
    next_agent_id = metadata.get("next_agent_id") or config.get("next_agent_id")
    task = metadata.get("task") or config.get("task")
    return (
        str(agent_id) if agent_id else None,
        str(next_agent_id) if next_agent_id else None,
        str(task).strip() if task else None,
    )
