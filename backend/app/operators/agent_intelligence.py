"""Universal AgentIntelligence layer (STA-137 / AI-001).

Central entry point for agent task execution: org context, RAG, memory, handoff
briefings, role prompts, and ReAct tool loop.
"""
from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field

from app.config import MODEL_TIERS, Settings, get_settings
from app.core.logging import get_logger
from app.operators.agent_prompts import build_agent_system_prompt, get_agent_persona
from app.operators.react_engine import ReActEngine, ReActStatus, get_react_engine, resolve_permitted_tools
from app.services.agent_finetune_service import resolve_agent_inference_model
from app.services.agent_memory_service import build_task_retrieval_context, format_retrieval_prompt_section
from app.services.org_context_service import get_org_context_service
from app.services.rag_service import RAGService
from app.services.tool_registry import get_tool_registry
from app.services.tool_types import ToolContext
from app.workflows.audit import write_audit_event

logger = get_logger(__name__)

class AgentResult(BaseModel):
    """Structured agent output for handoffs, jobs, and UI."""

    summary: str = ""
    answer: str = ""
    status: str = "completed"
    react_status: str = "completed"
    decision: dict[str, Any] | None = None
    recommended_actions: list[str] = Field(default_factory=list)
    confidence: int = Field(default=0, ge=0, le=100)
    needs_human_input: bool = False
    human_input_prompt: str | None = None
    rag_sources: list[dict[str, Any]] = Field(default_factory=list)
    react_trace: list[dict[str, Any]] = Field(default_factory=list)
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    agent_id: str | None = None
    agent_name: str | None = None
    task: str | None = None
    persona: str | None = None
    model: str | None = None
    provider: str = "openai"
    briefing_received: bool = False
    error: str | None = None

    def to_handoff_dict(self) -> dict[str, Any]:
        """Shape compatible with handoff_service.run_agent_task consumers."""
        payload: dict[str, Any] = {
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "task": self.task,
            "summary": self.summary,
            "answer": self.answer,
            "status": self.status,
            "react_status": self.react_status,
            "recommended_actions": self.recommended_actions,
            "confidence": self.confidence,
            "briefing_received": self.briefing_received,
            "model": self.model,
            "provider": self.provider,
            "needs_human_input": self.needs_human_input,
            "rag_sources": self.rag_sources,
            "react_trace": self.react_trace,
            "tool_calls": self.tool_calls,
            "persona": self.persona,
        }
        if self.decision:
            payload["decision"] = self.decision
        if self.human_input_prompt:
            payload["human_input_prompt"] = self.human_input_prompt
        if self.error:
            payload["error"] = self.error
        return payload


def resolve_agent_record(
    client: Any,
    org_id: str,
    agent_id: str,
    *,
    environment_name: str = "default",
) -> dict[str, Any] | None:
    """Load workflow agent row or synthesize from operator + connector bindings."""
    from app.operators.repository import get_operator, list_connectors_by_ids, list_operator_bindings
    from app.services.handoff_service import get_agent

    row = get_agent(client, org_id, agent_id)
    if row:
        return row

    operator = get_operator(client, org_id, agent_id)
    if not operator:
        return None

    bindings = list_operator_bindings(client, org_id, [agent_id])
    connector_ids = [str(b["connector_id"]) for b in bindings if b.get("connector_id")]
    connectors = list_connectors_by_ids(client, org_id, connector_ids, environment_name)
    systems = sorted({str(c.get("type")).lower() for c in connectors if c.get("type")})

    config = dict(operator.get("config") or {})
    if operator.get("role") and not config.get("persona"):
        config.setdefault("persona", operator.get("role"))

    return {
        "id": agent_id,
        "org_id": org_id,
        "name": operator.get("name") or "Agent",
        "role": operator.get("role"),
        "purpose": operator.get("description"),
        "description": operator.get("description"),
        "systems": systems,
        "connectedSystems": systems,
        "status": operator.get("status") or "active",
        "config": config,
        "model": config.get("model"),
    }


def load_org_context(
    client: Any,
    org_id: str,
    environment_name: str = "default",
    *,
    user_id: str | None = None,
    depth: str = "standard",
) -> dict[str, Any]:
    """Org snapshot for agent prompts via OrgContextService (STA-147)."""
    return get_org_context_service().get_snapshot(
        client,
        org_id,
        environment_name=environment_name,
        depth=depth,
        user_id=user_id,
    )


def select_model_for_agent(
    agent: dict[str, Any],
    client: Any,
    org_id: str,
    task: str,
    *,
    parameters: dict[str, Any] | None = None,
) -> str:
    """Resolve OpenAI model: agent override, fine-tuned model, or complexity tier."""
    inference = resolve_agent_inference_model(client, org_id, agent)
    if inference.fine_tuned_openai_id:
        return inference.fine_tuned_openai_id
    configured = (agent.get("model") or inference.base_model or "").strip()
    if configured:
        return configured
    params = parameters or {}
    complexity = str(params.get("complexity") or "").lower()
    if complexity in {"high", "complex"} or params.get("require_high_model"):
        return MODEL_TIERS["high"]["openai"]
    if len(task) > 2500 or len(task.split()) > 400:
        return MODEL_TIERS["high"]["openai"]
    return MODEL_TIERS["medium"]["openai"]


def load_agent_task_history(
    client: Any,
    org_id: str,
    agent_id: str,
    *,
    limit: int = 5,
    exclude_task_id: str | None = None,
) -> list[dict[str, Any]]:
    """Recent completed agent_task jobs for the same agent (STA-137 task history)."""
    if not agent_id:
        return []
    try:
        resp = (
            client.table("agent_jobs")
            .select("id, payload, result, finished_at, status")
            .eq("org_id", org_id)
            .eq("kind", "agent_task")
            .eq("status", "completed")
            .order("finished_at", desc=True)
            .limit(max(limit * 3, 10))
            .execute()
        )
        rows = resp.data or []
    except Exception as exc:  # noqa: BLE001
        logger.debug("agent_task_history_load_skipped agent_id=%s error=%s", agent_id, exc)
        return []

    history: list[dict[str, Any]] = []
    for row in rows:
        job_id = str(row.get("id") or "")
        if exclude_task_id and job_id == exclude_task_id:
            continue
        payload = row.get("payload") or {}
        row_agent = str(payload.get("agent_id") or payload.get("agentId") or "")
        if row_agent != agent_id:
            continue
        result = row.get("result") or {}
        task_text = str(payload.get("task") or "").strip()
        summary = str(result.get("summary") or result.get("answer") or "").strip()
        if not task_text and not summary:
            continue
        history.append(
            {
                "task": task_text[:500],
                "summary": summary[:500],
                "finishedAt": row.get("finished_at"),
                "jobId": job_id,
            }
        )
        if len(history) >= limit:
            break
    return history


def _normalize_react_trace_step(step: dict[str, Any]) -> dict[str, Any]:
    """UI-friendly trace step with action alias for toolName (STA-174)."""
    out = dict(step)
    tool_name = out.get("toolName") or out.get("tool_name")
    if tool_name and not out.get("action"):
        out["action"] = tool_name
    return out


def _confidence_from_react(react_status: ReActStatus, tool_calls: list[dict[str, Any]]) -> int:
    if react_status == ReActStatus.COMPLETED:
        if not tool_calls:
            return 78
        successes = sum(1 for call in tool_calls if (call.get("result") or {}).get("success"))
        ratio = successes / max(len(tool_calls), 1)
        return min(95, 70 + int(ratio * 25))
    if react_status == ReActStatus.NEEDS_HUMAN_INPUT:
        return 35
    if react_status == ReActStatus.MAX_ITERATIONS_REACHED:
        return 45
    return 20


def _recommended_actions_from_tools(tool_calls: list[dict[str, Any]], answer: str) -> list[str]:
    actions: list[str] = []
    for call in tool_calls:
        tool = str(call.get("tool") or "")
        result = call.get("result") or {}
        if result.get("success"):
            actions.append(f"Executed {tool}")
        elif tool:
            actions.append(f"Review failed action: {tool}")
    if not actions and answer.strip():
        actions.append(answer.strip()[:240])
    return actions[:8]


class AgentIntelligence:
    """Unified intelligence layer for all agent task execution paths."""

    def __init__(
        self,
        settings: Settings | None = None,
        react_engine: ReActEngine | None = None,
        rag_service: RAGService | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.react_engine = react_engine or get_react_engine()
        self.rag_service = rag_service or RAGService()
        self.tool_registry = get_tool_registry()

    def get_agent_tools(
        self,
        agent: dict[str, Any],
        connected_integrations: list[str],
        *,
        permitted_tools: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """OpenAI-format tools permitted for the agent and connected for the org (STA-160)."""
        allowed = resolve_permitted_tools(agent, permitted_tools)
        return self.tool_registry.get_tools_for_agent(allowed, connected_integrations)

    async def execute_task(
        self,
        *,
        settings: Settings | None = None,
        org_id: str,
        agent: dict[str, Any],
        task: str,
        briefing: dict[str, Any] | None = None,
        parameters: dict[str, Any] | None = None,
        actor_id: str | None = None,
        run_id: str | None = None,
        task_id: str | None = None,
        environment_name: str = "default",
        client: Any | None = None,
        max_iterations: int | None = None,
    ) -> AgentResult:
        active_settings = settings or self.settings
        if client is None:
            from app.workflows.repository import get_supabase_client

            client = get_supabase_client(active_settings)

        agent_id = str(agent.get("id") or "")
        agent_name = str(agent.get("name") or "Agent")
        task_text = task.strip()
        params = parameters or {}

        org_context = load_org_context(client, org_id, environment_name=environment_name)
        connected = org_context.get("connectedIntegrations") or self.tool_registry.list_connected_integrations(
            client, org_id, environment_name=environment_name
        )

        rag_sources: list[dict[str, Any]] = []
        rag_section = ""
        try:
            rag_response = await self.rag_service.query(
                org_id,
                task_text,
                scope="agent",
                top_k=int(params.get("rag_top_k") or active_settings.rag_top_k or 8),
                agent_id=agent_id or None,
                filters={"environment": environment_name},
            )
            rag_sources = [
                {
                    "id": chunk.id,
                    "content": chunk.content[:500],
                    "score": chunk.score,
                    "source": chunk.source,
                }
                for chunk in rag_response.chunks
            ]
            if rag_response.chunks:
                rag_section = (
                    "<knowledge_base>\n"
                    + json.dumps(
                        [{"source": c.source, "content": c.content[:1200], "score": c.score} for c in rag_response.chunks],
                        default=str,
                    )[:12000]
                    + "\n</knowledge_base>\n"
                )
        except Exception as exc:  # noqa: BLE001
            logger.debug("agent_rag_query_skipped agent_id=%s error=%s", agent_id, exc)

        memory_context = build_task_retrieval_context(
            active_settings,
            client,
            org_id=org_id,
            agent=agent,
            task=task_text,
            parameters=params,
        )
        memory_section = format_retrieval_prompt_section(memory_context)

        include_history = params.get("include_task_history")
        if include_history is None:
            include_history = True
        task_history: list[dict[str, Any]] = []
        if include_history:
            task_history = load_agent_task_history(
                client,
                org_id,
                agent_id,
                limit=int(params.get("task_history_limit") or 5),
                exclude_task_id=task_id,
            )

        task_prompt = self._build_task_prompt(
            task_text,
            briefing=briefing,
            parameters=params,
            org_context=org_context,
            rag_section=rag_section,
            memory_section=memory_section,
            task_history=task_history,
        )
        system_prompt = build_agent_system_prompt(
            agent,
            org_context=org_context,
            connected_integrations=list(connected),
            rag_available=bool(rag_sources),
        )
        persona = get_agent_persona(agent)
        model = select_model_for_agent(agent, client, org_id, task_text, parameters=params)

        ctx = ToolContext(
            settings=active_settings,
            client=client,
            org_id=org_id,
            actor_id=actor_id or agent_id or "system",
            environment_name=environment_name,
            run_id=run_id,
            task_id=task_id or run_id,
            agent_id=agent_id or None,
        )

        react_result = await self.react_engine.run(
            ctx=ctx,
            task=task_prompt,
            system_prompt=system_prompt,
            agent=agent,
            model=model,
            connected_integrations=list(connected),
            max_iterations=max_iterations or int(params.get("max_react_iterations") or 10),
            audit_resource_type="workflow_run" if run_id else "agent_job",
            audit_resource_id=task_id or run_id or agent_id,
        )

        agent_result = self._agent_result_from_react(
            react_result,
            agent_id=agent_id,
            agent_name=agent_name,
            task=task_text,
            model=model,
            briefing=briefing,
            rag_sources=rag_sources,
            persona=persona.key,
        )

        write_audit_event(
            client,
            org_id=org_id,
            actor_id=ctx.actor_id,
            action="agent.intelligence.executed",
            resource_type="agent",
            resource_id=agent_id or org_id,
            metadata={
                "taskId": task_id,
                "runId": run_id,
                "personaKey": persona.key,
                "reactStatus": agent_result.react_status,
                "toolCallCount": len(agent_result.tool_calls),
                "ragSourceCount": len(rag_sources),
                "needsHumanInput": agent_result.needs_human_input,
            },
        )
        return agent_result

    @staticmethod
    def _build_task_prompt(
        task: str,
        *,
        briefing: dict[str, Any] | None,
        parameters: dict[str, Any],
        org_context: dict[str, Any],
        rag_section: str,
        memory_section: str,
        task_history: list[dict[str, Any]] | None = None,
    ) -> str:
        parts = [f"Task:\n{task}"]
        if briefing:
            parts.append(f"<handoff_briefing>{json.dumps(briefing, default=str)[:8000]}</handoff_briefing>")
        if task_history:
            parts.append(f"<task_history>{json.dumps(task_history, default=str)[:4000]}</task_history>")
        parts.append(f"<org_context>{json.dumps(org_context, default=str)[:4000]}</org_context>")
        if rag_section:
            parts.append(rag_section)
        if memory_section:
            parts.append(memory_section)
        if parameters:
            parts.append(f"<workflow_context>{json.dumps(parameters, default=str)[:8000]}</workflow_context>")
        return "\n".join(parts)

    @staticmethod
    def _agent_result_from_react(
        react_result: Any,
        *,
        agent_id: str,
        agent_name: str,
        task: str,
        model: str,
        briefing: dict[str, Any] | None,
        rag_sources: list[dict[str, Any]],
        persona: str | None = None,
    ) -> AgentResult:
        status = react_result.status
        answer = react_result.answer or ""
        tool_calls = react_result.tool_calls or []
        trace = react_result.to_dict().get("trace") or []
        normalized_trace = [_normalize_react_trace_step(step) for step in trace]
        confidence = _confidence_from_react(status, tool_calls)
        recommended = _recommended_actions_from_tools(tool_calls, answer)
        needs_human = status == ReActStatus.NEEDS_HUMAN_INPUT
        overall_status = status.value if hasattr(status, "value") else str(status)

        decision: dict[str, Any] | None = None
        if status == ReActStatus.COMPLETED:
            decision = {
                "summary": answer[:2000],
                "confidence": confidence,
                "toolsUsed": [call.get("tool") for call in tool_calls if call.get("tool")],
            }
            if rag_sources:
                decision["ragSources"] = [
                    {
                        "id": source.get("id"),
                        "source": source.get("source"),
                        "score": source.get("score"),
                    }
                    for source in rag_sources
                ]

        return AgentResult(
            summary=answer[:4000],
            answer=answer,
            status=overall_status,
            react_status=overall_status,
            decision=decision,
            recommended_actions=recommended,
            confidence=confidence,
            needs_human_input=needs_human,
            human_input_prompt=answer if needs_human else None,
            rag_sources=rag_sources,
            react_trace=normalized_trace,
            tool_calls=tool_calls,
            agent_id=agent_id,
            agent_name=agent_name,
            task=task,
            persona=persona,
            model=model,
            briefing_received=bool(briefing),
            error=react_result.error,
        )


_agent_intelligence_singleton: AgentIntelligence | None = None


def get_agent_intelligence() -> AgentIntelligence:
    global _agent_intelligence_singleton
    if _agent_intelligence_singleton is None:
        _agent_intelligence_singleton = AgentIntelligence()
    return _agent_intelligence_singleton
