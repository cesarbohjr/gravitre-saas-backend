"""Department-scoped RAG helpers (STA-20)."""
from __future__ import annotations

from typing import Any


def resolve_department_id_for_agent(
    client: Any,
    org_id: str,
    agent_id: str | None,
) -> tuple[str | None, str | None]:
    """Return (department_id, agent_id) for RAG filtering from an agent row."""
    if not agent_id:
        return None, None
    r = (
        client.table("agents")
        .select("id, department")
        .eq("org_id", org_id)
        .eq("id", agent_id)
        .limit(1)
        .execute()
    )
    if not r.data:
        return None, agent_id
    row = r.data[0]
    dept_name = (row.get("department") or "").strip()
    if not dept_name:
        return None, agent_id
    dept_r = (
        client.table("departments")
        .select("id")
        .eq("org_id", org_id)
        .eq("name", dept_name)
        .limit(1)
        .execute()
    )
    if not dept_r.data:
        return None, agent_id
    return str(dept_r.data[0]["id"]), agent_id


def resolve_department_id_by_name(client: Any, org_id: str, department_name: str | None) -> str | None:
    if not department_name or not str(department_name).strip():
        return None
    r = (
        client.table("departments")
        .select("id")
        .eq("org_id", org_id)
        .eq("name", str(department_name).strip())
        .limit(1)
        .execute()
    )
    if not r.data:
        return None
    return str(r.data[0]["id"])
