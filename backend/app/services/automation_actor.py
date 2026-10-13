"""Who an event-triggered run is attributed to.

Runs started by a webhook or provider event used to be attributed to whichever
member row the database returned first (unordered, any role) or, failing that,
to the org id, which is not a user and cannot satisfy the
``workflow_runs.triggered_by`` foreign key. Attribution is now deterministic and
accountable, in this order:

1. the admin who configured the trigger (``configured_by``), while still an
   owner or admin of the org;
2. the workflow's creator, while still an owner, admin or member;
3. the earliest owner of the org.

If none applies the run is not started. The actor is recorded for audit and
run ownership only: a triggered run with writes still waits for human approval.
"""
from __future__ import annotations

from typing import Any

_CONFIGURER_ROLES = frozenset({"owner", "admin"})
_CREATOR_ROLES = frozenset({"owner", "admin", "member"})


def resolve_automation_actor(
    client: Any,
    org_id: str,
    *,
    configured_by: str | None = None,
    workflow_created_by: str | None = None,
) -> str | None:
    rows = (
        client.table("organization_members")
        .select("user_id,role,created_at")
        .eq("org_id", org_id)
        .order("created_at")
        .execute()
    ).data or []
    roles = {str(r.get("user_id")): str(r.get("role") or "").lower() for r in rows if r.get("user_id")}
    if configured_by and roles.get(str(configured_by)) in _CONFIGURER_ROLES:
        return str(configured_by)
    if workflow_created_by and roles.get(str(workflow_created_by)) in _CREATOR_ROLES:
        return str(workflow_created_by)
    for row in rows:
        if str(row.get("role") or "").lower() == "owner" and row.get("user_id"):
            return str(row["user_id"])
    return None


def configured_by_from_parameters(parameters: dict[str, Any] | None) -> str | None:
    trigger = (parameters or {}).get("trigger")
    if isinstance(trigger, dict) and trigger.get("configured_by"):
        return str(trigger["configured_by"])
    return None


NO_ACTOR_REASON = "no_accountable_member"
