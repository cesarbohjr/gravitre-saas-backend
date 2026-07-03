"""Reference-first provenance and memory lineage for agent knowledge."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.services.agent_memory_service import ensure_agent_in_org

logger = get_logger(__name__)


class AgentKnowledgeProvenanceService:
    """Explain why an agent knows something — references only, no raw payloads."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def explain_memory(
        self,
        client: Any,
        org_id: str,
        agent_id: str,
        memory_id: str,
    ) -> dict[str, Any]:
        ensure_agent_in_org(client, org_id, agent_id)
        row = (
            client.table("agent_memories")
            .select("*")
            .eq("org_id", org_id)
            .eq("agent_id", agent_id)
            .eq("id", memory_id)
            .maybe_single()
            .execute()
        )
        if not row.data:
            return {"found": False, "message": "Memory not found for this agent."}
        memory = row.data
        provenance = memory.get("provenance") if isinstance(memory.get("provenance"), dict) else {}
        return {
            "found": True,
            "memoryId": memory_id,
            "summary": memory.get("content"),
            "sourceSystem": provenance.get("source_system") or provenance.get("sourceSystem"),
            "sourceTitle": provenance.get("source_title") or provenance.get("sourceTitle"),
            "sourceSection": provenance.get("source_section") or provenance.get("sourceSection"),
            "externalUrl": provenance.get("external_url") or provenance.get("externalUrl"),
            "lastSyncedAt": provenance.get("last_synced_at") or provenance.get("lastSyncedAt"),
            "confidence": provenance.get("confidence_score") or memory.get("confidence"),
            "freshness": provenance.get("freshness_score") or provenance.get("freshnessScore"),
            "permissions": provenance.get("permission_scope") or provenance.get("permissionScope") or {},
            "howLearned": provenance.get("how_learned") or provenance.get("howLearned") or "Promoted from approved retrieval context.",
            "provenanceChain": provenance.get("provenance_chain") or provenance.get("provenanceChain") or [],
            "referenceOnly": provenance.get("reference_only", True),
        }

    def explain_provenance(
        self,
        client: Any,
        org_id: str,
        agent_id: str,
        assignment_id: str,
    ) -> dict[str, Any]:
        ensure_agent_in_org(client, org_id, agent_id)
        assignment = None
        try:
            row = (
                client.table("agent_knowledge_assignments")
                .select("*")
                .eq("org_id", org_id)
                .eq("agent_id", agent_id)
                .eq("id", assignment_id)
                .maybe_single()
                .execute()
            )
            assignment = row.data
        except Exception:  # noqa: BLE001
            assignment = None

        refs = self._load_references(client, org_id, agent_id, limit=100)
        scoped = [ref for ref in refs if str(ref.get("assignment_id") or "") == assignment_id]
        if not scoped:
            scoped = refs[:5]

        return {
            "assignmentId": assignment_id,
            "found": bool(assignment or scoped),
            "label": (assignment or {}).get("label"),
            "sourceType": (assignment or {}).get("source_type"),
            "freshnessStatus": (assignment or {}).get("freshness_status") or "unknown",
            "lastSyncedAt": (assignment or {}).get("last_synced_at"),
            "referenceOnly": True,
            "references": [
                {
                    "id": ref.get("id"),
                    "title": ref.get("source_title"),
                    "sourceSystem": ref.get("source_system"),
                    "externalUrl": ref.get("external_url"),
                    "freshnessScore": ref.get("freshness_score"),
                    "lastSyncedAt": ref.get("last_synced_at"),
                    "summary": str(ref.get("memory_summary") or "")[:240],
                }
                for ref in scoped
            ],
            "provenanceChain": [
                step
                for ref in scoped
                for step in (ref.get("provenance_chain") or [])
            ],
        }

    def list_lineage(
        self,
        client: Any,
        org_id: str,
        agent_id: str,
        *,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        ensure_agent_in_org(client, org_id, agent_id)
        refs = self._load_references(client, org_id, agent_id, limit=limit)
        memories = (
            client.table("agent_memories")
            .select("id, content, category, provenance, created_at")
            .eq("org_id", org_id)
            .eq("agent_id", agent_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        lineage: list[dict[str, Any]] = []
        for ref in refs:
            lineage.append(
                {
                    "kind": "reference",
                    "id": ref.get("id"),
                    "title": ref.get("source_title"),
                    "sourceSystem": ref.get("source_system"),
                    "externalUrl": ref.get("external_url"),
                    "freshnessScore": ref.get("freshness_score"),
                    "lastSyncedAt": ref.get("last_synced_at"),
                    "referenceOnly": ref.get("reference_only", True),
                }
            )
        for mem in memories.data or []:
            prov = mem.get("provenance") if isinstance(mem.get("provenance"), dict) else {}
            lineage.append(
                {
                    "kind": "memory",
                    "id": mem.get("id"),
                    "title": prov.get("source_title") or (str(mem.get("content") or "")[:80]),
                    "sourceSystem": prov.get("source_system"),
                    "externalUrl": prov.get("external_url"),
                    "freshnessScore": prov.get("freshness_score"),
                    "lastSyncedAt": prov.get("last_synced_at"),
                    "referenceOnly": prov.get("reference_only", True),
                }
            )
        return lineage[:limit]

    def upsert_reference(
        self,
        client: Any,
        org_id: str,
        agent_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Store reference metadata + summary only — never raw document bodies."""
        ensure_agent_in_org(client, org_id, agent_id)
        summary = str(payload.get("memory_summary") or payload.get("summary") or "").strip()
        if not summary:
            raise ValueError("memory_summary required")
        if len(summary) > 8000:
            summary = summary[:8000]
        row = {
            "org_id": org_id,
            "agent_id": agent_id,
            "assignment_id": payload.get("assignment_id"),
            "source_system": payload.get("source_system") or payload.get("sourceSystem") or "unknown",
            "connector_id": payload.get("connector_id"),
            "external_object_id": str(payload.get("external_object_id") or payload.get("externalObjectId") or ""),
            "external_url": payload.get("external_url") or payload.get("externalUrl"),
            "source_title": payload.get("source_title") or payload.get("sourceTitle") or "Reference",
            "source_type": payload.get("source_type") or payload.get("sourceType") or "reference",
            "source_section": payload.get("source_section") or payload.get("sourceSection"),
            "source_updated_at": payload.get("source_updated_at"),
            "last_synced_at": payload.get("last_synced_at") or datetime.now(timezone.utc).isoformat(),
            "last_verified_at": payload.get("last_verified_at"),
            "confidence_score": payload.get("confidence_score", 0.75),
            "freshness_score": payload.get("freshness_score", 0.75),
            "permission_scope": payload.get("permission_scope") or {},
            "provenance_chain": payload.get("provenance_chain") or [],
            "memory_type": payload.get("memory_type") or "reference",
            "memory_summary": summary,
            "embedding_reference": payload.get("embedding_reference"),
            "graph_entity_ids": payload.get("graph_entity_ids") or [],
            "reference_only": True,
            "metadata": payload.get("metadata") or {},
        }
        try:
            result = (
                client.table("agent_knowledge_references")
                .upsert(row, on_conflict="org_id,agent_id,source_system,external_object_id")
                .execute()
            )
            return result.data[0] if result.data else row
        except Exception as exc:  # noqa: BLE001
            logger.debug("reference_upsert_skipped agent=%s error=%s", agent_id, exc)
            return row

    def mark_stale_for_assignment(
        self,
        client: Any,
        org_id: str,
        agent_id: str,
        assignment_id: str,
        *,
        reason: str,
    ) -> int:
        try:
            result = (
                client.table("agent_knowledge_references")
                .update(
                    {
                        "freshness_score": 0.2,
                        "metadata": {"stale_reason": reason},
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    }
                )
                .eq("org_id", org_id)
                .eq("agent_id", agent_id)
                .eq("assignment_id", assignment_id)
                .execute()
            )
            return len(result.data or [])
        except Exception:  # noqa: BLE001
            return 0

    @staticmethod
    def _load_references(client: Any, org_id: str, agent_id: str, *, limit: int) -> list[dict[str, Any]]:
        try:
            result = (
                client.table("agent_knowledge_references")
                .select("*")
                .eq("org_id", org_id)
                .eq("agent_id", agent_id)
                .order("updated_at", desc=True)
                .limit(limit)
                .execute()
            )
            return list(result.data or [])
        except Exception:  # noqa: BLE001
            return []


_service: AgentKnowledgeProvenanceService | None = None


def get_agent_knowledge_provenance_service(settings: Settings | None = None) -> AgentKnowledgeProvenanceService:
    global _service
    if _service is None or settings is not None:
        _service = AgentKnowledgeProvenanceService(settings)
    return _service
