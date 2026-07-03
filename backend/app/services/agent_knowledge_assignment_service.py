"""Agent knowledge source assignments — CRUD, sync freshness, config merge."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.services.agent_memory_service import ensure_agent_in_org

logger = get_logger(__name__)

FRESHNESS_STALE_HOURS = 72


class AgentKnowledgeAssignmentService:
    """Runtime knowledge ownership per agent — DB assignments + legacy config."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def list_assignments(self, client: Any, org_id: str, agent_id: str) -> list[dict[str, Any]]:
        ensure_agent_in_org(client, org_id, agent_id)
        rows = self._load_db_assignments(client, org_id, agent_id)
        if rows:
            return [self._serialize_row(row) for row in rows]
        agent = ensure_agent_in_org(client, org_id, agent_id)
        return self.resolve_assignments(agent)

    def resolve_assignments(self, agent: dict[str, Any]) -> list[dict[str, Any]]:
        config = agent.get("config") if isinstance(agent.get("config"), dict) else {}
        assignments: list[dict[str, Any]] = []
        for folder in config.get("reference_folders") or []:
            if isinstance(folder, dict):
                assignments.append(
                    self._serialize_row(
                        {
                            "agent_id": agent.get("id"),
                            "source_type": "folder",
                            "source_id": str(folder.get("id") or folder.get("path") or ""),
                            "label": folder.get("name") or folder.get("path") or "Folder",
                            "include_rules": folder.get("include_rules") or [],
                            "exclude_rules": folder.get("exclude_rules") or [],
                            "freshness_status": "unknown",
                            "enabled": True,
                        }
                    )
                )
                assignments[-1]["fromConfig"] = True
            elif isinstance(folder, str):
                assignments.append(
                    self._serialize_row(
                        {
                            "agent_id": agent.get("id"),
                            "source_type": "folder",
                            "source_id": folder,
                            "label": folder,
                            "freshness_status": "unknown",
                            "enabled": True,
                        }
                    )
                )
                assignments[-1]["fromConfig"] = True
        for pack in config.get("knowledge_packs") or []:
            if isinstance(pack, dict):
                assignments.append(
                    self._serialize_row(
                        {
                            "agent_id": agent.get("id"),
                            "source_type": "knowledge_pack",
                            "source_id": str(pack.get("id") or ""),
                            "label": pack.get("name") or pack.get("id") or "Knowledge pack",
                            "freshness_status": "unknown",
                            "enabled": True,
                        }
                    )
                )
                assignments[-1]["fromConfig"] = True
        for dataset in config.get("training_datasets") or config.get("datasets") or []:
            if isinstance(dataset, dict):
                assignments.append(
                    self._serialize_row(
                        {
                            "agent_id": agent.get("id"),
                            "source_type": "dataset",
                            "source_id": str(dataset.get("id") or ""),
                            "label": dataset.get("name") or "Training dataset",
                            "freshness_status": "unknown",
                            "enabled": True,
                        }
                    )
                )
                assignments[-1]["fromConfig"] = True
        return assignments

    def create_assignment(
        self,
        client: Any,
        org_id: str,
        agent_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        ensure_agent_in_org(client, org_id, agent_id)
        row = {
            "org_id": org_id,
            "agent_id": agent_id,
            "source_type": payload["source_type"],
            "source_id": payload["source_id"],
            "label": payload["label"],
            "include_rules": payload.get("include_rules") or [],
            "exclude_rules": payload.get("exclude_rules") or [],
            "sync_schedule": payload.get("sync_schedule"),
            "owner_user_id": payload.get("owner_user_id"),
            "confidence_score": payload.get("confidence_score", 0.75),
            "freshness_status": payload.get("freshness_status") or "unknown",
            "enabled": payload.get("enabled", True),
            "metadata": payload.get("metadata") or {},
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            inserted = client.table("agent_knowledge_assignments").insert(row).execute()
        except Exception as exc:  # noqa: BLE001
            if "duplicate" in str(exc).lower() or "unique" in str(exc).lower():
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Assignment already exists") from exc
            if self._is_missing_table(exc):
                return self._create_config_assignment(client, org_id, agent_id, payload)
            raise
        if not inserted.data:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Insert failed")
        return self._serialize_row(inserted.data[0])

    def update_assignment(
        self,
        client: Any,
        org_id: str,
        agent_id: str,
        assignment_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        ensure_agent_in_org(client, org_id, agent_id)
        updates = {key: payload[key] for key in payload if key in {
            "label", "include_rules", "exclude_rules", "sync_schedule", "owner_user_id",
            "confidence_score", "freshness_status", "enabled", "metadata", "last_synced_at",
        }}
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        try:
            result = (
                client.table("agent_knowledge_assignments")
                .update(updates)
                .eq("org_id", org_id)
                .eq("agent_id", agent_id)
                .eq("id", assignment_id)
                .execute()
            )
        except Exception as exc:  # noqa: BLE001
            if self._is_missing_table(exc):
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found") from exc
            raise
        if not result.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")
        return self._serialize_row(result.data[0])

    def delete_assignment(self, client: Any, org_id: str, agent_id: str, assignment_id: str) -> None:
        ensure_agent_in_org(client, org_id, agent_id)
        try:
            result = (
                client.table("agent_knowledge_assignments")
                .delete()
                .eq("org_id", org_id)
                .eq("agent_id", agent_id)
                .eq("id", assignment_id)
                .execute()
            )
        except Exception as exc:  # noqa: BLE001
            if self._is_missing_table(exc):
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found") from exc
            raise
        if not result.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")

    def sync_freshness(self, client: Any, org_id: str, agent_id: str) -> list[dict[str, Any]]:
        assignments = self.list_assignments(client, org_id, agent_id)
        updated: list[dict[str, Any]] = []
        for row in assignments:
            if row.get("from_config"):
                updated.append(row)
                continue
            freshness = self._compute_freshness(client, org_id, row)
            if row.get("id"):
                try:
                    result = (
                        client.table("agent_knowledge_assignments")
                        .update({"freshness_status": freshness, "updated_at": datetime.now(timezone.utc).isoformat()})
                        .eq("id", row["id"])
                        .execute()
                    )
                    if result.data:
                        updated.append(self._serialize_row(result.data[0]))
                        continue
                except Exception as exc:  # noqa: BLE001
                    logger.debug("knowledge_freshness_update_skipped id=%s error=%s", row.get("id"), exc)
            row["freshness_status"] = freshness
            updated.append(row)
        return updated

    def build_prompt_section(self, assignments: list[dict[str, Any]]) -> str:
        enabled = [row for row in assignments if row.get("enabled", True)]
        if not enabled:
            return ""
        lines = ["Assigned knowledge sources:"]
        for row in enabled[:10]:
            freshness = row.get("freshnessStatus") or row.get("freshness_status") or "unknown"
            label = row.get("label") or "Source"
            source_type = row.get("sourceType") or row.get("source_type") or "source"
            lines.append(f"- [{source_type}] {label} (freshness: {freshness})")
        return "\n".join(lines)

    def _load_db_assignments(self, client: Any, org_id: str, agent_id: str) -> list[dict[str, Any]]:
        try:
            result = (
                client.table("agent_knowledge_assignments")
                .select("*")
                .eq("org_id", org_id)
                .eq("agent_id", agent_id)
                .order("created_at", desc=True)
                .execute()
            )
            return list(result.data or [])
        except Exception as exc:  # noqa: BLE001
            if self._is_missing_table(exc):
                return []
            raise

    def _compute_freshness(self, client: Any, org_id: str, assignment: dict[str, Any]) -> str:
        last_synced = assignment.get("last_synced_at") or assignment.get("lastSyncedAt")
        if not last_synced:
            try:
                jobs = (
                    client.table("knowledge_sync_jobs")
                    .select("finished_at,status")
                    .eq("org_id", org_id)
                    .eq("source_type", assignment.get("source_type"))
                    .order("finished_at", desc=True)
                    .limit(1)
                    .execute()
                )
                if jobs.data:
                    last_synced = jobs.data[0].get("finished_at")
            except Exception:  # noqa: BLE001
                return "unknown"
        if not last_synced:
            return "unknown"
        try:
            synced_at = datetime.fromisoformat(str(last_synced).replace("Z", "+00:00"))
            age_hours = (datetime.now(timezone.utc) - synced_at).total_seconds() / 3600
            if age_hours <= FRESHNESS_STALE_HOURS:
                return "fresh"
            if age_hours <= FRESHNESS_STALE_HOURS * 3:
                return "stale"
            return "expired"
        except Exception:  # noqa: BLE001
            return "unknown"

    def _create_config_assignment(
        self,
        client: Any,
        org_id: str,
        agent_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        agent = ensure_agent_in_org(client, org_id, agent_id)
        config = dict(agent.get("config") or {})
        folders = list(config.get("reference_folders") or [])
        if payload["source_type"] == "folder":
            folders.append(
                {
                    "id": payload["source_id"],
                    "name": payload["label"],
                    "include_rules": payload.get("include_rules") or [],
                    "exclude_rules": payload.get("exclude_rules") or [],
                }
            )
            config["reference_folders"] = folders
        else:
            packs = list(config.get("knowledge_packs") or [])
            packs.append({"id": payload["source_id"], "name": payload["label"]})
            config["knowledge_packs"] = packs
        client.table("agents").update({"config": config}).eq("id", agent_id).eq("org_id", org_id).execute()
        return {
            "sourceType": payload["source_type"],
            "sourceId": payload["source_id"],
            "label": payload["label"],
            "freshnessStatus": "unknown",
            "enabled": True,
            "fromConfig": True,
        }

    @staticmethod
    def _serialize_row(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": row.get("id"),
            "agentId": row.get("agent_id"),
            "sourceType": row.get("source_type"),
            "sourceId": row.get("source_id"),
            "label": row.get("label"),
            "includeRules": row.get("include_rules") or [],
            "excludeRules": row.get("exclude_rules") or [],
            "syncSchedule": row.get("sync_schedule"),
            "ownerUserId": row.get("owner_user_id"),
            "confidenceScore": float(row.get("confidence_score") or 0.75),
            "lastSyncedAt": row.get("last_synced_at"),
            "freshnessStatus": row.get("freshness_status") or "unknown",
            "enabled": bool(row.get("enabled", True)),
            "metadata": row.get("metadata") or {},
            "fromConfig": bool(row.get("from_config")),
        }

    @staticmethod
    def _is_missing_table(exc: Exception) -> bool:
        message = str(exc).lower()
        return "agent_knowledge_assignments" in message and (
            "does not exist" in message or "relation" in message or "42p01" in message
        )


_service: AgentKnowledgeAssignmentService | None = None


def get_agent_knowledge_assignment_service(settings: Settings | None = None) -> AgentKnowledgeAssignmentService:
    global _service
    if _service is None or settings is not None:
        _service = AgentKnowledgeAssignmentService(settings)
    return _service
