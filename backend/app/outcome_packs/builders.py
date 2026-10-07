"""Small helpers manifests use to declare Plays and dashboards.

They only shape declarative config (validated by ``OutcomePackAssetConfig``);
they never execute anything and hold no department knowledge.
"""
from __future__ import annotations

from typing import Any

CAPABILITY_ACTION_PREFIX = "capability."


def tool_step(
    step_id: str,
    name: str,
    action: str,
    *,
    param_sources: dict[str, Any] | None = None,
    connector: str | None = None,
) -> dict[str, Any]:
    """An ``invoke_tool`` step. ``capability.<id>`` actions resolve to the connected provider at run time."""
    is_capability = action.startswith(CAPABILITY_ACTION_PREFIX)
    vendor = connector or (None if is_capability else action.split(".", 1)[0])
    config: dict[str, Any] = {
        "action": action,
        "tool_action": action,
        "selectedAction": action.split(".", 1)[-1],
        "selected_action": action.split(".", 1)[-1],
    }
    if vendor:
        config["vendor"] = vendor
        config["connector"] = vendor
    if is_capability:
        config["capability_id"] = action[len(CAPABILITY_ACTION_PREFIX):]
    if param_sources:
        config["param_sources"] = param_sources
    step: dict[str, Any] = {"id": step_id, "name": name, "type": "invoke_tool", "config": config}
    if vendor:
        step["requires_connector"] = vendor
    return step


def agent_step(step_id: str, name: str, agent_seed: str, task: str) -> dict[str, Any]:
    return {
        "id": step_id,
        "name": name,
        "type": "agent",
        "metadata": {"agent_seed": agent_seed, "task": task},
    }


def approval_step(step_id: str, name: str, reason: str) -> dict[str, Any]:
    return {
        "id": step_id,
        "name": name,
        "type": "approval",
        "config": {"reason": reason, "required_approvals": 1},
    }


def _runtime_inputs(steps: list[dict[str, Any]]) -> list[str]:
    found: set[str] = set()
    for step in steps:
        config = step.get("config") if isinstance(step.get("config"), dict) else {}
        sources = config.get("param_sources") if isinstance(config.get("param_sources"), dict) else {}
        for value in sources.values():
            if isinstance(value, str) and value.startswith("$") and len(value) > 1:
                found.add(value[1:])
    return sorted(found)


def play(
    key: str,
    name: str,
    description: str,
    *,
    kpis: list[str],
    outcome_event: str,
    trigger: dict[str, Any],
    agent_seed: str,
    task: str,
    objective: str = "",
    evidence_steps: list[dict[str, Any]] | None = None,
    action_steps_after: list[dict[str, Any]] | None = None,
    approvals: list[dict[str, Any]] | None = None,
    capability_groups: list[list[str]] | None = None,
    required_connector_groups: list[list[str]] | None = None,
    optional_connectors: list[str] | None = None,
    read_action_groups: list[list[str]] | None = None,
    write_action_groups: list[list[str]] | None = None,
    write_actions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    steps = list(evidence_steps or [])
    steps.append(agent_step(f"{key}-analyze", f"{name} analysis", agent_seed, task))
    steps.extend(action_steps_after or [])
    return {
        "key": key,
        "name": name,
        "description": description,
        "objective": objective or description,
        "trigger": trigger,
        "workflow_steps": steps,
        "outcome_events": [outcome_event],
        "kpi_keys": list(kpis),
        "approvals": list(approvals or []),
        "verification": {"mode": "source_of_record", "provider_acceptance_is_terminal": False},
        "runtime_inputs": _runtime_inputs(steps),
        "capability_groups": [list(group) for group in (capability_groups or [])],
        "required_connector_groups": [list(group) for group in (required_connector_groups or [])],
        "optional_connectors": list(optional_connectors or []),
        "read_action_groups": [list(group) for group in (read_action_groups or [])],
        "write_action_groups": [list(group) for group in (write_action_groups or [])],
        "write_actions": list(write_actions or []),
    }


def dashboard(
    *,
    title: str,
    template_id: str,
    department: str,
    kpis: list[dict[str, Any]],
    sections: list[dict[str, Any]],
    system_health_kpis: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "title": title,
        "template_id": template_id,
        "department": department,
        "refresh_mode": "event",
        "sections": sections,
        "system_health_kpis": list(system_health_kpis or []),
        "metrics": [
            {
                "kpi_key": row["key"],
                "label": row["label"],
                "visualization": "trend"
                if row.get("unit") in {"minutes", "hours", "percent", "ratio", "score"}
                else "metric",
                "description": str(row.get("description") or row["label"])[:500],
            }
            for row in kpis
        ],
    }


def runtime_profile_actions(plays: list[dict[str, Any]], *extra: str) -> list[str]:
    """Every invoke_tool action the Plays use, so profile validation stays in sync."""
    actions: set[str] = set(extra)
    for item in plays:
        for step in item["workflow_steps"]:
            config = step.get("config") if isinstance(step.get("config"), dict) else {}
            if step.get("type") == "invoke_tool" and config.get("action"):
                actions.add(str(config["action"]))
    return sorted(actions)
