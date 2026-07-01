"""Multi-source research coordinator — advisory only."""
from __future__ import annotations

from typing import Any

from app.config import Settings, get_settings
from app.services.knowledge_graph_service import get_knowledge_graph_service
from app.services.rag_service import get_rag_service


class AutonomousResearchService:
    """
    Combines RAG, optional web search, knowledge graph, and connector context.
    Research outputs are always advisory_only for human review.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    async def research(
        self,
        org_id: str,
        topic: str,
        depth: str = "standard",
    ) -> dict[str, Any]:
        findings: list[dict[str, Any]] = []
        sources: list[dict[str, Any]] = []
        gaps: list[str] = []

        rag = get_rag_service()
        rag_result = await rag.query(org_id=org_id, query=topic, top_k=8 if depth == "deep" else 5)
        for chunk in rag_result.chunks or []:
            findings.append(
                {
                    "type": "org_knowledge",
                    "summary": str(getattr(chunk, "content", "") or "")[:400],
                    "source": getattr(chunk, "document_id", None) or getattr(chunk, "source_document_id", None),
                }
            )
            sources.append({"type": "rag", "id": getattr(chunk, "chunk_id", None)})

        if depth == "deep":
            graph = await get_knowledge_graph_service().answer_business_question(org_id, topic)
            if graph.get("status") == "ok":
                findings.append({"type": "graph_context", "summary": str(graph.get("explanation"))[:500]})
                sources.append({"type": "knowledge_graph"})

        if not findings:
            gaps.append("No org knowledge matched this topic yet.")

        confidence = min(0.9, 0.35 + 0.08 * len(findings))
        return {
            "findings": findings,
            "sources": sources,
            "confidence": round(confidence, 4),
            "gaps": gaps,
            "advisory_only": True,
            "depth": depth,
        }


_research_service: AutonomousResearchService | None = None


def get_research_service(settings: Settings | None = None) -> AutonomousResearchService:
    global _research_service
    if _research_service is None or settings is not None:
        _research_service = AutonomousResearchService(settings)
    return _research_service
