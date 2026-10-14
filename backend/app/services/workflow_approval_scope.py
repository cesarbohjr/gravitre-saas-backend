"""Seal which catalog writes a workflow approval authorizes.

A run's ``definition_snapshot`` is frozen at creation. Execution must not run
invoke actions that were not present in that snapshot when approvers signed off.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from app.services.canvas_write_gate import EXTERNAL_WRITE_STEP_TYPES, _invoke_action_from_step, _iter_definition_steps
from app.services.catalog_write_authority import invoke_action_requires_write_approval
from app.services.tool_service import STEP_TYPE_TO_ACTION

APPROVAL_SCOPE_KEY = "approval_scope"


def definition_write_surface(definition: dict[str, Any] | None) -> dict[str, Any]:
    """Catalog invoke actions and legacy external step types in a definition."""
    invoke_actions: set[str] = set()
    external_types: set[str] = set()
    for step in _iter_definition_steps(definition):
        stype = str(step.get("type") or "").strip()
        if stype in EXTERNAL_WRITE_STEP_TYPES:
            external_types.add(stype)
            action = STEP_TYPE_TO_ACTION.get(stype)
            if action:
                invoke_actions.add(action)
            continue
        action = _invoke_action_from_step(step)
        if action and invoke_action_requires_write_approval(action):
            invoke_actions.add(action)
    payload = json.dumps(definition or {}, sort_keys=True, default=str)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return {
        "definition_digest": digest,
        "allowed_invoke_actions": sorted(invoke_actions),
        "allowed_external_step_types": sorted(external_types),
    }


def seal_approval_scope(definition: dict[str, Any] | None) -> dict[str, Any]:
    return definition_write_surface(definition)


def persist_run_approval_scope(client: Any, run_id: str, definition: dict[str, Any] | None) -> None:
    from app.workflows.repository import merge_run_parameters

    merge_run_parameters(
        client,
        run_id,
        {APPROVAL_SCOPE_KEY: seal_approval_scope(definition if isinstance(definition, dict) else {})},
    )


def scope_from_run_parameters(parameters: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(parameters, dict):
        return None
    scope = parameters.get(APPROVAL_SCOPE_KEY)
    return scope if isinstance(scope, dict) else None


def step_allowed_by_scope(
    *,
    step_type: str,
    config: dict[str, Any] | None,
    scope: dict[str, Any] | None,
) -> bool:
    if not scope:
        return True
    stype = str(step_type or "").strip()
    allowed_external = {str(x) for x in (scope.get("allowed_external_step_types") or [])}
    if stype in allowed_external:
        return True
    allowed = {str(x) for x in (scope.get("allowed_invoke_actions") or [])}
    if not allowed:
        return stype not in EXTERNAL_WRITE_STEP_TYPES
    action: str | None = None
    if stype in EXTERNAL_WRITE_STEP_TYPES:
        action = STEP_TYPE_TO_ACTION.get(stype)
    elif stype == "invoke_tool":
        cfg = config if isinstance(config, dict) else {}
        action = str(cfg.get("action") or cfg.get("tool_action") or "").strip() or None
    if not action:
        return True
    if not invoke_action_requires_write_approval(action):
        return True
    return action in allowed
