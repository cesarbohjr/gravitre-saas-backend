"""Plan resolution for IntelligenceOrchestrator Step 4 (RESOLVE_EXISTING vs GENERATE_AT_RUNTIME)."""
from __future__ import annotations

import json
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class PlanResolutionMode(str, Enum):
    RESOLVE_EXISTING = "resolve_existing"
    GENERATE_AT_RUNTIME = "generate_at_runtime"


class PlanResolutionError(ValueError):
    pass


class PlanResolutionRequest(BaseModel):
    surface: str = "agent"
    task_text: str = ""
    agent: dict[str, Any] = Field(default_factory=dict)
    existing_plan: dict[str, Any] | None = None
    subtask_spec: dict[str, Any] | None = None
    step_outputs: dict[str, Any] | None = None
    briefing: dict[str, Any] | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)


class ResolvedPlan(BaseModel):
    mode: PlanResolutionMode
    task_text: str
    agent: dict[str, Any]
    permitted_tools: list[str] | None = None
    upstream_context: dict[str, Any] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


def _tool_names_from_scoped(scoped_tools: Any) -> list[str]:
    if not isinstance(scoped_tools, list):
        return []
    names: list[str] = []
    for item in scoped_tools:
        if isinstance(item, str) and item.strip():
            names.append(item.strip())
        elif isinstance(item, dict):
            connector = item.get("connectorType") or item.get("connector_type")
            if connector:
                names.append(str(connector).strip().lower())
                continue
            name = item.get("name") or item.get("tool") or item.get("toolName")
            if name:
                names.append(str(name))
    return names


def _resolve_from_subtask(req: PlanResolutionRequest) -> ResolvedPlan:
    spec = req.subtask_spec or {}
    task = str(spec.get("task") or spec.get("task_prompt") or spec.get("taskPrompt") or req.task_text).strip()
    if not task:
        raise PlanResolutionError("subtask_spec requires task text")
    objective = str(spec.get("objective") or "").strip()
    parts = [task]
    if objective:
        parts.insert(0, f"Swarm objective: {objective}")
    scoped = spec.get("scoped_tools") or spec.get("scopedTools") or []
    return ResolvedPlan(
        mode=PlanResolutionMode.RESOLVE_EXISTING,
        task_text="\n".join(parts),
        agent=req.agent,
        permitted_tools=_tool_names_from_scoped(scoped) or None,
        upstream_context=req.briefing,
        metadata={
            "surface": req.surface,
            "planSource": "swarm_subtask",
            "subtaskId": spec.get("subtask_id") or spec.get("subtaskId"),
            "swarmRunId": spec.get("swarm_run_id") or spec.get("swarmRunId"),
        },
    )


def _resolve_from_workflow_step(req: PlanResolutionRequest) -> ResolvedPlan:
    plan = req.existing_plan or {}
    task = str(plan.get("task") or plan.get("task_prompt") or req.task_text).strip()
    if not task:
        raise PlanResolutionError("existing_plan requires task text")
    upstream: dict[str, Any] | None = None
    if req.briefing:
        upstream = dict(req.briefing)
    elif req.step_outputs:
        upstream = {"step_outputs": req.step_outputs}
    metadata = {
        "surface": req.surface,
        "planSource": "workflow_step",
        "stepId": plan.get("step_id") or plan.get("stepId"),
        "stepType": plan.get("step_type") or plan.get("stepType"),
    }
    permitted = plan.get("permitted_tools") or plan.get("permittedTools")
    if isinstance(permitted, list):
        tool_names = [str(t) for t in permitted if t]
    else:
        tool_names = _tool_names_from_scoped(plan.get("scoped_tools") or plan.get("scopedTools"))
    return ResolvedPlan(
        mode=PlanResolutionMode.RESOLVE_EXISTING,
        task_text=task,
        agent=req.agent,
        permitted_tools=tool_names or None,
        upstream_context=upstream,
        metadata=metadata,
    )


def resolve_plan(req: PlanResolutionRequest) -> ResolvedPlan:
    """Resolve how to bind work before ExecutionCore runs."""
    if req.subtask_spec:
        return _resolve_from_subtask(req)
    if req.existing_plan:
        return _resolve_from_workflow_step(req)
    if req.step_outputs and req.briefing is None and req.parameters.get("briefing_from_steps"):
        return ResolvedPlan(
            mode=PlanResolutionMode.RESOLVE_EXISTING,
            task_text=req.task_text.strip() or "Complete assigned workflow task",
            agent=req.agent,
            upstream_context={"step_outputs": req.step_outputs},
            metadata={"surface": req.surface, "planSource": "workflow_handoff"},
        )
    task = req.task_text.strip()
    if not task:
        raise PlanResolutionError("task_text is required for runtime plan generation")
    return ResolvedPlan(
        mode=PlanResolutionMode.GENERATE_AT_RUNTIME,
        task_text=task,
        agent=req.agent,
        upstream_context=req.briefing,
        metadata={"surface": req.surface, "planSource": "runtime"},
    )


def format_upstream_section(upstream: dict[str, Any] | None) -> str:
    if not upstream:
        return ""
    return f"<upstream_context>{json.dumps(upstream, default=str)[:8000]}</upstream_context>\n"
