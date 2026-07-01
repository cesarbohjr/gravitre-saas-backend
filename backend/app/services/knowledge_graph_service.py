"""Unified one-hop knowledge graph query interface over org_entity_relationships (v6)."""
from __future__ import annotations

import json
import re
from typing import Any

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.services.entity_relationship_service import get_related_entities
from app.services.model_router import TaskType, get_model_router
from app.workflows.repository import get_supabase_client

logger = get_logger(__name__)

SCOPE_NOTE = (
    "One-hop traversal only over org_entity_relationships. "
    "No multi-hop inference or fabricated edges."
)


class KnowledgeGraphService:
    """
    Unified query interface over org_entity_relationships.
    One hop only — v6's deliberate scope boundary is permanent.
    """

    async def explain_entity(
        self,
        org_id: str,
        entity_type: str,
        entity_id: str,
        *,
        settings: Settings | None = None,
        client: Any | None = None,
    ) -> dict[str, Any]:
        active = settings or get_settings()
        db = client or get_supabase_client(active)
        related = await get_related_entities(
            org_id,
            entity_type,
            entity_id,
            max_results=8,
            settings=active,
            client=db,
        )
        signals = (
            db.table("optimization_suggestions")
            .select("id, suggestion_type, title, status, estimated_impact")
            .eq("org_id", org_id)
            .eq("status", "pending_review")
            .limit(20)
            .execute()
            .data
            or []
        )
        entity_signals = [
            row
            for row in signals
            if entity_id in json.dumps(row.get("evidence") or {})
            or entity_type.lower() in str(row.get("title") or "").lower()
        ][:5]
        return {
            "entityType": entity_type,
            "entityId": entity_id,
            "relatedEntities": related,
            "businessSignals": entity_signals,
            "scopeNote": SCOPE_NOTE,
            "hopLimit": 1,
        }

    async def answer_business_question(
        self,
        org_id: str,
        question: str,
        *,
        settings: Settings | None = None,
        client: Any | None = None,
    ) -> dict[str, Any]:
        """LLM identifies entity only; graph traversal is deterministic."""
        active = settings or get_settings()
        db = client or get_supabase_client(active)
        router = get_model_router()
        prompt = (
            "Identify the primary business entity referenced in the question. "
            "Return JSON only: {\"entity_type\": string, \"entity_id\": string}. "
            "Use entity_type from: deal, contact, company, workflow, agent, glossary_term, query_cluster. "
            "If unknown, use entity_type=unknown and entity_id=unknown.\n\n"
            f"Question: {question}"
        )
        entity_type = "unknown"
        entity_id = "unknown"
        try:
            response = await router.complete(
                TaskType.CLASSIFICATION,
                prompt=prompt,
                system_prompt="You extract entity references for graph lookup only.",
                org_id=org_id,
                max_tokens=120,
                temperature=0.0,
            )
            raw = (response.content or "").strip()
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if match:
                parsed = json.loads(match.group(0))
                entity_type = str(parsed.get("entity_type") or "unknown")
                entity_id = str(parsed.get("entity_id") or "unknown")
        except Exception as exc:  # noqa: BLE001
            logger.debug("knowledge_graph_entity_identify_failed org_id=%s error=%s", org_id, exc)

        if entity_type == "unknown" or entity_id == "unknown":
            return {
                "status": "insufficient_entity_match",
                "question": question,
                "scopeNote": SCOPE_NOTE,
                "message": "Could not identify a specific entity for graph lookup.",
            }

        explanation = await self.explain_entity(
            org_id,
            entity_type,
            entity_id,
            settings=active,
            client=db,
        )
        return {
            "status": "ok",
            "question": question,
            "identifiedEntity": {"entityType": entity_type, "entityId": entity_id},
            "explanation": explanation,
            "scopeNote": SCOPE_NOTE,
        }


_knowledge_graph_service: KnowledgeGraphService | None = None


def get_knowledge_graph_service() -> KnowledgeGraphService:
    global _knowledge_graph_service
    if _knowledge_graph_service is None:
        _knowledge_graph_service = KnowledgeGraphService()
    return _knowledge_graph_service
