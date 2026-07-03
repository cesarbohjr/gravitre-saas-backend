"""Assistant server-side tools (STA-148 / AI-016).

Each tool is org-scoped. Outputs are fenced by the assistant router before model
injection — never treat tool payloads as instructions.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any

from app.config import Settings
from app.core.logging import get_logger
from app.services.model_router import TaskType, get_model_router
from app.services.org_context_service import get_org_context_service
from app.workflows.repository import get_supabase_client

logger = get_logger(__name__)

TOOL_DISPLAY_NAMES: dict[str, str] = {
    "knowledge_base": "searchKnowledgeBase",
    "agent_status": "getAgentStatus",
    "connector_status": "getConnectorStatus",
    "workflow_runs": "getWorkflowRuns",
    "analytics": "getAnalytics",
    "search_web": "searchWeb",
    "generate_document": "generateDocument",
    "run_agent_task": "runAgentTask",
    "create_workflow": "createWorkflow",
    "create_agent": "createAgent",
    "dependency_impact": "estimateDependencyImpact",
}

DEFAULT_ASSISTANT_TOOLS = ["knowledge_base", "agent_status", "connector_status"]

_SCHEMA_VERSION = 2


def knowledge_base_output_from_retrieval(
    rag_sources: list[dict[str, Any]],
    metrics: dict[str, Any] | None = None,
    memory_context: dict[str, Any] | None = None,
    *,
    agent_id: str | None = None,
) -> dict[str, Any]:
    """Shape unified retrieval hits like the knowledge_base tool (no second retrieve call)."""
    scope = "agent" if agent_id else "organization"
    results = [
        {
            "title": item.get("source") or "Knowledge Source",
            "snippet": (item.get("content") or "")[:280],
            "relevance": round(float(item.get("score") or 0.0), 2),
        }
        for item in rag_sources
    ]
    sources = [
        {
            "title": item.get("source") or "Knowledge Source",
            "excerpt": (item.get("content") or "")[:280],
        }
        for item in rag_sources
    ]
    memory_hits: list[dict[str, Any]] = []
    for key in ("memories", "patterns", "facts"):
        for row in (memory_context or {}).get(key) or []:
            if isinstance(row, dict):
                memory_hits.append(
                    {
                        "category": key.rstrip("s") if key.endswith("s") else key,
                        "content": str(row.get("content") or row.get("text") or "")[:280],
                        "score": round(float(row.get("score") or 0.0), 2),
                    }
                )
    payload: dict[str, Any] = {
        "results": results,
        "sources": sources,
        "totalResults": len(results),
        "method": str((metrics or {}).get("embedding_method") or "unified_retrieval"),
        "scope": scope,
    }
    if memory_hits:
        payload["memoryHits"] = memory_hits
        payload["memoryHitCount"] = len(memory_hits)
    if agent_id:
        payload["agentId"] = agent_id
    return payload


async def tool_knowledge_base(
    org_id: str,
    query: str,
    settings: Settings,
    *,
    agent_id: str | None = None,
) -> dict[str, Any]:
    try:
        from app.services.unified_retrieval_service import (
            RetrievalScopes,
            get_unified_retrieval_service,
        )

        client = get_supabase_client(settings)
        use_agent_memory = bool(agent_id)
        bundle = await get_unified_retrieval_service().retrieve(
            org_id=org_id,
            query=query,
            client=client,
            agent={"id": agent_id or ""},
            parameters={"rag_top_k": 5},
            scopes=RetrievalScopes(
                knowledge=True,
                org_context=False,
                agent_memory=use_agent_memory,
            ),
        )
        return knowledge_base_output_from_retrieval(
            bundle.rag_sources,
            bundle.metrics,
            bundle.memory_context,
            agent_id=agent_id,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("assistant knowledge_base tool failed org_id=%s error=%s", org_id, str(exc))
        return {"results": [], "totalResults": 0, "error": "knowledge base unavailable"}


def tool_agent_status(org_id: str, settings: Settings, *, agent_id: str | None = None) -> dict[str, Any]:
    try:
        client = get_supabase_client(settings)
        query = client.table("agents").select("id,name,status,stats").eq("org_id", org_id)
        if agent_id:
            query = query.eq("id", agent_id)
        rows = query.execute().data or []
        agents = []
        for row in rows:
            stats = row.get("stats") if isinstance(row.get("stats"), dict) else {}
            agents.append(
                {
                    "id": str(row.get("id")),
                    "name": str(row.get("name") or "Agent"),
                    "status": str(row.get("status") or "idle"),
                    "tasksToday": int((stats or {}).get("tasksToday") or 0),
                    "successRate": int((stats or {}).get("successRate") or 100),
                }
            )
        return {"agents": agents}
    except Exception as exc:  # noqa: BLE001
        logger.warning("assistant agent_status tool failed org_id=%s error=%s", org_id, str(exc))
        return {"agents": [], "error": "agent status unavailable"}


def tool_connector_status(org_id: str, settings: Settings) -> dict[str, Any]:
    try:
        client = get_supabase_client(settings)
        rows = (
            client.table("connectors")
            .select("id,name,type,status,health")
            .eq("org_id", org_id)
            .execute()
            .data
            or []
        )
        connectors = [
            {
                "id": str(row.get("id")),
                "name": str(row.get("name") or "connector"),
                "type": str(row.get("type") or "Custom"),
                "status": str(row.get("status") or "disconnected"),
                "health": int(row.get("health") or 0),
            }
            for row in rows
        ]
        return {"connectors": connectors}
    except Exception as exc:  # noqa: BLE001
        logger.warning("assistant connector_status tool failed org_id=%s error=%s", org_id, str(exc))
        return {"connectors": [], "error": "connector status unavailable"}


def tool_workflow_runs(
    org_id: str,
    settings: Settings,
    *,
    limit: int = 10,
    status_filter: str | None = None,
) -> dict[str, Any]:
    try:
        client = get_supabase_client(settings)
        q = (
            client.table("workflow_runs")
            .select("id,workflow_id,status,run_type,created_at,completed_at,error_message")
            .eq("org_id", org_id)
            .order("created_at", desc=True)
            .limit(max(1, min(limit, 25)))
        )
        if status_filter:
            q = q.eq("status", status_filter)
        rows = q.execute().data or []
        workflow_ids = list({str(row.get("workflow_id")) for row in rows if row.get("workflow_id")})
        workflow_names: dict[str, str] = {}
        if workflow_ids:
            wf = (
                client.table("workflow_defs")
                .select("id,name")
                .eq("org_id", org_id)
                .in_("id", workflow_ids)
                .execute()
            )
            workflow_names = {str(w["id"]): w.get("name") or "" for w in (wf.data or [])}
        runs = []
        for row in rows:
            wf_id = str(row.get("workflow_id") or "")
            runs.append(
                {
                    "id": str(row.get("id")),
                    "workflowId": wf_id or None,
                    "workflowName": workflow_names.get(wf_id) or None,
                    "status": str(row.get("status") or "unknown"),
                    "runType": str(row.get("run_type") or "execute"),
                    "createdAt": row.get("created_at"),
                    "completedAt": row.get("completed_at"),
                    "errorMessage": row.get("error_message"),
                }
            )
        return {"runs": runs, "total": len(runs)}
    except Exception as exc:  # noqa: BLE001
        logger.warning("assistant workflow_runs tool failed org_id=%s error=%s", org_id, str(exc))
        return {"runs": [], "total": 0, "error": "workflow runs unavailable"}


def _infer_run_status_filter(query: str) -> str | None:
    lowered = query.lower()
    for status in ("failed", "completed", "running", "pending", "cancelled"):
        if status in lowered:
            return status
    return None


def tool_analytics(
    org_id: str,
    settings: Settings,
    *,
    user_id: str | None = None,
) -> dict[str, Any]:
    try:
        client = get_supabase_client(settings)
        service = get_org_context_service()
        snapshot = service.get_snapshot(client, org_id, depth="full", user_id=user_id)
        since = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        run_rows = (
            client.table("workflow_runs")
            .select("status")
            .eq("org_id", org_id)
            .gte("created_at", since)
            .execute()
            .data
            or []
        )
        status_counts: dict[str, int] = {}
        for row in run_rows:
            key = str(row.get("status") or "unknown")
            status_counts[key] = status_counts.get(key, 0) + 1
        total_runs = len(run_rows)
        completed = status_counts.get("completed", 0)
        success_rate = round((completed / total_runs) * 100, 1) if total_runs else None
        return {
            "orgName": snapshot.get("orgName"),
            "counts": snapshot.get("counts") or {},
            "connectedIntegrations": snapshot.get("connectedIntegrations") or [],
            "openAlerts": len(snapshot.get("alerts") or []),
            "last7Days": {
                "totalRuns": total_runs,
                "statusBreakdown": status_counts,
                "successRatePercent": success_rate,
            },
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("assistant analytics tool failed org_id=%s error=%s", org_id, str(exc))
        return {"error": "analytics unavailable"}


async def tool_search_web(query: str, settings: Settings) -> dict[str, Any]:
    from app.services.web_research import TavilyNotConfiguredError, search_web

    try:
        return await search_web(query, settings=settings, max_results=5)
    except TavilyNotConfiguredError:
        return {"results": [], "totalResults": 0, "error": "web search not configured"}


async def tool_generate_document(org_id: str, query: str, settings: Settings) -> dict[str, Any]:
    topic = query.strip() or "Untitled document"
    try:
        router = get_model_router()
        result = await router.complete(
            task_type=TaskType.CONTENT_GENERATION,
            prompt=(
                f"Create a concise markdown document about: {topic}\n\n"
                "Use headings, bullet lists, and short paragraphs. Output only the document body."
            ),
            system_prompt=(
                "You write clear operational documents for an enterprise automation platform. "
                "Do not include preamble or meta commentary."
            ),
            org_id=org_id,
        )
        content = (result.content or "").strip()
        title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        title = title_match.group(1).strip() if title_match else topic[:80]
        return {
            "title": title,
            "format": "markdown",
            "content": content,
            "wordCount": len(content.split()),
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("assistant generate_document tool failed org_id=%s error=%s", org_id, str(exc))
        return {"title": topic[:80], "format": "markdown", "content": "", "error": "document generation failed"}


def _resolve_agent_for_task(
    client: Any,
    org_id: str,
    query: str,
    *,
    agent_id: str | None,
) -> dict[str, Any] | None:
    from app.services.handoff_service import get_agent

    if agent_id:
        return get_agent(client, org_id, agent_id)
    rows = (
        client.table("agents")
        .select("id,org_id,name,purpose,role,model,systems,status,config,trained_model_id")
        .eq("org_id", org_id)
        .eq("status", "active")
        .limit(50)
        .execute()
        .data
        or []
    )
    if not rows:
        return None
    lowered = query.lower()
    for row in rows:
        name = str(row.get("name") or "").lower()
        if name and name in lowered:
            return dict(row)
    if len(rows) == 1:
        return dict(rows[0])
    return None


async def tool_run_agent_task(
    org_id: str,
    query: str,
    settings: Settings,
    *,
    agent_id: str | None = None,
    user_id: str | None = None,
) -> dict[str, Any]:
    from app.services.handoff_service import run_agent_task

    client = get_supabase_client(settings)
    agent = _resolve_agent_for_task(client, org_id, query, agent_id=agent_id)
    if not agent:
        names = [
            str(row.get("name") or "Agent")
            for row in (
                client.table("agents")
                .select("name")
                .eq("org_id", org_id)
                .limit(10)
                .execute()
                .data
                or []
            )
        ]
        return {
            "error": "Specify an agent or mention an active agent by name",
            "availableAgents": names,
        }
    try:
        output = await run_agent_task(
            settings,
            org_id=org_id,
            agent=agent,
            task=query,
            actor_id=user_id,
        )
        return {
            "agentId": str(agent.get("id")),
            "agentName": str(agent.get("name") or "Agent"),
            "status": output.get("status"),
            "output": output.get("output"),
            "reactTraceSteps": len(output.get("react_trace") or []),
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "assistant run_agent_task tool failed org_id=%s agent_id=%s error=%s",
            org_id,
            agent.get("id"),
            str(exc),
        )
        return {
            "agentId": str(agent.get("id")),
            "agentName": str(agent.get("name") or "Agent"),
            "error": "agent task failed",
        }


def _draft_workflow_name(query: str) -> str:
    cleaned = re.sub(r"\s+", " ", query.strip())
    if not cleaned:
        return "Assistant Draft Workflow"
    first_line = cleaned.split("\n", 1)[0].strip()
    if len(first_line) > 80:
        return first_line[:77] + "..."
    return first_line


def tool_create_agent(
    org_id: str,
    query: str,
    settings: Settings,
    *,
    user_id: str | None = None,
    name: str | None = None,
    purpose: str | None = None,
) -> dict[str, Any]:
    from app.operators.repository import create_operator
    from app.services.entity_link_service import build_entity_url

    agent_name = (name or _draft_workflow_name(query)).strip()[:120]
    agent_purpose = (purpose or query or "").strip()[:500] or None
    try:
        client = get_supabase_client(settings)
        operator = create_operator(
            client,
            org_id,
            {
                "name": agent_name,
                "description": agent_purpose,
                "role": "assistant",
                "status": "inactive",
                "capabilities": [],
            },
            user_id,
        )
        agent_id = str(operator["id"])
        return {
            "id": agent_id,
            "name": agent_name,
            "url": build_entity_url("agent", agent_id),
            "message": f"Agent “{agent_name}” created — open the agent page to configure it",
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("assistant create_agent tool failed org_id=%s error=%s", org_id, str(exc))
        return {"error": "agent create failed"}


def tool_create_workflow(
    org_id: str,
    query: str,
    settings: Settings,
    *,
    user_id: str | None = None,
) -> dict[str, Any]:
    name = _draft_workflow_name(query)
    try:
        client = get_supabase_client(settings)
        definition = {"schema_version": _SCHEMA_VERSION, "steps": []}
        row = {
            "org_id": org_id,
            "name": name,
            "goal": query.strip()[:500] or name,
            "description": "Draft created by Gravitre Assistant",
            "definition": definition,
            "schema_version": _SCHEMA_VERSION,
            "status": "draft",
            "stage": "build",
            "version": "v1.0.0",
            "created_by": user_id,
        }
        result = client.table("workflow_defs").insert(row).execute()
        if not result.data:
            return {"error": "workflow create failed"}
        workflow_id = str(result.data[0]["id"])
        from app.workflows.schema_sync import mirror_legacy_workflow_row_to_contract

        mirror_legacy_workflow_row_to_contract(client, dict(result.data[0]))
        return {
            "id": workflow_id,
            "name": name,
            "status": "draft",
            "message": "Draft workflow created — open the workflow builder to add steps",
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("assistant create_workflow tool failed org_id=%s error=%s", org_id, str(exc))
        return {"error": "workflow create failed"}


async def tool_dependency_impact(
    org_id: str,
    settings: Settings,
    *,
    question: str = "",
    entity_type: str | None = None,
    entity_id: str | None = None,
) -> dict[str, Any]:
    """v9: grounded dependency impact report (graph traversal, not simulation)."""
    from app.services.dependency_impact_service import SCOPE_NOTE, get_dependency_impact_service

    service = get_dependency_impact_service(settings)
    if entity_type and entity_id:
        return await service.estimate_removal_impact(org_id, entity_type, entity_id)
    if not question.strip():
        return {"error": "question or entity_type/entity_id is required", "scopeNote": SCOPE_NOTE}
    return await service.answer_dependency_question(org_id, question)


async def run_assistant_tools(
    requested: list[str],
    org_id: str,
    query: str,
    settings: Settings,
    *,
    agent_id: str | None = None,
    user_id: str | None = None,
) -> list[dict[str, Any]]:
    """Execute requested tools server-side. Returns [{name, displayName, input, output}]."""
    results: list[dict[str, Any]] = []
    status_filter = _infer_run_status_filter(query)

    for name in requested:
        if name not in TOOL_DISPLAY_NAMES:
            continue
        tool_input: dict[str, Any] = {}
        if name == "knowledge_base":
            output = await tool_knowledge_base(org_id, query, settings, agent_id=agent_id)
            tool_input = {"query": query, "limit": 5}
            if agent_id:
                tool_input["agentId"] = agent_id
        elif name == "agent_status":
            output = tool_agent_status(org_id, settings, agent_id=agent_id)
            tool_input = {"agentId": agent_id} if agent_id else {}
        elif name == "connector_status":
            output = tool_connector_status(org_id, settings)
            tool_input = {}
        elif name == "workflow_runs":
            output = tool_workflow_runs(org_id, settings, status_filter=status_filter)
            tool_input = {"limit": 10}
            if status_filter:
                tool_input["status"] = status_filter
        elif name == "analytics":
            output = tool_analytics(org_id, settings, user_id=user_id)
            tool_input = {"windowDays": 7}
        elif name == "search_web":
            output = await tool_search_web(query, settings)
            tool_input = {"query": query}
        elif name == "generate_document":
            output = await tool_generate_document(org_id, query, settings)
            tool_input = {"topic": query[:200]}
        elif name == "run_agent_task":
            output = await tool_run_agent_task(
                org_id,
                query,
                settings,
                agent_id=agent_id,
                user_id=user_id,
            )
            tool_input = {"task": query[:200]}
            if agent_id:
                tool_input["agentId"] = agent_id
        elif name == "create_workflow":
            output = tool_create_workflow(org_id, query, settings, user_id=user_id)
            tool_input = {"name": _draft_workflow_name(query)}
        elif name == "create_agent":
            output = tool_create_agent(org_id, query, settings, user_id=user_id)
            tool_input = {"name": _draft_workflow_name(query)}
        else:
            continue

        results.append(
            {
                "name": name,
                "displayName": TOOL_DISPLAY_NAMES[name],
                "input": tool_input,
                "output": output,
            }
        )
    return results
