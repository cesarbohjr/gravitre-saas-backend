"""UnifiedRetrievalService — single internal+org retrieval path for intelligence runs."""
from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.services.org_context_service import get_org_context_service
from app.services.agent_memory_service import build_task_retrieval_context, format_retrieval_prompt_section
from app.services.rag_service import RAGService, RAGResponse, get_rag_service

logger = get_logger(__name__)


class RetrievalScopes(BaseModel):
    """Which retrieval sources to include in a bundle."""

    knowledge: bool = True
    org_context: bool = True
    agent_memory: bool = True


class UnifiedRetrievalBundle(BaseModel):
    """Normalized retrieval output for AgentIntelligence / orchestrator."""

    rag_sources: list[dict[str, Any]] = Field(default_factory=list)
    rag_section: str = ""
    org_context: dict[str, Any] = Field(default_factory=dict)
    memory_context: dict[str, Any] = Field(default_factory=dict)
    memory_section: str = ""
    sources: list[dict[str, Any]] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    graph_context: dict[str, Any] = Field(default_factory=dict)
    retrieval_plan: dict[str, Any] = Field(default_factory=dict)
    retrieval_effectiveness: dict[str, Any] = Field(default_factory=dict)


class UnifiedRetrievalService:
    """Consolidates RAG chunks, org snapshot, and agent memory for agent tasks."""

    def __init__(self, settings: Settings | None = None, rag_service: RAGService | None = None) -> None:
        self.settings = settings or get_settings()
        self.rag_service = rag_service or get_rag_service()

    async def retrieve(
        self,
        *,
        org_id: str,
        query: str,
        client: Any,
        agent: dict[str, Any],
        parameters: dict[str, Any] | None = None,
        environment_name: str = "default",
        scopes: RetrievalScopes | None = None,
        user_id: str | None = None,
        message_id: str | None = None,
        reranking_enabled: bool | None = None,
    ) -> UnifiedRetrievalBundle:
        active_scopes = scopes or RetrievalScopes()
        params = parameters or {}
        agent = agent or {}
        agent_id = str(agent.get("id") or "")
        classification = params.get("classification") if isinstance(params.get("classification"), dict) else {}
        assignments = params.get("knowledge_assignments") or []
        strict_mode = bool(params.get("strict_assignment_mode"))

        from app.services.domain_retrieval_policy import build_retrieval_plan, should_fetch_graph

        retrieval_plan = build_retrieval_plan(
            classification,
            assignments,
            settings=self.settings,
            strict_assignment_mode=strict_mode,
        )

        org_context: dict[str, Any] = {}
        if active_scopes.org_context:
            org_context = get_org_context_service().get_snapshot(
                client,
                org_id,
                environment_name=environment_name,
                depth=str(params.get("org_context_depth") or "standard"),
                user_id=user_id,
            )

        memory_context: dict[str, Any] = {}
        memory_section = ""
        if active_scopes.agent_memory:
            memory_context = build_task_retrieval_context(
                self.settings,
                client,
                org_id=org_id,
                agent=agent,
                task=query,
                parameters=params,
            )
            memory_section = format_retrieval_prompt_section(memory_context)

        rag_sources: list[dict[str, Any]] = []
        rag_section = ""
        metrics: dict[str, Any] = {}
        if active_scopes.knowledge:
            try:
                top_k = int(params.get("rag_top_k") or self.settings.rag_top_k or 8)
                filters: dict[str, Any] = {"environment": environment_name}
                if reranking_enabled is False:
                    filters["disable_rerank"] = True
                rows, metrics = await self.rag_service.retrieve_hybrid_rows(
                    org_id,
                    query,
                    scope="agent",
                    top_k=top_k,
                    agent_id=agent_id or None,
                    message_id=message_id,
                    filters=filters,
                )
                rag_sources = [
                    {
                        "id": str(row.get("id") or row.get("chunk_id") or ""),
                        "document_id": row.get("document_id"),
                        "content": str(row.get("content") or "")[:500],
                        "score": float(row.get("score") or 0.0),
                        "source": str(row.get("title") or row.get("source_title") or row.get("source") or ""),
                        "title": row.get("title") or row.get("source_title"),
                        "metadata": row.get("metadata") if isinstance(row.get("metadata"), dict) else {},
                    }
                    for row in rows
                ]
                assignments = params.get("knowledge_assignments") or []
                if assignments:
                    from app.services.agent_knowledge_assignment_service import (
                        get_agent_knowledge_assignment_service,
                    )

                    assignment_svc = get_agent_knowledge_assignment_service()
                    rag_sources, missing = assignment_svc.filter_rag_sources(
                        rag_sources,
                        assignments,
                        plan=retrieval_plan,
                    )
                    metrics = dict(metrics or {})
                    metrics["assignment_scoped"] = True
                    metrics["assignment_match_count"] = len(
                        [row for row in rag_sources if row.get("match_tier") != "unassigned"]
                    )
                    if missing:
                        metrics["missing_assignments"] = missing
                elif retrieval_plan.active:
                    from app.services.domain_retrieval_policy import apply_source_score
                    from app.services.retrieval_provenance import build_from_rag_row

                    boosted = []
                    for source in rag_sources:
                        updated = dict(source)
                        tier = "unassigned"
                        updated["match_tier"] = tier
                        updated["score"] = apply_source_score(
                            float(updated.get("score") or 0.0),
                            updated,
                            retrieval_plan,
                            match_tier=tier,
                        )
                        updated["provenance"] = build_from_rag_row(updated, plan=retrieval_plan, match_tier=tier)
                        boosted.append(updated)
                    rag_sources = sorted(boosted, key=lambda row: float(row.get("score") or 0.0), reverse=True)
                metrics = dict(metrics or {})
                metrics["retrieval_policy"] = retrieval_plan.policy_version if retrieval_plan.active else "legacy"
                if rag_sources:
                    rag_section = (
                        "<knowledge_base>\n"
                        + json.dumps(
                            [
                                {
                                    "source": source.get("source"),
                                    "content": source.get("content", "")[:1200],
                                    "score": source.get("score"),
                                }
                                for source in rag_sources
                            ],
                            default=str,
                        )[:12000]
                        + "\n</knowledge_base>\n"
                    )
            except Exception as exc:  # noqa: BLE001
                logger.debug("unified_retrieval_knowledge_skipped org_id=%s error=%s", org_id, exc)
                metrics = {"fallback": "knowledge_unavailable", "error": str(exc)}

        sources: list[dict[str, Any]] = []
        for item in rag_sources:
            sources.append({"kind": "knowledge", **item})
        for key in ("memories", "patterns", "facts"):
            for row in memory_context.get(key) or []:
                if isinstance(row, dict):
                    from app.services.retrieval_provenance import build_from_memory_row

                    enriched = dict(row)
                    enriched["provenance"] = build_from_memory_row(enriched, plan=retrieval_plan)
                    sources.append({"kind": "memory", "category": key, **enriched})

        graph_context: dict[str, Any] = {}
        if should_fetch_graph(classification, retrieval_plan):
            try:
                from app.services.knowledge_graph_service import get_knowledge_graph_service
                from app.services.retrieval_provenance import build_from_graph_context

                graph_context = await get_knowledge_graph_service().answer_business_question(org_id, query)
                if isinstance(graph_context, dict) and graph_context:
                    graph_context["provenance"] = build_from_graph_context(graph_context, plan=retrieval_plan)
                    sources.append({"kind": "graph", **graph_context})
            except Exception as exc:  # noqa: BLE001
                logger.debug("unified_retrieval_graph_skipped org_id=%s error=%s", org_id, exc)

        from app.services.retrieval_provenance import summarize_retrieval_effectiveness

        retrieval_effectiveness = summarize_retrieval_effectiveness(
            sources,
            plan=retrieval_plan,
            classification=classification,
        )

        return UnifiedRetrievalBundle(
            rag_sources=rag_sources,
            rag_section=rag_section,
            org_context=org_context,
            memory_context=memory_context,
            memory_section=memory_section,
            sources=sources,
            metrics=metrics,
            graph_context=graph_context,
            retrieval_plan=retrieval_plan.to_params(),
            retrieval_effectiveness=retrieval_effectiveness,
        )

    async def retrieve_knowledge_rows(
        self,
        *,
        org_id: str,
        query: str,
        top_k: int = 10,
        environment_name: str = "default",
        agent_id: str | None = None,
        department_id: str | None = None,
        source_id: str | None = None,
        document_id: str | None = None,
        min_score: float | None = None,
        scope: str = "organization",
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Knowledge-only hybrid retrieval with BE-10 row shape for HTTP/workflow callers."""
        filters: dict[str, Any] = {"environment": environment_name}
        if source_id:
            filters["source_id"] = source_id
        if document_id:
            filters["document_id"] = document_id
        if department_id:
            filters["department_id"] = department_id
        active_scope = scope
        if agent_id and active_scope == "organization":
            active_scope = "agent"
        rows, metrics = await self.rag_service.retrieve_hybrid_rows(
            org_id,
            query,
            scope=active_scope,
            top_k=top_k,
            filters=filters,
            agent_id=agent_id,
        )
        mapped = [hybrid_row_to_be10_row(row) for row in rows]
        if min_score is not None:
            mapped = [row for row in mapped if float(row.get("score") or 0.0) >= min_score]
        return mapped, metrics

    async def query_knowledge(
        self,
        *,
        org_id: str,
        query: str,
        scope: str = "organization",
        top_k: int = 8,
        filters: dict[str, Any] | None = None,
        include_sources: bool = True,
        agent_id: str | None = None,
    ) -> RAGResponse:
        """RAG-enhanced query (retrieval + answer synthesis) via canonical service path."""
        return await self.rag_service.query(
            org_id=org_id,
            query=query,
            scope=scope,
            top_k=top_k,
            filters=filters,
            include_sources=include_sources,
            agent_id=agent_id,
        )


def hybrid_row_to_be10_row(row: dict[str, Any]) -> dict[str, Any]:
    """Map hybrid retrieval rows to BE-10 / workflow chunk dict shape."""
    chunk_id = str(row.get("chunk_id") or row.get("id") or "")
    source_title = str(row.get("source_title") or row.get("title") or "")
    return {
        "chunk_id": chunk_id,
        "content": str(row.get("content") or ""),
        "source_id": str(row.get("source_id") or ""),
        "source_title": source_title,
        "document_id": str(row.get("document_id") or ""),
        "document_title": row.get("document_title"),
        "chunk_index": int(row.get("chunk_index") or 0),
        "score": float(row.get("score") or 0.0),
    }


def be10_rows_to_workflow_chunks(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Map BE-10 rows to workflow rag_retrieve output chunk entries."""
    return [
        {
            "id": str(row["chunk_id"]),
            "text": row["content"],
            "source_id": str(row["source_id"]),
            "source_title": row.get("source_title") or "",
            "document_id": str(row["document_id"]),
            "document_title": row.get("document_title"),
            "chunk_index": row["chunk_index"],
            "score": round(float(row["score"]), 6),
        }
        for row in rows
    ]


_unified_retrieval_singleton: UnifiedRetrievalService | None = None


def get_unified_retrieval_service() -> UnifiedRetrievalService:
    global _unified_retrieval_singleton
    if _unified_retrieval_singleton is None:
        _unified_retrieval_singleton = UnifiedRetrievalService()
    return _unified_retrieval_singleton
