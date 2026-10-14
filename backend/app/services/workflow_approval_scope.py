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
from app.services.write_approval_fingerprints import (
    allowed_write_targets_from_definition,
    invoke_target_allowed,
    write_target_fingerprint,
)

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
    targets = allowed_write_targets_from_definition(definition)
    return {
        "definition_digest": digest,
        "allowed_invoke_actions": sorted(invoke_actions),
        "allowed_external_step_types": sorted(external_types),
        "allowed_write_targets": targets,
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


def definition_digest_matches(scope: dict[str, Any] | None, definition: dict[str, Any] | None) -> bool:
    if not scope:
        return True
    expected = str(scope.get("definition_digest") or "").strip()
    if not expected:
        return False
    current = definition_write_surface(definition if isinstance(definition, dict) else {}).get("definition_digest")
    return str(current or "") == expected


def approval_scope_required(run_row: dict[str, Any] | None) -> bool:
    if not isinstance(run_row, dict):
        return False
    try:
        required = int(run_row.get("required_approvals") or 0)
    except (TypeError, ValueError):
        required = 0
    return required > 0


def block_invoke_by_approval_scope(
    *,
    invoke_action: str,
    run_row: dict[str, Any] | None,
    run_parameters: dict[str, Any] | None,
    definition: dict[str, Any] | None,
    invoke_params: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Return a block payload when a catalog write is outside the sealed approval scope."""
    from app.services.catalog_write_authority import invoke_action_requires_write_approval

    if not invoke_action_requires_write_approval(invoke_action):
        return None
    if not approval_scope_required(run_row):
        return None
    params = run_parameters
    if params is None and isinstance(run_row, dict):
        raw = run_row.get("parameters")
        params = raw if isinstance(raw, dict) else None
    scope = scope_from_run_parameters(params)
    if not scope:
        return {
            "success": False,
            "error_code": "approval_scope_missing",
            "reason": "approval_scope_missing",
            "action": invoke_action,
        }
    if not definition_digest_matches(scope, definition):
        return {
            "success": False,
            "error_code": "approval_scope_digest_mismatch",
            "reason": "approval_scope_digest_mismatch",
            "action": invoke_action,
        }
    if not step_allowed_by_scope(
        step_type="invoke_tool",
        config={"action": invoke_action},
        scope=scope,
    ):
        return {
            "success": False,
            "error_code": "approval_scope_mismatch",
            "reason": "approval_scope_mismatch",
            "action": invoke_action,
        }
    allowed_targets = scope.get("allowed_write_targets") if isinstance(scope.get("allowed_write_targets"), list) else []
    runtime_params = invoke_params if isinstance(invoke_params, dict) else {}
    scoped_targets = [row for row in allowed_targets if row.get("invoke_action") == invoke_action]
    if not scoped_targets:
        return {
            "success": False,
            "error_code": "approval_scope_args_unsealed",
            "reason": "approval_scope_args_unsealed",
            "action": invoke_action,
        }
    if not invoke_target_allowed(
        invoke_action=invoke_action,
        params=runtime_params,
        allowed_targets=allowed_targets,
    ):
        fp = write_target_fingerprint(invoke_action=invoke_action, payload=runtime_params)
        return {
            "success": False,
            "error_code": "approval_scope_args_mismatch",
            "reason": "approval_scope_args_mismatch",
            "action": invoke_action,
            "fingerprint": fp,
        }
    return None


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
