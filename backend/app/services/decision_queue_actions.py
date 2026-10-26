"""Decision queue actions on a pending request: edit before approving, delegate, snooze.

A request is either a workflow run waiting at its execute gate (``workflow_runs``) or a
queued write in ``approvals`` (chat connector writes, MCP tool calls, browser extension
writes). Snooze and delegation live in ``decision_queue_states``; an edit rewrites the
stored arguments the approve path executes, and re-binds them so approval still runs
exactly what the approver saw.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException, status

from app.auth.org_role_permissions import capability_denied_detail, has_capability
from app.core.safe_dict import safe_normalize_stored_dict
from app.workflows.audit import write_audit_event
from app.workflows.policy import PolicyResolutionError, get_member_role, get_user_role, widen_to_member_role

STATE_TABLE = "decision_queue_states"
MAX_SNOOZE = timedelta(days=7)
MIN_SNOOZE = timedelta(minutes=5)
#: Run parameters the platform sets; an edit keeps their stored values.
RESERVED_RUN_KEYS = frozenset({"source", "conversation_id", "label", "agent_id", "goal_id", "job_id", "play_id"})
EXTENSION_TYPES = frozenset({"extension_write", "extension_workflow"})
STATE_FIELDS = (
    "approval_id, snoozed_until, snoozed_by, delegated_to, delegated_by, delegated_at, "
    "delegate_note, edited_by, edited_at"
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _require_approver(client: Any, org_id: str, user_id: str) -> None:
    try:
        role = widen_to_member_role(get_user_role, client, org_id, user_id)
    except PolicyResolutionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    if not has_capability(client, org_id, role, "approve_writes"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=capability_denied_detail("approve_writes"))


def _load_request(client: Any, org_id: str, environment_name: str, approval_id: str) -> dict[str, Any]:
    """The pending request behind ``approval_id``: ``{"kind": "run"|"queued", "row": ...}``."""
    try:
        rows = (
            client.table("approvals")
            .select("id, type, status, context, reviewed_at")
            .eq("id", approval_id)
            .eq("org_id", org_id)
            .limit(1)
            .execute()
            .data
            or []
        )
    except Exception:  # noqa: BLE001 — some deployments and mocks have no approvals table
        rows = []
    if rows:
        row = rows[0]
        if str(row.get("status") or "") != "pending" or row.get("reviewed_at"):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Approval already resolved")
        return {"kind": "queued", "row": row}
    runs = (
        client.table("workflow_runs")
        .select("id, status, approval_status, parameters, environment")
        .eq("id", approval_id)
        .eq("org_id", org_id)
        .eq("environment", environment_name)
        .limit(1)
        .execute()
        .data
        or []
    )
    if not runs:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    run = runs[0]
    if str(run.get("status") or "") != "pending_approval":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Approval already resolved")
    return {"kind": "run", "row": run}


def _upsert_state(client: Any, org_id: str, approval_id: str, fields: dict[str, Any]) -> dict[str, Any]:
    payload = {"org_id": org_id, "approval_id": approval_id, **fields, "updated_at": _now().isoformat()}
    rows = (
        client.table(STATE_TABLE)
        .upsert(payload, on_conflict="org_id,approval_id")
        .execute()
        .data
        or []
    )
    return rows[0] if rows else payload


def load_states(client: Any, org_id: str, approval_ids: list[str]) -> dict[str, dict[str, Any]]:
    """Snooze, delegation and edit state per approval id. Empty when the table is missing."""
    ids = [i for i in dict.fromkeys(approval_ids) if i]
    if not ids:
        return {}
    try:
        rows = (
            client.table(STATE_TABLE)
            .select(STATE_FIELDS)
            .eq("org_id", org_id)
            .in_("approval_id", ids)
            .execute()
            .data
            or []
        )
    except Exception:  # noqa: BLE001 — table not migrated yet: the queue works without it
        return {}
    return {str(r.get("approval_id")): r for r in rows if isinstance(r, dict)}


def _parse(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def editable_parameters(item: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    """What an approver may edit on a listed request, or why it can't be edited."""
    gate = str(item.get("gate_type") or "")
    if gate.startswith("browser_extension") or str(item.get("type") or "").startswith("extension_"):
        return None, "Browser extension writes run exactly as confirmed in the page. Reject and ask again to change one."
    if gate == "chat_orchestration_plan":
        return None, "Chat plans are approved as a whole. Reject with a reason to get a new plan."
    ctx = item.get("context") if isinstance(item.get("context"), dict) else {}
    if gate == "execute":
        params = item.get("request") if isinstance(item.get("request"), dict) else {}
        editable = {k: v for k, v in params.items() if k not in RESERVED_RUN_KEYS and not str(k).startswith("_")}
        return (editable, None) if editable else (None, "This run has no inputs to edit.")
    args = ctx.get("args") if isinstance(ctx.get("args"), dict) else None
    if args is None:
        args = ctx.get("parameters") if isinstance(ctx.get("parameters"), dict) else None
    if args:
        return dict(args), None
    return None, "This request has no arguments to edit."


def apply_states(items: list[dict[str, Any]], states: dict[str, dict[str, Any]], user_labels: dict[str, str]) -> None:
    """Stamp snooze, delegation and edit fields onto listed requests (in place)."""
    now = _now()
    for item in items:
        params, blocked = editable_parameters(item)
        item["editable_parameters"] = params if item.get("status") == "pending" else None
        item["edit_blocked_reason"] = blocked
        state = states.get(str(item.get("id") or ""))
        if not state:
            continue
        until = _parse(state.get("snoozed_until"))
        if until and until > now and item.get("status") == "pending":
            item["snoozed_until"] = until.isoformat()
            item["snoozed_by_name"] = user_labels.get(str(state.get("snoozed_by") or ""))
        delegated_to = str(state.get("delegated_to") or "")
        if delegated_to:
            item["delegated_to"] = delegated_to
            item["delegated_to_name"] = user_labels.get(delegated_to)
            item["delegated_by_name"] = user_labels.get(str(state.get("delegated_by") or ""))
            item["delegated_at"] = state.get("delegated_at")
            item["delegate_note"] = state.get("delegate_note")
        if state.get("edited_at"):
            item["edited_at"] = state.get("edited_at")
            item["edited_by_name"] = user_labels.get(str(state.get("edited_by") or ""))


def state_user_ids(states: dict[str, dict[str, Any]]) -> set[str]:
    out: set[str] = set()
    for state in states.values():
        for key in ("snoozed_by", "delegated_to", "delegated_by", "edited_by"):
            if state.get(key):
                out.add(str(state[key]))
    return out


# --------------------------------------------------------------------------- snooze


def snooze_request(
    client: Any, *, org_id: str, environment_name: str, approval_id: str, user_id: str, until: datetime | None
) -> dict[str, Any]:
    """Hide a pending request from "Waiting on you" until ``until``; ``None`` brings it back now."""
    _require_approver(client, org_id, user_id)
    _load_request(client, org_id, environment_name, approval_id)
    if until is not None:
        if until.tzinfo is None:
            until = until.replace(tzinfo=timezone.utc)
        delta = until - _now()
        if delta < MIN_SNOOZE:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Snooze for at least 5 minutes")
        if delta > MAX_SNOOZE:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Snooze for 7 days at most")
    _upsert_state(
        client,
        org_id,
        approval_id,
        {"snoozed_until": until.isoformat() if until else None, "snoozed_by": user_id if until else None},
    )
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=user_id,
        action="approval.snoozed" if until else "approval.unsnoozed",
        resource_type="approval",
        resource_id=approval_id,
        metadata={"snoozed_until": until.isoformat() if until else None},
    )
    return {"approval_id": approval_id, "snoozed_until": until.isoformat() if until else None}


# --------------------------------------------------------------------------- delegate


def delegate_request(
    client: Any,
    *,
    org_id: str,
    environment_name: str,
    approval_id: str,
    user_id: str,
    delegate_to: str,
    note: str | None,
    title: str | None = None,
) -> dict[str, Any]:
    """Hand a pending request to a teammate who can approve writes, and notify them."""
    _require_approver(client, org_id, user_id)
    _load_request(client, org_id, environment_name, approval_id)
    if delegate_to == user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Pick someone other than yourself")
    try:
        role = get_member_role(client, org_id, delegate_to)
    except PolicyResolutionError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="That person is not in this workspace") from exc
    if not has_capability(client, org_id, role, "approve_writes"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="That person's role can't approve writes. Pick someone who can.",
        )
    clean_note = (note or "").strip()[:500] or None
    stamp = _now().isoformat()
    _upsert_state(
        client,
        org_id,
        approval_id,
        {"delegated_to": delegate_to, "delegated_by": user_id, "delegated_at": stamp, "delegate_note": clean_note},
    )
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=user_id,
        action="approval.delegated",
        resource_type="approval",
        resource_id=approval_id,
        metadata={"delegated_to": delegate_to, "note": clean_note},
    )
    try:
        from app.services.notification_emitter import create_user_notification

        create_user_notification(
            client,
            org_id=org_id,
            user_id=delegate_to,
            notification_type="approval_delegated",
            title=f"Decision handed to you: {title}" if title else "A decision was handed to you",
            body=clean_note or "Open the decision queue to approve or reject it.",
            url=f"/approvals?id={approval_id}",
            entity_type="approval",
            entity_id=approval_id,
        )
    except Exception:  # noqa: BLE001 — the hand-off stands even if the notice fails
        pass
    return {"approval_id": approval_id, "delegated_to": delegate_to, "delegated_at": stamp, "delegate_note": clean_note}


# --------------------------------------------------------------------------- edit


def _edit_run(client: Any, org_id: str, run: dict[str, Any], edited: dict[str, Any]) -> dict[str, Any]:
    original = run.get("parameters") if isinstance(run.get("parameters"), dict) else {}
    reserved = {k: v for k, v in original.items() if k in RESERVED_RUN_KEYS or str(k).startswith("_")}
    merged = {**{k: v for k, v in edited.items() if k not in reserved}, **reserved}
    updated = (
        client.table("workflow_runs")
        .update({"parameters": merged})
        .eq("id", str(run["id"]))
        .eq("org_id", org_id)
        .eq("status", "pending_approval")
        .execute()
        .data
        or []
    )
    if not updated:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Approval already resolved")
    return original


def _edit_mcp(client: Any, org_id: str, row: dict[str, Any], edited: dict[str, Any]) -> dict[str, Any]:
    from app.services.mcp_client_service import mcp_input_sha256

    ctx = safe_normalize_stored_dict(row, key="context")
    original = safe_normalize_stored_dict(ctx, key="parameters")
    execution_id = str(ctx.get("mcp_execution_id") or "")
    if not execution_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Proposal is incomplete; request fresh approval")
    digest = mcp_input_sha256(edited)
    moved = (
        client.table("mcp_tool_executions")
        .update({"input": edited})
        .eq("id", execution_id)
        .eq("org_id", org_id)
        .eq("approval_id", str(row["id"]))
        .eq("status", "pending_approval")
        .execute()
        .data
        or []
    )
    if not moved:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Proposal no longer matches this approval")
    client.table("approvals").update(
        {"context": {**ctx, "parameters": edited, "input_sha256": digest}}
    ).eq("id", str(row["id"])).eq("org_id", org_id).eq("status", "pending").execute()
    return original


def _edit_connector_chat(settings: Any, client: Any, org_id: str, row: dict[str, Any], edited: dict[str, Any]) -> dict[str, Any]:
    from app.services.approval_action_binding import digest_plan_args
    from app.services.chat_connector_execution_service import get_chat_connector_execution_service

    ctx = safe_normalize_stored_dict(row, key="context")
    original = safe_normalize_stored_dict(ctx, key="parameters")
    binding = ctx.get("binding") if isinstance(ctx.get("binding"), dict) else {}
    if not binding:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This request predates editing. Reject and ask again.")
    service = get_chat_connector_execution_service(settings)
    plan = service.plan_action(
        "",
        connected_integrations=[],
        task_state={
            "pending_task": {"type": "connector_action", "status": "awaiting_admin_approval", "params": edited},
            "clarified_params": edited,
        },
    )
    if not plan:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="The edited request is incomplete")
    # An edit changes arguments only: the tool, action and app stay what was requested.
    for key, value in (("tool_name", plan.tool_name), ("invoke_action", plan.invoke_action), ("integration", plan.integration)):
        if str(binding.get(key) or "") != str(value or ""):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Edits can change the values sent, not which app or action runs.",
            )
    client.table("approvals").update(
        {"context": {**ctx, "parameters": edited, "binding": {**binding, "args_digest": digest_plan_args(plan.args)}}}
    ).eq("id", str(row["id"])).eq("org_id", org_id).eq("status", "pending").execute()
    return original


def edit_request(
    client: Any,
    settings: Any,
    *,
    org_id: str,
    environment_name: str,
    approval_id: str,
    user_id: str,
    parameters: dict[str, Any],
) -> dict[str, Any]:
    """Rewrite a pending request's arguments so the next approval runs the edited version."""
    if not isinstance(parameters, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Parameters must be an object")
    _require_approver(client, org_id, user_id)
    found = _load_request(client, org_id, environment_name, approval_id)
    row = found["row"]
    if found["kind"] == "run":
        original = _edit_run(client, org_id, row, parameters)
    else:
        kind = str(row.get("type") or "")
        if kind in EXTENSION_TYPES:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Browser extension writes can't be edited. Reject and ask again.",
            )
        if kind == "mcp_tool":
            original = _edit_mcp(client, org_id, row, parameters)
        elif kind == "connector_chat":
            original = _edit_connector_chat(settings, client, org_id, row, parameters)
        else:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This request can't be edited")
    existing = load_states(client, org_id, [approval_id]).get(approval_id) or {}
    stamp = _now().isoformat()
    fields: dict[str, Any] = {"edited_by": user_id, "edited_at": stamp}
    # Keep the first version the agent asked for, however many edits follow.
    if not existing.get("edited_at"):
        fields["original_parameters"] = original
    try:
        _upsert_state(client, org_id, approval_id, fields)
    except Exception:  # noqa: BLE001 — the edit itself is stored; the audit row below keeps the record
        pass
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=user_id,
        action="approval.edited",
        resource_type="approval",
        resource_id=approval_id,
        metadata={"before": original, "after": parameters},
    )
    return {"approval_id": approval_id, "edited_at": stamp, "parameters": parameters}
