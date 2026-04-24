"""BE-20: Policy resolution, role validation, concurrency check."""
from __future__ import annotations

from supabase import Client

from app.config import Settings
from app.workflows.constants import (
    ALLOWED_ROLES,
    EXECUTE_ALLOWED_STEP_TYPES,
    SAFE_DEFAULT_APPROVER_ROLES,
    SAFE_DEFAULT_REQUIRED_APPROVALS,
)


class PolicyResolutionError(Exception):
    """Raised when policy or role cannot be resolved."""


def resolve_policy(
    client: Client,
    org_id: str,
    workflow_id: str,
    run_type: str = "execute",
) -> tuple[int, list[str]]:
    """
    Resolve policy: 1) workflow-specific, 2) org default, 3) safe default.
    Returns (required_approvals, approver_roles).
    """
    # 1) Workflow-specific
    r = (
        client.table("approval_policies")
        .select("required_approvals, approver_roles, run_types")
        .eq("org_id", org_id)
        .eq("workflow_id", workflow_id)
        .limit(1)
        .execute()
    )
    if r.data and len(r.data) > 0:
        row = r.data[0]
        if run_type in (row.get("run_types") or []):
            return (
                int(row.get("required_approvals", 1)),
                list(row.get("approver_roles") or []),
            )
    # 2) Org default (workflow_id IS NULL)
    r = (
        client.table("approval_policies")
        .select("required_approvals, approver_roles, run_types")
        .eq("org_id", org_id)
        .is_("workflow_id", None)
        .limit(1)
        .execute()
    )
    if r.data and len(r.data) > 0:
        row = r.data[0]
        if run_type in (row.get("run_types") or []):
            return (
                int(row.get("required_approvals", 1)),
                list(row.get("approver_roles") or []),
            )
    # 3) Safe default
    return SAFE_DEFAULT_REQUIRED_APPROVALS, list(SAFE_DEFAULT_APPROVER_ROLES)


def get_user_role(client: Client, org_id: str, user_id: str) -> str:
    """
    Get organization_members.role for user. Raises PolicyResolutionError if
    role is missing or not in ALLOWED_ROLES (stop condition).
    """
    r = (
        client.table("organization_members")
        .select("role")
        .eq("org_id", org_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    if not r.data or len(r.data) == 0:
        raise PolicyResolutionError("User has no organization membership")
    role = (r.data[0].get("role") or "").strip().lower()
    if not role or role not in ALLOWED_ROLES:
        raise PolicyResolutionError(f"Invalid or missing role: {role!r}; allowed: {ALLOWED_ROLES}")
    return role


def can_approve(role: str, approver_roles: list[str]) -> bool:
    """Check if role is in approver_roles."""
    return role in (approver_roles or [])


def check_concurrency(
    client: Client,
    org_id: str,
    workflow_id: str,
    environment_name: str = "default",
) -> str | None:
    """
    Check for active execute run. Returns active_run_id if one exists, else None.
    Active = run_type=execute AND status IN (pending_approval, running).
    """
    r = (
        client.table("workflow_runs")
        .select("id")
        .eq("org_id", org_id)
        .eq("workflow_id", workflow_id)
        .eq("environment", environment_name)
        .eq("run_type", "execute")
        .in_("status", ["pending_approval", "running"])
        .limit(1)
        .execute()
    )
    if r.data and len(r.data) > 0:
        return str(r.data[0]["id"])
    return None


def validate_execute_steps(definition: dict) -> None:
    """Validate all steps are in EXECUTE_ALLOWED_STEP_TYPES; email_send requires connector_id. Raises ValueError."""
    steps = definition.get("steps") or []
    for i, s in enumerate(steps):
        stype = (s.get("type") or "").strip()
        if stype not in EXECUTE_ALLOWED_STEP_TYPES:
            raise ValueError(
                f"Step {i} has type {stype!r}; execute only allows: {sorted(EXECUTE_ALLOWED_STEP_TYPES)}"
            )
        if stype == "email_send":
            cfg = s.get("config") or {}
            if not cfg.get("connector_id"):
                raise ValueError(f"Step {i} (email_send) requires config.connector_id for execute")
        if stype == "webhook_post":
            cfg = s.get("config") or {}
            if not cfg.get("connector_id"):
                raise ValueError(f"Step {i} (webhook_post) requires config.connector_id for execute")
