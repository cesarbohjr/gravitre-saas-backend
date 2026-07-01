"""Parallel context assembly for intelligence router endpoints."""
from __future__ import annotations

import asyncio
from typing import Any

from app.config import Settings, get_settings
from app.services.company_intelligence_orchestrator import get_company_intelligence_orchestrator
from app.services.hybrid_memory_service import get_hybrid_memory_service
from app.services.knowledge_graph_service import get_knowledge_graph_service
from app.services.rag_service import get_rag_service
from app.services.research_service import get_research_service


class ContextAssembler:
    """
    Assembles RAG, memory, company intelligence, graph, and optional web context in parallel.
    Consumed by IntelligenceRouter — AgentIntelligence continues to use UnifiedRetrievalService.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    async def assemble(
        self,
        org_id: str,
        user_id: str,
        request: str,
        classification: dict[str, Any],
    ) -> dict[str, Any]:
        tasks: list[Any] = [
            get_rag_service().query(org_id=org_id, query=request, top_k=8),
            get_hybrid_memory_service(self.settings).query_all_memory(
                org_id=org_id,
                agent_id=None,
                query=request,
            ),
            get_company_intelligence_orchestrator().get_context_for_prompt(org_id),
        ]
        include_graph = bool(classification.get("requires_graph"))
        include_web = bool(classification.get("requires_web_search"))
        if include_graph:
            tasks.append(get_knowledge_graph_service().answer_business_question(org_id, request))
        if include_web:
            tasks.append(get_research_service(self.settings).research(org_id, request, depth="standard"))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        rag_result = results[0] if not isinstance(results[0], Exception) else None
        rag_context: list[dict[str, Any]] = []
        if rag_result is not None:
            for chunk in getattr(rag_result, "chunks", None) or []:
                rag_context.append(
                    {
                        "content": str(getattr(chunk, "content", "") or "")[:500],
                        "documentId": getattr(chunk, "document_id", None),
                        "score": getattr(chunk, "score", None),
                    }
                )

        memory_context = results[1] if not isinstance(results[1], Exception) else {}
        company_intelligence = results[2] if not isinstance(results[2], Exception) else ""
        graph_context = {}
        external_context = {}
        idx = 3
        if include_graph and len(results) > idx:
            graph_context = results[idx] if not isinstance(results[idx], Exception) else {}
            idx += 1
        if include_web and len(results) > idx:
            external_context = results[idx] if not isinstance(results[idx], Exception) else {}

        return {
            "rag_context": rag_context,
            "memory_context": memory_context,
            "company_intelligence": company_intelligence,
            "graph_context": graph_context,
            "external_context": external_context,
            "user_id": user_id,
        }


_context_assembler: ContextAssembler | None = None


def get_context_assembler(settings: Settings | None = None) -> ContextAssembler:
    global _context_assembler
    if _context_assembler is None or settings is not None:
        _context_assembler = ContextAssembler(settings)
    return _context_assembler
