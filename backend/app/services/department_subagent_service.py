"""Recursive department sub-agents under an umbrella agent + shared dept memory helpers."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.rag.department import resolve_department_id_for_agent, resolve_department_id_by_name
from app.workflows.repository import get_supabase_client

logger = get_logger(__name__)


class DepartmentSubagentError(Exception):
    def __init__(self, message: str, *, code: str = "VALIDATION_ERROR") -> None:
        super().__init__(message)
        self.code = code


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _serialize_agent(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(row.get("id")),
        "name": row.get("name"),
        "role": row.get("role"),
        "department": row.get("department"),
        "status": row.get("status"),
        "parentAgentId": str(row["parent_agent_id"]) if row.get("parent_agent_id") else None,
        "purpose": row.get("purpose") or row.get("description"),
        "config": row.get("config") if isinstance(row.get("config"), dict) else {},
    }


class DepartmentSubagentService:
    """Spawn and list department sub-agents under a department umbrella agent."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def _client(self) -> Any:
        return get_supabase_client(self.settings)

    def _get_agent(self, client: Any, org_id: str, agent_id: str) -> dict[str, Any]:
        rows = (
            client.table("agents")
            .select("id,org_id,name,purpose,description,role,department,status,config,parent_agent_id")
            .eq("org_id", org_id)
            .eq("id", agent_id)
            .limit(1)
            .execute()
            .data
            or []
        )
        if not rows:
            raise DepartmentSubagentError("Umbrella agent not found", code="NOT_FOUND")
        return dict(rows[0])

    def list_department_subagents(
        self,
        org_id: str,
        umbrella_agent_id: str,
        *,
        recursive: bool = True,
    ) -> dict[str, Any]:
        client = self._client()
        umbrella = self._get_agent(client, org_id, umbrella_agent_id)
        department = str(umbrella.get("department") or "").strip() or None
        dept_id, _ = resolve_department_id_for_agent(client, org_id, umbrella_agent_id)

        children: list[dict[str, Any]] = []
        frontier = [umbrella_agent_id]
        seen: set[str] = {umbrella_agent_id}
        while frontier:
            parent_id = frontier.pop(0)
            rows = (
                client.table("agents")
                .select("id,org_id,name,purpose,description,role,department,status,config,parent_agent_id")
                .eq("org_id", org_id)
                .eq("parent_agent_id", parent_id)
                .order("created_at", desc=False)
                .limit(100)
                .execute()
                .data
                or []
            )
            for row in rows:
                aid = str(row.get("id") or "")
                if not aid or aid in seen:
                    continue
                seen.add(aid)
                children.append(_serialize_agent(row))
                if recursive:
                    frontier.append(aid)

        return {
            "umbrellaAgent": _serialize_agent(umbrella),
            "department": department,
            "departmentId": dept_id,
            "subAgents": children,
            "count": len(children),
            "sharedDepartmentMemory": bool(dept_id),
        }

    def spawn_department_subagent(
        self,
        org_id: str,
        umbrella_agent_id: str,
        *,
        name: str,
        role: str | None = None,
        purpose: str | None = None,
        actor_id: str | None = None,
    ) -> dict[str, Any]:
        client = self._client()
        umbrella = self._get_agent(client, org_id, umbrella_agent_id)
        department = str(umbrella.get("department") or "").strip()
        if not department:
            raise DepartmentSubagentError(
                "Umbrella agent has no department; cannot spawn department sub-agent",
                code="VALIDATION_ERROR",
            )
        clean_name = (name or "").strip()
        if not clean_name:
            raise DepartmentSubagentError("name is required", code="VALIDATION_ERROR")

        dept_id = resolve_department_id_by_name(client, org_id, department)
        config = {
            "department": department,
            "departmentSubAgent": True,
            "umbrellaAgentId": umbrella_agent_id,
        }
        if dept_id:
            config["departmentId"] = dept_id

        row = {
            "org_id": org_id,
            "name": clean_name,
            "purpose": (purpose or f"Department sub-agent under {umbrella.get('name')}").strip(),
            "role": (role or umbrella.get("role") or "Specialist").strip(),
            "department": department,
            "parent_agent_id": umbrella_agent_id,
            "model": umbrella.get("model") or "gpt-4.1",
            "capabilities": umbrella.get("capabilities") or [],
            "systems": umbrella.get("systems") or [],
            "guardrails": umbrella.get("guardrails") or [],
            "config": config,
            "status": "active",
        }
        # created_by is optional depending on schema vintage
        if actor_id:
            row["created_by"] = actor_id
        inserted = client.table("agents").insert(row).execute()
        if not inserted.data:
            raise DepartmentSubagentError("Failed to create department sub-agent", code="INTERNAL")
        agent = dict(inserted.data[0])
        logger.info(
            "department_subagent_spawned org_id=%s umbrella=%s child=%s department=%s",
            org_id,
            umbrella_agent_id,
            agent.get("id"),
            department,
        )
        return {
            "agent": _serialize_agent(agent),
            "department": department,
            "departmentId": dept_id,
            "sharedDepartmentMemory": bool(dept_id),
        }


_service: DepartmentSubagentService | None = None


def get_department_subagent_service(settings: Settings | None = None) -> DepartmentSubagentService:
    global _service
    if _service is None or settings is not None:
        _service = DepartmentSubagentService(settings)
    return _service
