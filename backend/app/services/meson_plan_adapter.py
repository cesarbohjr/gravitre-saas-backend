"""Meson → CognitivePlanner schema adapter (Meson is a plan producer, not a second brain)."""
from __future__ import annotations

from typing import Any


def meson_workflow_to_cognitive_plan(workflow_artifact: dict[str, Any] | None) -> dict[str, Any]:
    """Map Meson generate_workflow / interpret output into current_plan-compatible shape."""
    artifact = workflow_artifact if isinstance(workflow_artifact, dict) else {}
    steps_in = artifact.get("steps") or artifact.get("nodes") or []
    steps: list[dict[str, Any]] = []
    if isinstance(steps_in, list):
        for idx, step in enumerate(steps_in):
            if not isinstance(step, dict):
                steps.append({"index": idx, "summary": str(step)[:300]})
                continue
            steps.append(
                {
                    "index": idx,
                    "id": step.get("id") or step.get("step_id"),
                    "type": step.get("type") or step.get("step_type"),
                    "summary": str(step.get("name") or step.get("summary") or step.get("action") or "")[:300],
                    "action": step.get("action") or step.get("invoke_action"),
                }
            )
    return {
        "steps": steps,
        "summary": str(artifact.get("summary") or artifact.get("name") or "meson_plan")[:500],
        "source": "meson_plan_adapter",
        "workflow_id": artifact.get("workflow_id") or artifact.get("id"),
    }
