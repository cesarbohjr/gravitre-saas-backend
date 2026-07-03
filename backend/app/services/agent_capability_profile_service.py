"""Aggregated agent capability profile — read, write, learn, recommend."""
from __future__ import annotations

from typing import Any

from app.config import Settings, get_settings
from app.services.agent_knowledge_assignment_service import get_agent_knowledge_assignment_service
from app.services.agent_memory_service import ensure_agent_in_org
from app.services.agent_tool_permissions import list_agent_tool_permissions

READ_SCOPES = {"read", "search", "lookup"}
WRITE_SCOPES = {"write", "create", "update", "delete", "execute"}
LEARN_SCOPES = {"learn", "summarize", "read"}


class AgentCapabilityProfileService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._knowledge = get_agent_knowledge_assignment_service(settings)

    def build_profile(self, client: Any, org_id: str, agent_id: str) -> dict[str, Any]:
        agent = ensure_agent_in_org(client, org_id, agent_id)
        assignments = self._knowledge.list_assignments(client, org_id, agent_id)
        tool_perms = list_agent_tool_permissions(client, org_id, agent_id)
        capabilities = list(agent.get("capabilities") or [])

        connected_sources = [
            {
                "label": row.get("label"),
                "sourceType": row.get("sourceType"),
                "freshnessStatus": row.get("freshnessStatus"),
                "lastSyncedAt": row.get("lastSyncedAt"),
                "enabled": row.get("enabled", True),
            }
            for row in assignments
            if row.get("enabled", True)
        ]

        read_actions: list[str] = []
        write_actions: list[str] = []
        approval_actions: list[str] = []
        for perm in tool_perms:
            scopes = set(str(s).lower() for s in (perm.get("scopes") or []))
            connector = perm.get("connector_type") or perm.get("connector_id") or "connector"
            if scopes.intersection(READ_SCOPES):
                read_actions.append(f"Read {connector}")
            if scopes.intersection(WRITE_SCOPES):
                write_actions.append(f"Write {connector}")
                approval_actions.append(f"Write {connector} (approval required)")

        for row in assignments:
            read_scope = row.get("readScope") or row.get("read_scope") or ["read"]
            learn_scope = row.get("learnScope") or row.get("learn_scope") or ["read", "summarize"]
            label = row.get("label") or row.get("sourceType")
            if any(s in READ_SCOPES for s in read_scope):
                read_actions.append(f"Read {label}")
            if any(s in LEARN_SCOPES for s in learn_scope):
                pass  # captured in learning_sources

        memory_count = self._memory_count(client, org_id, agent_id)
        freshness = self._aggregate_freshness(assignments)

        return {
            "agentId": agent_id,
            "department": agent.get("department"),
            "capabilities": capabilities,
            "connectedKnowledgeSources": connected_sources,
            "allowedConnectors": sorted({str(p.get("connector_type") or p.get("connector_id") or "") for p in tool_perms if p.get("connector_type") or p.get("connector_id")}),
            "availableReadActions": sorted(set(read_actions)),
            "availableWriteActions": sorted(set(write_actions)),
            "approvalRequiredActions": sorted(set(approval_actions)),
            "advisoryOnlyRestrictions": [
                "All recommendations are advisory until explicitly approved.",
                "Write actions require connector permission and human approval when configured.",
            ],
            "learningSources": [
                row.get("label") or row.get("sourceType")
                for row in assignments
                if row.get("enabled", True)
            ],
            "memoryCount": memory_count,
            "freshnessStatus": freshness,
            "lastSync": max(
                (row.get("lastSyncedAt") for row in assignments if row.get("lastSyncedAt")),
                default=None,
            ),
            "confidenceScore": round(
                sum(float(row.get("confidenceScore") or 0.75) for row in assignments) / max(len(assignments), 1),
                4,
            )
            if assignments
            else 0.75,
            "departmentScope": agent.get("department"),
            "planRestrictions": [],
            "canRecommend": True,
            "canExecuteWithApproval": bool(write_actions),
        }

    @staticmethod
    def _memory_count(client: Any, org_id: str, agent_id: str) -> int:
        try:
            result = (
                client.table("agent_memories")
                .select("id", count="exact")
                .eq("org_id", org_id)
                .eq("agent_id", agent_id)
                .execute()
            )
            return int(result.count or 0)
        except Exception:  # noqa: BLE001
            return 0

    @staticmethod
    def _aggregate_freshness(assignments: list[dict[str, Any]]) -> str:
        statuses = [str(row.get("freshnessStatus") or "unknown") for row in assignments]
        if not statuses:
            return "unknown"
        if any(s == "expired" for s in statuses):
            return "expired"
        if any(s == "stale" for s in statuses):
            return "stale"
        if all(s == "fresh" for s in statuses):
            return "fresh"
        return "mixed"


_service: AgentCapabilityProfileService | None = None


def get_agent_capability_profile_service(settings: Settings | None = None) -> AgentCapabilityProfileService:
    global _service
    if _service is None or settings is not None:
        _service = AgentCapabilityProfileService(settings)
    return _service
