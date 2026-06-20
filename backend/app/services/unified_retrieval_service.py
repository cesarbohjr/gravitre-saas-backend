"""UnifiedRetrievalService — single internal+org retrieval path for intelligence runs."""
from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.services.org_context_service import get_org_context_service
from app.services.agent_memory_service import build_task_retrieval_context, format_retrieval_prompt_section
from app.services.rag_service import RAGService, get_rag_service

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
    ) -> UnifiedRetrievalBundle:
        active_scopes = scopes or RetrievalScopes()
        params = parameters or {}
        agent_id = str(agent.get("id") or "")

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
                chunks, metrics = await self.rag_service.retrieve_chunks(
                    org_id,
                    query,
                    scope="agent",
                    top_k=int(params.get("rag_top_k") or self.settings.rag_top_k or 8),
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
                    for chunk in chunks
                ]
                if chunks:
                    rag_section = (
                        "<knowledge_base>\n"
                        + json.dumps(
                            [
                                {
                                    "source": chunk.source,
                                    "content": chunk.content[:1200],
                                    "score": chunk.score,
                                }
                                for chunk in chunks
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
                    sources.append({"kind": "memory", "category": key, **row})

        return UnifiedRetrievalBundle(
            rag_sources=rag_sources,
            rag_section=rag_section,
            org_context=org_context,
            memory_context=memory_context,
            memory_section=memory_section,
            sources=sources,
            metrics=metrics,
        )


_unified_retrieval_singleton: UnifiedRetrievalService | None = None


def get_unified_retrieval_service() -> UnifiedRetrievalService:
    global _unified_retrieval_singleton
    if _unified_retrieval_singleton is None:
        _unified_retrieval_singleton = UnifiedRetrievalService()
    return _unified_retrieval_singleton
