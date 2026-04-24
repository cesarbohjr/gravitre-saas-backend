"""BE-11: Workflow definition validation; size limits; no PII in definition."""
from __future__ import annotations

import json
from typing import Any

from app.workflows.constants import (
    ALLOWED_STEP_TYPES,
    DEFINITION_MAX_BYTES,
    MAX_STEPS,
    PARAMS_MAX_BYTES,
    SCHEMA_VERSION,
)


class WorkflowValidationError(Exception):
    """Raised when definition or parameters fail validation."""
    def __init__(self, message: str, errors: list[str] | None = None):
        self.message = message
        self.errors = errors or [message]
        super().__init__(message)


def _check_size(data: dict | list, max_bytes: int, label: str) -> None:
    raw = json.dumps(data, separators=(",", ":"))
    if len(raw.encode("utf-8")) > max_bytes:
        raise WorkflowValidationError(
            f"{label} exceeds maximum size ({max_bytes} bytes)",
            errors=[f"{label}_too_large"],
        )


def validate_definition(definition: dict[str, Any]) -> dict[str, Any]:
    """
    Validate workflow definition. Returns normalized definition.
    Raises WorkflowValidationError on invalid schema or unknown version/step type.
    """
    if not isinstance(definition, dict):
        raise WorkflowValidationError("definition must be an object", errors=["invalid_definition"])
    _check_size(definition, DEFINITION_MAX_BYTES, "definition")

    version = definition.get("schema_version")
    if version != SCHEMA_VERSION:
        raise WorkflowValidationError(
            f"Unsupported schema_version: {version!r}; supported: {SCHEMA_VERSION!r}",
            errors=["unsupported_schema_version"],
        )

    steps = definition.get("steps")
    if not isinstance(steps, list):
        raise WorkflowValidationError("definition.steps must be an array", errors=["missing_steps"])
    if len(steps) > MAX_STEPS:
        raise WorkflowValidationError(
            f"definition.steps exceeds maximum ({MAX_STEPS} steps)",
            errors=["steps_count_exceeded"],
        )
    if len(steps) == 0:
        raise WorkflowValidationError("definition.steps must not be empty", errors=["empty_steps"])

    seen_ids: set[str] = set()
    for i, raw_step in enumerate(steps):
        if not isinstance(raw_step, dict):
            raise WorkflowValidationError(
                f"step at index {i} must be an object",
                errors=[f"step_{i}_invalid"],
            )
        step_id = raw_step.get("id")
        if not step_id or not isinstance(step_id, str) or not step_id.strip():
            raise WorkflowValidationError(
                f"step at index {i} must have non-empty string 'id'",
                errors=[f"step_{i}_missing_id"],
            )
        if step_id in seen_ids:
            raise WorkflowValidationError(
                f"duplicate step id: {step_id!r}",
                errors=[f"step_{i}_duplicate_id"],
            )
        seen_ids.add(step_id)
        name = raw_step.get("name")
        if not name or not isinstance(name, str):
            raise WorkflowValidationError(
                f"step {step_id!r} must have non-empty string 'name'",
                errors=[f"step_{i}_missing_name"],
            )
        step_type = raw_step.get("type")
        if step_type not in ALLOWED_STEP_TYPES:
            raise WorkflowValidationError(
                f"step {step_id!r} has unsupported type: {step_type!r}",
                errors=[f"step_{i}_invalid_type"],
            )
        config = raw_step.get("config")
        if config is not None and not isinstance(config, dict):
            raise WorkflowValidationError(
                f"step {step_id!r} config must be an object",
                errors=[f"step_{i}_invalid_config"],
            )
        metadata = raw_step.get("metadata")
        if metadata is not None and not isinstance(metadata, dict):
            raise WorkflowValidationError(
                f"step {step_id!r} metadata must be an object",
                errors=[f"step_{i}_invalid_metadata"],
            )
        if isinstance(metadata, dict):
            role = metadata.get("role")
            if role is not None and not isinstance(role, str):
                raise WorkflowValidationError(
                    f"step {step_id!r} metadata.role must be a string",
                    errors=[f"step_{i}_invalid_metadata_role"],
                )
            agent_id = metadata.get("agent_id")
            if agent_id is not None and not isinstance(agent_id, str):
                raise WorkflowValidationError(
                    f"step {step_id!r} metadata.agent_id must be a string",
                    errors=[f"step_{i}_invalid_metadata_agent_id"],
                )
            next_agent_id = metadata.get("next_agent_id")
            if next_agent_id is not None and not isinstance(next_agent_id, str):
                raise WorkflowValidationError(
                    f"step {step_id!r} metadata.next_agent_id must be a string",
                    errors=[f"step_{i}_invalid_metadata_next_agent_id"],
                )
            task = metadata.get("task")
            if task is not None and not isinstance(task, str):
                raise WorkflowValidationError(
                    f"step {step_id!r} metadata.task must be a string",
                    errors=[f"step_{i}_invalid_metadata_task"],
                )
            approval_gate = metadata.get("approval_gate")
            if approval_gate is not None and not isinstance(approval_gate, bool):
                raise WorkflowValidationError(
                    f"step {step_id!r} metadata.approval_gate must be a boolean",
                    errors=[f"step_{i}_invalid_metadata_approval_gate"],
                )
    return definition


def validate_parameters(parameters: dict[str, Any] | None) -> dict[str, Any]:
    """Validate parameters size; return params or empty dict."""
    if parameters is None:
        return {}
    if not isinstance(parameters, dict):
        raise WorkflowValidationError("parameters must be an object", errors=["invalid_parameters"])
    _check_size(parameters, PARAMS_MAX_BYTES, "parameters")
    return parameters


def compute_run_hash(definition_snapshot: dict, parameters: dict, schema_version: str) -> str:
    """Stable hash for definition_snapshot + parameters + schema_version."""
    import hashlib
    payload = json.dumps(
        {"d": definition_snapshot, "p": parameters, "v": schema_version},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
