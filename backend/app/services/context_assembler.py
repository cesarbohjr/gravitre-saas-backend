"""Parallel context assembly for intelligence router endpoints."""
from __future__ import annotations

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
            logger.warning("context_assembler_retrieve_failed org_id=%s error=%s", org_id, exc)
            bundle = SimpleNamespace(
                rag_sources=[],
                memory_context={},
                graph_context={},
                sources=[],
                org_context={},
                retrieval_plan={},
                retrieval_effectiveness={},
            )

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

        company_intelligence = await get_company_intelligence_orchestrator().get_context_for_prompt(org_id)
        external_context: dict[str, Any] = {}
        if classification.get("requires_web_search"):
            external_context = await get_research_service(self.settings).research(
                org_id,
                request,
                depth="standard",
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
