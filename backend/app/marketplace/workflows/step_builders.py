"""Shared step builders for marketplace / intelligence-pack workflows."""
from __future__ import annotations

from typing import Any


def invoke_step(
    step_id: str,
    name: str,
    action: str,
    *,
    connector: str | None = None,
    params: dict[str, Any] | None = None,
    param_sources: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build an ``invoke_tool`` step with optional connector binding."""
    config: dict[str, Any] = {"action": action, "tool_action": action}
    if connector:
        config["vendor"] = connector
        config["connector"] = connector
        if "." in action:
            _vendor, selected = action.split(".", 1)
            config["selectedAction"] = selected
            config["selected_action"] = selected
    if params:
        config["params"] = params
    if param_sources:
        config["param_sources"] = param_sources
    step: dict[str, Any] = {
        "id": step_id,
        "name": name,
        "type": "invoke_tool",
        "config": config,
    }
    if connector:
        step["requires_connector"] = connector
    return step


def agent_step(
    step_id: str,
    name: str,
    task: str,
    *,
    agent_slug: str,
    briefing_from_steps: bool = False,
    receiver_task: str | None = None,
    next_agent_slug: str | None = None,
) -> dict[str, Any]:
    """Build an agent step with exact assignment instructions + seed for install bind."""
    metadata: dict[str, Any] = {
        "agent_seed": f"agent:{agent_slug}",
        "task": task,
        "assignment": True,
    }
    if briefing_from_steps:
        metadata["briefing_from_steps"] = True
    if receiver_task:
        metadata["receiver_task"] = receiver_task
    if next_agent_slug:
        metadata["next_agent_seed"] = f"agent:{next_agent_slug}"
    return {
        "id": step_id,
        "name": name,
        "type": "agent",
        "metadata": metadata,
    }


def sandwich_workflow(
    *,
    agent_slug: str,
    open_id: str,
    open_name: str,
    open_task: str,
    tool_steps: list[dict[str, Any]],
    close_id: str,
    close_name: str,
    close_task: str,
) -> list[dict[str, Any]]:
    """Agent brief → tool steps → agent summarize/notify."""
    return [
        agent_step(open_id, open_name, open_task, agent_slug=agent_slug),
        *tool_steps,
        agent_step(
            close_id,
            close_name,
            close_task,
            agent_slug=agent_slug,
            briefing_from_steps=True,
        ),
    ]
