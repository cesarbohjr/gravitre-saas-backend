"""G1 — Canonical agent roster (agents table + operators merge).

Matches the Next.js BFF at apps/web/app/api/agents/route.ts so map and
runtime share one definition of configured vs running agents.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.operators.repository import list_operators
from app.schemas.intelligence_projection import (
    AgentConfiguredStatus,
    AgentExecutionStatus,
    CanonicalAgent,
    IntelligenceProvenance,
)
from app.services.handoff_service import get_agent
from app.services.swarm_coordinator_service import SWARM_AGGREGATING, SWARM_RUNNING, list_swarm_runs


def _map_configured_status(raw: str | None) -> AgentConfiguredStatus:
    normalized = str(raw or "idle").lower()
    if normalized == "active":
        return "active"
    if normalized in {"processing", "running"}:
        return "processing"
    if normalized in {"error", "failed"}:
        return "error"
    return "idle"


def _infer_department(name: str, role: str | None, purpose: str | None) -> str:
    text = f"{name} {role or ''} {purpose or ''}".lower()
    if "sales" in text or "revenue" in text:
        return "Sales"
    if "marketing" in text:
        return "Marketing"
    if "finance" in text or "billing" in text:
        return "Finance"
    if "support" in text or "customer" in text:
        return "Support"
    if "hr" in text or "talent" in text or "recruit" in text:
        return "HR"
    return "Operations"


def load_canonical_agents(
    client: Any,
    org_id: str,
    *,
    environment_name: str = "production",
) -> tuple[list[CanonicalAgent], set[str]]:
    """Return canonical agents and set of agent ids currently in swarm execution."""
    now = datetime.now(timezone.utc).isoformat()
    running_ids: set[str] = set()
    try:
        for run in list_swarm_runs(client, org_id, limit=50):
            if run.get("status") in {SWARM_RUNNING, SWARM_AGGREGATING}:
                for agent_id in run.get("agent_ids") or []:
                    running_ids.add(str(agent_id))
                lead = run.get("lead_agent_id")
                if lead:
                    running_ids.add(str(lead))
    except Exception:  # noqa: BLE001
        running_ids = set()

    agents: list[CanonicalAgent] = []
    seen: set[str] = set()

    try:
        rows = (
            client.table("agents")
            .select("id,name,role,department,status,description,purpose")
            .eq("org_id", org_id)
            .order("updated_at", desc=True)
            .limit(100)
            .execute()
            .data
            or []
        )
    except Exception:  # noqa: BLE001
        rows = []

    for row in rows:
        agent_id = str(row.get("id") or "")
        if not agent_id or agent_id in seen:
            continue
        seen.add(agent_id)
        configured = _map_configured_status(row.get("status"))
        is_running = agent_id in running_ids
        dept = str(row.get("department") or _infer_department(
            str(row.get("name") or ""),
            row.get("role"),
            row.get("description") or row.get("purpose"),
        ))
        agents.append(
            CanonicalAgent(
                id=agent_id,
                name=str(row.get("name") or "Agent"),
                role=row.get("role"),
                department=dept,
                businessLabel=str(row.get("name") or "Agent"),
                technicalLabel=agent_id,
                configuredStatus=configured,
                executionStatus="running" if is_running else "idle",
                isConfiguredActive=configured in {"active", "processing"},
                isCurrentlyRunning=is_running,
                source=IntelligenceProvenance(system="agent_roster", recordId=agent_id, fetchedAt=now),
                metadata={"table": "agents"},
            )
        )

    try:
        operators = list_operators(client, org_id)
    except Exception:  # noqa: BLE001
        operators = []

    for op in operators:
        op_id = str(op.get("id") or "")
        if not op_id or op_id in seen:
            continue
        # Mirror Next BFF: include operator if not already represented in agents table.
        agent_row = get_agent(client, org_id, op_id)
        if agent_row:
            continue
        seen.add(op_id)
        configured = _map_configured_status(op.get("status"))
        is_running = op_id in running_ids
        name = str(op.get("name") or "Agent")
        role = op.get("role")
        agents.append(
            CanonicalAgent(
                id=op_id,
                name=name,
                role=role,
                department=_infer_department(name, role, op.get("description")),
                businessLabel=name,
                technicalLabel=op_id,
                configuredStatus=configured,
                executionStatus="running" if is_running else "idle",
                isConfiguredActive=configured in {"active", "processing"},
                isCurrentlyRunning=is_running,
                source=IntelligenceProvenance(system="agent_roster", recordId=op_id, fetchedAt=now),
                metadata={"table": "operators"},
            )
        )

    return agents, running_ids
