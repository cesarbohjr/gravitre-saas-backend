"""Declarative policy evaluation for workflow execution."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.config import Settings
from app.workflows.constants import SAFE_DEFAULT_APPROVER_ROLES


EXTERNAL_STEP_TYPES = {"slack_post_message", "email_send", "webhook_post"}


@dataclass
class PolicyContext:
    settings: Settings
    org_id: str
    workflow_id: str
    definition: dict[str, Any]
    required_approvals: int
    approver_roles: list[str]
    environment_name: str | None = None
    max_steps: int | None = None
    max_runtime_seconds: int | None = None
    allowed_envs: list[str] | None = None
    allowed_connector_types: list[str] | None = None


@dataclass
class PolicyDecision:
    allowed: bool
    required_approvals: int
    approver_roles: list[str]
    approval_floor_applied: bool
    has_external_steps: bool
    status_code: int | None = None
    message: str | None = None


def _step_types(definition: dict[str, Any]) -> list[str]:
    return [str(s.get("type") or "").strip() for s in (definition.get("steps") or [])]


def evaluate_policy(context: PolicyContext) -> PolicyDecision:
    steps = _step_types(context.definition)
    step_count = len(steps)
    has_external = any(st in EXTERNAL_STEP_TYPES for st in steps)
    required_approvals = int(context.required_approvals or 0)
    approver_roles = list(context.approver_roles or [])
    approval_floor_applied = False

    if context.max_steps and step_count > context.max_steps:
        return PolicyDecision(
            allowed=False,
            required_approvals=required_approvals,
            approver_roles=approver_roles,
            approval_floor_applied=False,
            has_external_steps=has_external,
            status_code=400,
            message="Workflow exceeds max step limit",
        )

    if context.allowed_envs and context.environment_name:
        if context.environment_name not in context.allowed_envs:
            return PolicyDecision(
                allowed=False,
                required_approvals=required_approvals,
                approver_roles=approver_roles,
                approval_floor_applied=False,
                has_external_steps=has_external,
                status_code=403,
                message="Environment not allowed",
            )

    if context.allowed_connector_types and has_external:
        for st in steps:
            if st in EXTERNAL_STEP_TYPES:
                connector_type = "webhook" if st == "webhook_post" else st.split("_")[0]
                if connector_type not in context.allowed_connector_types:
                    return PolicyDecision(
                        allowed=False,
                        required_approvals=required_approvals,
                        approver_roles=approver_roles,
                        approval_floor_applied=False,
                        has_external_steps=has_external,
                        status_code=403,
                        message="Connector type not allowed",
                    )

    if context.settings.disable_connectors and has_external:
        return PolicyDecision(
            allowed=False,
            required_approvals=required_approvals,
            approver_roles=approver_roles,
            approval_floor_applied=False,
            has_external_steps=has_external,
            status_code=503,
            message="Connectors are disabled",
        )

    if context.max_runtime_seconds:
        configured = context.definition.get("max_runtime_seconds")
        if configured is not None and int(configured) > context.max_runtime_seconds:
            return PolicyDecision(
                allowed=False,
                required_approvals=required_approvals,
                approver_roles=approver_roles,
                approval_floor_applied=False,
                has_external_steps=has_external,
                status_code=400,
                message="Workflow exceeds max runtime cap",
            )

    if has_external and required_approvals < 1:
        required_approvals = 1
        if not approver_roles:
            approver_roles = list(SAFE_DEFAULT_APPROVER_ROLES)
        approval_floor_applied = True

    return PolicyDecision(
        allowed=True,
        required_approvals=required_approvals,
        approver_roles=approver_roles,
        approval_floor_applied=approval_floor_applied,
        has_external_steps=has_external,
    )


def can_manage_workflow_versions(role: str) -> bool:
    return role == "admin"


def can_activate_workflow_version(role: str) -> bool:
    return role == "admin"


def can_promote_workflow_version(role: str) -> bool:
    return role == "admin"
