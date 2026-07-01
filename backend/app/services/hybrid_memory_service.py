"""Parallel query over episodic, graph, glossary, and cluster memory stores."""
from __future__ import annotations

import asyncio
from typing import Any

from app.config import Settings, get_settings
from app.services.query_normalization import normalize_query
from app.workflows.repository import get_supabase_client


class HybridMemoryService:
    """
    Unified query over agent_memories, org_entity_relationships,
    org_glossary_terms, and org_query_clusters.
    Does not replace individual stores — one entry point for prompts.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def _client(self) -> Any:
        return get_supabase_client(self.settings)

    async def _query_agent_memories(
        self,
        org_id: str,
        agent_id: str | None,
        query: str,
        top_k: int,
        client: Any,
    ) -> list[dict[str, Any]]:
        q = (
            client.table("agent_memories")
            .select("id, content, category, confidence, usage_count")
            .eq("org_id", org_id)
            .eq("is_active", True)
            .limit(top_k)
        )
        if agent_id:
            q = q.eq("agent_id", agent_id)
        rows = q.execute().data or []
        needle = normalize_query(query).lower()
        scored = []
        for row in rows:
            content = str(row.get("content") or "")
            score = 1.0 if needle and needle in normalize_query(content).lower() else 0.2
            scored.append({**row, "score": score})
        scored.sort(key=lambda item: float(item.get("score") or 0), reverse=True)
        return scored[:top_k]

    async def _query_entity_relationships(
        self,
        org_id: str,
        query: str,
        client: Any,
    ) -> list[dict[str, Any]]:
        rows = (
            client.table("org_entity_relationships")
            .select("source_entity_type, source_entity_id, target_entity_type, target_entity_id, relationship_type, confidence")
            .eq("org_id", org_id)
            .limit(50)
            .execute()
            .data
            or []
        )
        needle = normalize_query(query).lower()
        matches = [
            row
            for row in rows
            if needle
            and needle in " ".join(
                str(row.get(key) or "")
                for key in (
                    "source_entity_type",
                    "target_entity_type",
                    "relationship_type",
                )
            ).lower()
        ]
        return matches[:10]

    async def _query_glossary_terms(
        self,
        org_id: str,
        query: str,
        client: Any,
    ) -> list[dict[str, Any]]:
        rows = (
            client.table("org_glossary_terms")
            .select("term, term_type, associated_department, status")
            .eq("org_id", org_id)
            .limit(100)
            .execute()
            .data
            or []
        )
        needle = normalize_query(query).lower()
        return [row for row in rows if needle and needle in str(row.get("term") or "").lower()][:10]

    async def query_all_memory(
        self,
        org_id: str,
        agent_id: str | None,
        query: str,
        top_k: int = 5,
    ) -> dict[str, Any]:
        client = self._client()
        results = await asyncio.gather(
            self._query_agent_memories(org_id, agent_id, query, top_k, client),
            self._query_entity_relationships(org_id, query, client),
            self._query_glossary_terms(org_id, query, client),
            return_exceptions=True,
        )
        cluster_rows = (
            client.table("org_query_clusters")
            .select("cluster_label, representative_queries, member_query_count")
            .eq("org_id", org_id)
            .limit(top_k)
            .execute()
            .data
            or []
        )
        return {
            "episodic_memories": results[0] if not isinstance(results[0], Exception) else [],
            "graph_context": results[1] if not isinstance(results[1], Exception) else [],
            "vocabulary": results[2] if not isinstance(results[2], Exception) else [],
            "query_clusters": cluster_rows,
        }


_hybrid_memory_service: HybridMemoryService | None = None


def get_hybrid_memory_service(settings: Settings | None = None) -> HybridMemoryService:
    global _hybrid_memory_service
    if _hybrid_memory_service is None or settings is not None:
        _hybrid_memory_service = HybridMemoryService(settings)
    return _hybrid_memory_service
