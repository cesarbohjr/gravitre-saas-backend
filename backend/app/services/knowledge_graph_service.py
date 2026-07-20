"""Unified knowledge graph query interface over org_entity_relationships (v6)."""
from __future__ import annotations

import json
import re
from collections import deque
from datetime import datetime, timezone
from typing import Any

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.services.confidence_honesty import (
    CONFIDENCE_SOURCE_TYPE_PRIOR,
    KG_BLEND_NOTE,
    label_confidence,
)
from app.services.entity_relationship_service import get_related_entities
from app.services.model_router import TaskType, get_model_router
from app.workflows.repository import get_supabase_client

logger = get_logger(__name__)

ONE_HOP_SCOPE_NOTE = (
    "One-hop traversal only over org_entity_relationships. "
    "No multi-hop inference or fabricated edges."
)

MULTI_HOP_SCOPE_NOTE = (
    "Bounded multi-hop traversal over org_entity_relationships only. "
    "Confidence decays per hop; edges below minimum confidence are excluded. "
    "No fabricated edges."
)


class KnowledgeGraphService:
    """
    Unified query interface over org_entity_relationships.
    One-hop explain/answer methods are unchanged (v6 boundary).
    Multi-hop traversal is bounded (max 3 hops) with confidence decay.
    """

    MAX_HOPS = 3
    CONFIDENCE_DECAY_PER_HOP = 0.3
    MIN_TRAVERSAL_CONFIDENCE = 0.2

    # Module C / STA-331: static type priors are estimates, not learned edge confidence.
    # Kept for traversal blending until Module A outcome volume can season real weights.
    _TYPE_RELIABILITY_PRIOR: dict[str, float] = {
        "associated-department": 0.85,
        "referenced-by-agent": 0.8,
        "co-occurs-with": 0.65,
        "tracked-by": 0.75,
        "observed-in": 0.7,
        "belongs-to": 0.8,
        "influenced-by": 0.72,
        "reports_to": 0.82,
        "blocked_by": 0.78,
        "contributes_to": 0.74,
        "impacts": 0.76,
        "references": 0.7,
    }
    # Backward-compatible alias for any external references.
    _RELATIONSHIP_RELIABILITY = _TYPE_RELIABILITY_PRIOR

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
            "scopeNote": ONE_HOP_SCOPE_NOTE,
            "hopLimit": 1,
            "advisory_only": True,
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
                "scopeNote": ONE_HOP_SCOPE_NOTE,
                "message": "Could not identify a specific entity for graph lookup.",
                "advisory_only": True,
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
            "scopeNote": ONE_HOP_SCOPE_NOTE,
            "advisory_only": True,
        }

    def _client(self, settings: Settings | None, client: Any | None) -> Any:
        active = settings or get_settings()
        return client or get_supabase_client(active)

    async def score_relationship(
        self,
        org_id: str,
        source_entity_id: str,
        target_entity_id: str,
        *,
        settings: Settings | None = None,
        client: Any | None = None,
    ) -> dict[str, Any]:
        """Score a relationship from evidence_count, recency, and type reliability prior.

        Returns provenance fields so callers cannot treat the static prior as a
        learned confidence score (Module C / STA-331).
        """
        db = self._client(settings, client)
        rows = (
            db.table("org_entity_relationships")
            .select("*")
            .eq("org_id", org_id)
            .eq("source_entity_id", source_entity_id)
            .eq("target_entity_id", target_entity_id)
            .limit(5)
            .execute()
            .data
            or []
        )
        reverse_rows = (
            db.table("org_entity_relationships")
            .select("*")
            .eq("org_id", org_id)
            .eq("source_entity_id", target_entity_id)
            .eq("target_entity_id", source_entity_id)
            .limit(5)
            .execute()
            .data
            or []
        )
        rows = rows + reverse_rows
        if not rows:
            return {
                **label_confidence(0.0, source=CONFIDENCE_SOURCE_TYPE_PRIOR, is_estimate=True),
                "note": KG_BLEND_NOTE,
            }
        best = 0.0
        now = datetime.now(timezone.utc)
        for row in rows:
            # Stored edge confidence (entity_relationship_builder) is itself an estimate.
            base = float(row.get("confidence") or 0)
            evidence = int(row.get("evidence_count") or 0)
            rel_type = str(row.get("relationship_type") or "")
            reliability = self._TYPE_RELIABILITY_PRIOR.get(rel_type, 0.6)
            evidence_boost = min(0.15, evidence * 0.02)
            recency_factor = 1.0
            observed = row.get("last_observed_at") or row.get("updated_at")
            if observed:
                try:
                    observed_dt = datetime.fromisoformat(str(observed).replace("Z", "+00:00"))
                    age_days = max(0.0, (now - observed_dt).total_seconds() / 86400)
                    recency_factor = max(0.5, 1.0 - (age_days / 365.0) * 0.3)
                except ValueError:
                    pass
            # Both inputs estimated — blend is not more authoritative than either alone.
            score = min(1.0, (base * 0.5 + reliability * 0.35 + evidence_boost) * recency_factor)
            best = max(best, score)
        return {
            **label_confidence(round(best, 4), source=CONFIDENCE_SOURCE_TYPE_PRIOR, is_estimate=True),
            "note": KG_BLEND_NOTE,
        }

    async def traverse_multi_hop(
        self,
        org_id: str,
        start_entity_type: str,
        start_entity_id: str,
        relationship_types: list[str] | None = None,
        max_hops: int = 2,
        *,
        settings: Settings | None = None,
        client: Any | None = None,
    ) -> dict[str, Any]:
        max_hops = min(max(1, int(max_hops)), self.MAX_HOPS)
        db = self._client(settings, client)
        allowed_types = set(relationship_types or [])
        queue: deque[tuple[str, str, str, int, float, list[str]]] = deque(
            [(start_entity_type, start_entity_id, "", 0, 1.0, [])]
        )
        visited: set[tuple[str, str]] = {(start_entity_type, start_entity_id)}
        paths: list[dict[str, Any]] = []

        while queue:
            entity_type, entity_id, rel_type, depth, confidence, chain = queue.popleft()
            if depth >= max_hops:
                continue
            neighbors = await get_related_entities(
                org_id,
                entity_type,
                entity_id,
                max_results=12,
                settings=settings or get_settings(),
                client=db,
            )
            for neighbor in neighbors:
                n_type = str(neighbor.get("entityType") or "")
                n_id = str(neighbor.get("entityId") or "")
                n_rel = str(neighbor.get("relationshipType") or "")
                if allowed_types and n_rel not in allowed_types:
                    continue
                edge_conf = float(neighbor.get("confidence") or 0)
                hop_conf = confidence * max(
                    edge_conf * (1.0 - self.CONFIDENCE_DECAY_PER_HOP * depth),
                    0.0,
                )
                if hop_conf < self.MIN_TRAVERSAL_CONFIDENCE:
                    continue
                key = (n_type, n_id)
                if key in visited:
                    continue
                visited.add(key)
                next_chain = chain + [f"{entity_type}:{entity_id} -[{n_rel}]-> {n_type}"]
                paths.append(
                    {
                        "entityType": n_type,
                        "entityId": n_id,
                        "hopDepth": depth + 1,
                        "confidence": round(hop_conf, 4),
                        "relationshipType": n_rel,
                        "pathSummary": " → ".join(next_chain[-3:]),
                    }
                )
                queue.append((n_type, n_id, n_rel, depth + 1, hop_conf, next_chain))

        return {
            "startEntityType": start_entity_type,
            "startEntityId": start_entity_id,
            "maxHopsRequested": max_hops,
            "maxHopsCap": self.MAX_HOPS,
            "paths": sorted(paths, key=lambda row: row["confidence"], reverse=True)[:25],
            "scope_note": MULTI_HOP_SCOPE_NOTE,
            "advisory_only": True,
        }

    async def get_graph_recommendations(
        self,
        org_id: str,
        entity_type: str,
        entity_id: str,
        recommendation_goal: str,
        *,
        settings: Settings | None = None,
        client: Any | None = None,
    ) -> list[dict[str, Any]]:
        traversal = await self.traverse_multi_hop(
            org_id,
            entity_type,
            entity_id,
            max_hops=2,
            settings=settings,
            client=client,
        )
        recommendations: list[dict[str, Any]] = []
        for path in traversal.get("paths") or []:
            recommendations.append(
                {
                    "goal": recommendation_goal,
                    "entityType": path.get("entityType"),
                    "entityId": path.get("entityId"),
                    "confidence": path.get("confidence"),
                    "reason": f"Connected within {path.get('hopDepth')} hop(s) for goal: {recommendation_goal}",
                    "advisory_only": True,
                    "approval_required": True,
                }
            )
        from app.services.decision_intelligence_service import get_decision_intelligence_service

        decision = await get_decision_intelligence_service(settings).recommend_next_action(
            org_id,
            f"{recommendation_goal} related to {entity_type}:{entity_id}",
        )
        for rec in (decision.get("recommendations") or [])[:3]:
            recommendations.append(
                {
                    "goal": recommendation_goal,
                    "action": rec.get("action"),
                    "confidence": rec.get("confidence"),
                    "reason": rec.get("reasoning"),
                    "advisory_only": True,
                    "approval_required": True,
                    "source": "DecisionIntelligenceService",
                }
            )
        return recommendations[:10]

    async def explain_graph_reasoning(
        self,
        org_id: str,
        traversal_result: dict[str, Any],
    ) -> str:
        _ = org_id
        paths = traversal_result.get("paths") or []
        max_depth = max((int(p.get("hopDepth") or 0) for p in paths), default=0)
        if not paths:
            return (
                "No additional graph connections met the confidence threshold. "
                f"Hop depth searched: up to {traversal_result.get('maxHopsRequested', 1)}. "
                "Confidence level: insufficient for recommendations."
            )
        top = paths[0]
        avg_conf = sum(float(p.get("confidence") or 0) for p in paths) / len(paths)
        return (
            f"Found {len(paths)} connected entities within {max_depth} hop(s) "
            f"at average confidence {avg_conf:.0%}. "
            f"Strongest connection: {top.get('entityType')} "
            f"(confidence {float(top.get('confidence') or 0):.0%}). "
            "Recommendations are advisory only and require human approval."
        )

    async def get_admin_summary(
        self,
        org_id: str,
        *,
        settings: Settings | None = None,
        client: Any | None = None,
    ) -> dict[str, Any]:
        db = self._client(settings, client)
        rel_rows = (
            db.table("org_entity_relationships")
            .select("confidence, source_entity_type, target_entity_type, relationship_type")
            .eq("org_id", org_id)
            .limit(5000)
            .execute()
            .data
            or []
        )
        entity_types: set[str] = set()
        relationship_types: set[str] = set()
        confidences: list[float] = []
        entities: set[str] = set()
        for row in rel_rows:
            relationship_types.add(str(row.get("relationship_type") or ""))
            for key in ("source_entity_type", "target_entity_type"):
                et = str(row.get(key) or "")
                if et:
                    entity_types.add(et)
            sid = str(row.get("source_entity_id") or "")
            tid = str(row.get("target_entity_id") or "")
            if sid:
                entities.add(sid)
            if tid:
                entities.add(tid)
            confidences.append(float(row.get("confidence") or 0))
        avg_conf = round(sum(confidences) / len(confidences), 4) if confidences else 0.0
        return {
            "entity_count": len(entities),
            "relationship_count": len(rel_rows),
            "max_traversal_hops": self.MAX_HOPS,
            "avg_relationship_confidence": avg_conf,
            "entity_types": sorted(entity_types),
            "relationship_types": sorted(relationship_types),
            "scope_note": MULTI_HOP_SCOPE_NOTE,
            "advisory_only": True,
        }


_knowledge_graph_service: KnowledgeGraphService | None = None


def get_knowledge_graph_service() -> KnowledgeGraphService:
    global _knowledge_graph_service
    if _knowledge_graph_service is None:
        _knowledge_graph_service = KnowledgeGraphService()
    return _knowledge_graph_service
