"""Per-assignment knowledge sync with include/exclude rules."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.services.agent_knowledge_assignment_service import get_agent_knowledge_assignment_service
from app.services.agent_knowledge_provenance_service import get_agent_knowledge_provenance_service
from app.services.agent_memory_service import ensure_agent_in_org
from app.services.knowledge_source_types import connector_vendor_for_source_type, normalize_source_type
from app.services.knowledge_sync_service import parse_sync_interval

logger = get_logger(__name__)


class AgentKnowledgeSyncService:
    """Idempotent sync jobs per agent knowledge assignment."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._assignments = get_agent_knowledge_assignment_service(settings)
        self._provenance = get_agent_knowledge_provenance_service(settings)

    async def sync_assignment(
        self,
        client: Any,
        org_id: str,
        agent_id: str,
        assignment_id: str,
        *,
        actor_id: str | None = None,
    ) -> dict[str, Any]:
        ensure_agent_in_org(client, org_id, agent_id)
        assignment = self._get_assignment(client, org_id, agent_id, assignment_id)
        if not assignment:
            return {"success": False, "message": "Assignment not found"}
        if not assignment.get("enabled", True):
            return {"success": False, "message": "Assignment is disabled"}
        if not assignment.get("syncEnabled", assignment.get("sync_enabled", True)):
            return {"success": False, "message": "Sync is disabled for this assignment"}

        source_type = normalize_source_type(str(assignment.get("sourceType") or assignment.get("source_type") or ""))
        vendor = connector_vendor_for_source_type(source_type)

        if source_type == "knowledge_pack":
            result = await self._sync_knowledge_pack(client, org_id, agent_id, assignment)
        elif vendor == "hubspot":
            result = await self._sync_via_org_connector(client, org_id, agent_id, assignment, vendor="hubspot")
        elif vendor == "google_drive":
            result = await self._sync_drive_reference(client, org_id, agent_id, assignment)
        elif vendor in {"notion", "confluence", "zendesk"}:
            result = await self._sync_via_org_connector(client, org_id, agent_id, assignment, vendor=vendor)
        else:
            result = await self._sync_reference_stub(client, org_id, agent_id, assignment, vendor or source_type)

        now = datetime.now(timezone.utc).isoformat()
        freshness = "fresh" if result.get("success") else "stale"
        try:
            client.table("agent_knowledge_assignments").update(
                {
                    "last_synced_at": now,
                    "last_verified_at": now,
                    "freshness_status": freshness,
                    "confidence_score": 0.85 if result.get("success") else 0.35,
                    "updated_at": now,
                }
            ).eq("id", assignment_id).execute()
        except Exception as exc:  # noqa: BLE001
            logger.debug("assignment_sync_update_skipped id=%s error=%s", assignment_id, exc)

        result["assignmentId"] = assignment_id
        result["syncedAt"] = now
        result["freshnessStatus"] = freshness
        _ = actor_id
        return result

    def evaluate_rules(self, assignment: dict[str, Any], candidate: dict[str, Any]) -> bool:
        """Apply include/exclude/tag/age rules to a candidate object metadata dict."""
        name = str(candidate.get("name") or candidate.get("title") or "").lower()
        tags = {str(t).lower() for t in (candidate.get("tags") or [])}
        include = [str(r).lower() for r in (assignment.get("includeRules") or assignment.get("include_rules") or [])]
        exclude = [str(r).lower() for r in (assignment.get("excludeRules") or assignment.get("exclude_rules") or [])]
        required_tags = {str(t).lower() for t in (assignment.get("tagsRequired") or assignment.get("tags_required") or [])}
        excluded_tags = {str(t).lower() for t in (assignment.get("tagsExcluded") or assignment.get("tags_excluded") or [])}

        for pattern in exclude:
            if pattern and (pattern in name or self._match_pattern(pattern, name)):
                return False
        for blocked in ("hr", "legal", "payroll", "compensation", "private"):
            if blocked in name and any(blocked in (p or "") for p in exclude + list(excluded_tags)):
                return False
        if required_tags and not required_tags.intersection(tags):
            return False
        if excluded_tags.intersection(tags):
            return False
        if include:
            if not any(p in name or self._match_pattern(p, name) for p in include if p):
                return False

        policy = assignment.get("freshnessPolicy") or assignment.get("freshness_policy") or {}
        max_age = policy.get("max_age_days")
        if max_age and candidate.get("modified_at"):
            try:
                modified = datetime.fromisoformat(str(candidate["modified_at"]).replace("Z", "+00:00"))
                age_days = (datetime.now(timezone.utc) - modified).days
                if age_days > int(max_age):
                    return False
            except Exception:  # noqa: BLE001
                pass
        if policy.get("approved_only") and not candidate.get("approved", True):
            return False
        if policy.get("private_excluded") and candidate.get("is_private"):
            return False
        return True

    def assignment_is_due(self, assignment: dict[str, Any], *, now: datetime | None = None) -> bool:
        now = now or datetime.now(timezone.utc)
        freq = assignment.get("syncFrequency") or assignment.get("sync_frequency") or "daily"
        if str(freq).lower() == "manual":
            return False
        last = assignment.get("lastSyncedAt") or assignment.get("last_synced_at")
        if not last:
            return True
        try:
            last_dt = datetime.fromisoformat(str(last).replace("Z", "+00:00"))
            return now - last_dt >= parse_sync_interval(str(freq))
        except Exception:  # noqa: BLE001
            return True

    async def _sync_knowledge_pack(
        self,
        client: Any,
        org_id: str,
        agent_id: str,
        assignment: dict[str, Any],
    ) -> dict[str, Any]:
        pack_id = str(assignment.get("sourceId") or assignment.get("source_id") or "")
        self._provenance.upsert_reference(
            client,
            org_id,
            agent_id,
            {
                "assignment_id": assignment.get("id"),
                "source_system": "knowledge_pack",
                "external_object_id": pack_id,
                "source_title": assignment.get("label") or pack_id,
                "source_type": "knowledge_pack",
                "memory_summary": f"Approved knowledge pack '{assignment.get('label') or pack_id}' is assigned to this agent.",
                "confidence_score": 0.8,
                "freshness_score": 0.85,
                "provenance_chain": [{"step": "pack_assignment", "pack_id": pack_id}],
            },
        )
        return {"success": True, "message": "Knowledge pack reference registered.", "references": 1}

    async def _sync_drive_reference(
        self,
        client: Any,
        org_id: str,
        agent_id: str,
        assignment: dict[str, Any],
    ) -> dict[str, Any]:
        folder_id = str(assignment.get("sourceId") or assignment.get("source_id") or "")
        label = assignment.get("label") or folder_id
        candidate = {"name": label, "title": label, "approved": True}
        if not self.evaluate_rules(assignment, candidate):
            return {"success": False, "message": "Assignment rules excluded this source."}
        self._provenance.upsert_reference(
            client,
            org_id,
            agent_id,
            {
                "assignment_id": assignment.get("id"),
                "source_system": "google_drive",
                "connector_id": assignment.get("connectorId") or assignment.get("connector_id"),
                "external_object_id": folder_id,
                "external_url": assignment.get("externalSourceUrl") or assignment.get("external_source_url"),
                "source_title": label,
                "source_type": normalize_source_type(str(assignment.get("sourceType") or "google_drive_folder")),
                "memory_summary": f"Reference to Google Drive folder '{label}'. Content is indexed as summaries and embeddings only.",
                "provenance_chain": [{"step": "drive_folder_assignment", "folder_id": folder_id}],
            },
        )
        return {"success": True, "message": "Google Drive folder reference synced.", "references": 1}

    async def _sync_via_org_connector(
        self,
        client: Any,
        org_id: str,
        agent_id: str,
        assignment: dict[str, Any],
        *,
        vendor: str,
    ) -> dict[str, Any]:
        label = assignment.get("label") or assignment.get("sourceId")
        self._provenance.upsert_reference(
            client,
            org_id,
            agent_id,
            {
                "assignment_id": assignment.get("id"),
                "source_system": vendor,
                "connector_id": assignment.get("connectorId") or assignment.get("connector_id"),
                "external_object_id": str(assignment.get("sourceId") or assignment.get("source_id") or ""),
                "source_title": label,
                "source_type": normalize_source_type(str(assignment.get("sourceType") or vendor)),
                "memory_summary": f"Reference to {vendor} source '{label}'. Sync uses org connector with reference-only storage.",
                "provenance_chain": [{"step": "connector_assignment", "vendor": vendor}],
            },
        )
        return {"success": True, "message": f"{vendor} reference synced.", "references": 1}

    async def _sync_reference_stub(
        self,
        client: Any,
        org_id: str,
        agent_id: str,
        assignment: dict[str, Any],
        vendor: str,
    ) -> dict[str, Any]:
        label = assignment.get("label") or "Source"
        self._provenance.upsert_reference(
            client,
            org_id,
            agent_id,
            {
                "assignment_id": assignment.get("id"),
                "source_system": vendor,
                "external_object_id": str(assignment.get("sourceId") or assignment.get("source_id") or label),
                "source_title": label,
                "source_type": normalize_source_type(str(assignment.get("sourceType") or "manual_rule")),
                "memory_summary": f"Reference registered for '{label}'. Full connector sync pending for {vendor}.",
                "freshness_score": 0.5,
            },
        )
        return {"success": True, "message": "Reference stub registered.", "references": 1, "degraded": True}

    @staticmethod
    def _get_assignment(client: Any, org_id: str, agent_id: str, assignment_id: str) -> dict[str, Any] | None:
        try:
            result = (
                client.table("agent_knowledge_assignments")
                .select("*")
                .eq("org_id", org_id)
                .eq("agent_id", agent_id)
                .eq("id", assignment_id)
                .maybe_single()
                .execute()
            )
            if not result.data:
                return None
            return get_agent_knowledge_assignment_service()._serialize_row(result.data)
        except Exception:  # noqa: BLE001
            rows = get_agent_knowledge_assignment_service().list_assignments(client, org_id, agent_id)
            for row in rows:
                if str(row.get("id")) == assignment_id:
                    return row
            return None

    @staticmethod
    def _match_pattern(pattern: str, value: str) -> bool:
        if "*" in pattern or "?" in pattern:
            regex = "^" + re.escape(pattern).replace("\\*", ".*").replace("\\?", ".") + "$"
            return bool(re.search(regex, value, re.I))
        return pattern.lower() in value.lower()


_service: AgentKnowledgeSyncService | None = None


def get_agent_knowledge_sync_service(settings: Settings | None = None) -> AgentKnowledgeSyncService:
    global _service
    if _service is None or settings is not None:
        _service = AgentKnowledgeSyncService(settings)
    return _service
