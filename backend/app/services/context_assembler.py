"""Parallel context assembly for intelligence router endpoints."""
from __future__ import annotations

from time import perf_counter
from types import SimpleNamespace
from typing import Any

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.services.company_intelligence_orchestrator import get_company_intelligence_orchestrator
from app.services.unified_retrieval_service import RetrievalScopes, get_unified_retrieval_service
from app.services.research_service import get_research_service
from app.workflows.repository import get_supabase_client

logger = get_logger(__name__)


class ContextAssembler:
    """
    Assembles context via UnifiedRetrievalService + domain policy (router parity with assistant chat).
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    async def assemble(
        self,
        org_id: str,
        user_id: str,
        request: str,
        classification: dict[str, Any],
        *,
        agent: dict[str, Any] | None = None,
        assignments: list[dict[str, Any]] | None = None,
        client: Any | None = None,
        environment_name: str = "production",
    ) -> dict[str, Any]:
        db_client = client or get_supabase_client(self.settings)
        agent_payload = agent or {"id": "router", "name": "Intelligence Router"}
        strict_mode = bool(classification.get("strict_assignment_mode"))

        started = perf_counter()
        retrieval_started = perf_counter()
        retrieval_ok = True
        try:
            bundle = await get_unified_retrieval_service().retrieve(
                org_id=org_id,
                query=request,
                client=db_client,
                agent=agent_payload,
                parameters={
                    "classification": classification,
                    "knowledge_assignments": assignments or [],
                    "strict_assignment_mode": strict_mode,
                    "rag_top_k": 8,
                },
                environment_name=environment_name,
                user_id=user_id,
                scopes=RetrievalScopes(knowledge=True, org_context=True, agent_memory=True),
            )
        except Exception as exc:  # noqa: BLE001
            retrieval_ok = False
            logger.warning("context_assembler_retrieve_failed error_type=%s", type(exc).__name__)
            bundle = SimpleNamespace(
                rag_sources=[],
                memory_context={},
                graph_context={},
                sources=[],
                org_context={},
                retrieval_plan={},
                retrieval_effectiveness={},
            )

        retrieval_ms = (perf_counter() - retrieval_started) * 1000
        rag_context: list[dict[str, Any]] = []
        for source in bundle.rag_sources:
            rag_context.append(
                {
                    "content": str(source.get("content") or "")[:500],
                    "documentId": source.get("document_id"),
                    "score": source.get("score"),
                    "provenance": source.get("provenance"),
                    "match_tier": source.get("match_tier"),
                }
            )

        company_started = perf_counter()
        try:
            company_intelligence = await get_company_intelligence_orchestrator().get_context_for_prompt(org_id)
        finally:
            company_ms = (perf_counter() - company_started) * 1000
        external_context: dict[str, Any] = {}
        research_ms = 0.0
        if classification.get("requires_web_search"):
            research_started = perf_counter()
            try:
                external_context = await get_research_service(self.settings).research(
                    org_id,
                    request,
                    depth="standard",
                )
            finally:
                research_ms = (perf_counter() - research_started) * 1000
        logger.info(
            "eco003_context_stage_timing retrieval_ms=%.3f company_ms=%.3f research_ms=%.3f total_ms=%.3f retrieval_ok=%s research_requested=%s",
            retrieval_ms, company_ms, research_ms, (perf_counter() - started) * 1000,
            retrieval_ok, bool(classification.get("requires_web_search")),
        )

        return {
            "rag_context": rag_context,
            "memory_context": bundle.memory_context,
            "company_intelligence": company_intelligence,
            "graph_context": bundle.graph_context,
            "external_context": external_context,
            "user_id": user_id,
            "retrieval_plan": bundle.retrieval_plan,
            "retrieval_effectiveness": bundle.retrieval_effectiveness,
            "sources": bundle.sources,
            "org_context": bundle.org_context,
        }


_context_assembler: ContextAssembler | None = None


def get_context_assembler(settings: Settings | None = None) -> ContextAssembler:
    global _context_assembler
    if _context_assembler is None or settings is not None:
        _context_assembler = ContextAssembler(settings)
    return _context_assembler
