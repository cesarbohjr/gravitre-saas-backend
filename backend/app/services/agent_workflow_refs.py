"""Find workflows that reference an agent in their definition/builder graph."""
from __future__ import annotations

from typing import Any


def _collect_agent_ids_from_value(value: Any, into: set[str]) -> None:
    if value is None:
        return
    if isinstance(value, str):
        text = value.strip()
        if text:
            into.add(text)
        return
    if isinstance(value, (list, tuple, set)):
        for item in value:
            _collect_agent_ids_from_value(item, into)
        return
    if isinstance(value, dict):
        for key, nested in value.items():
            key_l = str(key).lower()
            if key_l in {
                "agent_id",
                "agentid",
                "next_agent_id",
                "nextagentid",
                "operator_id",
                "operatorid",
            }:
                _collect_agent_ids_from_value(nested, into)
            elif key_l in {"agent_ids", "agentids"}:
                _collect_agent_ids_from_value(nested, into)
            else:
                _collect_agent_ids_from_value(nested, into)


def agent_ids_in_definition(definition: dict[str, Any] | None) -> set[str]:
    found: set[str] = set()
    if not isinstance(definition, dict):
        return found
    _collect_agent_ids_from_value(definition, found)
    return found


def find_workflows_referencing_agent(
    client: Any,
    org_id: str,
    agent_id: str,
    *,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Return active (non-archived) workflows that reference agent_id in their definition."""
    target = str(agent_id).strip()
    if not target:
        return []

    try:
        result = (
            client.table("workflow_defs")
            .select("id, name, status, definition")
            .eq("org_id", org_id)
            .limit(limit)
            .execute()
        )
        rows = list(result.data or [])
    except Exception:
        rows = []

    refs: list[dict[str, Any]] = []
    for row in rows:
        status = str(row.get("status") or "").lower()
        if status in {"archived", "deleted"}:
            continue
        definition = row.get("definition") if isinstance(row.get("definition"), dict) else {}
        if target not in agent_ids_in_definition(definition):
            continue
        refs.append(
            {
                "workflowId": str(row.get("id") or ""),
                "workflowName": str(row.get("name") or "Workflow"),
                "status": status or None,
            }
        )

    # Annotate whether any enabled schedule exists for each workflow.
    for ref in refs:
        wid = ref["workflowId"]
        if not wid:
            ref["hasEnabledSchedule"] = False
            continue
        try:
            schedules = (
                client.table("workflow_schedules")
                .select("id, enabled")
                .eq("org_id", org_id)
                .eq("workflow_id", wid)
                .limit(20)
                .execute()
            )
            enabled = False
            for s in schedules.data or []:
                if s.get("enabled", True):
                    enabled = True
                    break
            ref["hasEnabledSchedule"] = enabled
        except Exception:
            ref["hasEnabledSchedule"] = False

    return refs
