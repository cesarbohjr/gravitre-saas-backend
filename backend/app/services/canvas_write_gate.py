"""Canvas / workflow-execute adapter around catalog write authority.

Classification of write vs read is NOT implemented here. This module only:
1. Maps workflow steps → invoke action keys
2. Asks ``catalog_write_authority.invoke_action_requires_write_approval``
   (same schema-derived source of truth as chat/ReAct)
3. Enforces run-level approval requirements before those writes execute

Chat/ReAct previously gated writes via catalog_write_authority; canvas execute
relied on optional BE-20 policies and in-graph approval nodes — a parallel,
weaker path. This adapter closes that gap without a second classification.
"""
from __future__ import annotations

from typing import Any

from app.services.catalog_write_authority import invoke_action_requires_write_approval
from app.services.conversation_turn_controller import bind_canvas_step_args
from app.services.tool_service import STEP_TYPE_TO_ACTION

CANVAS_WRITE_AUTHORITY_BLOCKED = "canvas_write_authority_blocked"

# Legacy external step types (always treated as writes for the approval floor).
EXTERNAL_WRITE_STEP_TYPES = frozenset({"slack_post_message", "email_send", "webhook_post"})


def _invoke_action_from_step(step: dict[str, Any]) -> str | None:
    stype = str(step.get("type") or "").strip()
    if stype in STEP_TYPE_TO_ACTION:
        return STEP_TYPE_TO_ACTION[stype]
    if stype == "invoke_tool":
        cfg = step.get("config") if isinstance(step.get("config"), dict) else {}
        action = cfg.get("action") or cfg.get("tool_action")
        text = str(action or "").strip()
        return text or None
    return None


def _iter_definition_steps(definition: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(definition, dict):
        return []
    steps = definition.get("steps")
    out: list[dict[str, Any]] = []
    if isinstance(steps, list):
        out.extend(s for s in steps if isinstance(s, dict))
    graph = definition.get("graph")
    if isinstance(graph, dict):
        nodes = graph.get("nodes")
        if isinstance(nodes, list):
            for node in nodes:
                if not isinstance(node, dict):
                    continue
                out.append(
                    {
                        "id": node.get("id"),
                        "type": node.get("type") or node.get("node_type"),
                        "config": node.get("config") if isinstance(node.get("config"), dict) else {},
                    }
                )
    return out


def definition_has_catalog_write_steps(definition: dict[str, Any] | None) -> bool:
    """True when any step is a catalog (or legacy external) write."""
    for step in _iter_definition_steps(definition):
        stype = str(step.get("type") or "").strip()
        if stype in EXTERNAL_WRITE_STEP_TYPES:
            return True
        action = _invoke_action_from_step(step)
        if action and invoke_action_requires_write_approval(action):
            return True
    return False


def run_allows_catalog_write_execution(run_row: dict[str, Any] | None) -> bool:
    """Writes may proceed only when the run required and received approval.

    Auto-approved runs created with ``required_approvals=0`` must not execute writes.
    """
    if not isinstance(run_row, dict):
        return False
    try:
        required = int(run_row.get("required_approvals") or 0)
    except (TypeError, ValueError):
        required = 0
    status = str(run_row.get("approval_status") or "").strip().lower()
    if required < 1:
        return False
    return status in {"approved"}


def block_canvas_write_step(
    *,
    step_type: str,
    config: dict[str, Any] | None,
    run_row: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Return a failure payload when this write step must not execute."""
    stype = str(step_type or "").strip()
    action: str | None = None
    if stype in EXTERNAL_WRITE_STEP_TYPES:
        action = STEP_TYPE_TO_ACTION.get(stype)
    elif stype == "invoke_tool":
        cfg = config if isinstance(config, dict) else {}
        action = str(cfg.get("action") or cfg.get("tool_action") or "").strip() or None
    if not action or not invoke_action_requires_write_approval(action):
        return None
    if run_allows_catalog_write_execution(run_row):
        return None
    # User-facing copy owned by Module D gravitree_voice (same SoT as chat/ReAct).
    from app.services.gravitree_voice import format_operator_message

    return {
        "success": False,
        "error_code": CANVAS_WRITE_AUTHORITY_BLOCKED,
        "error": format_operator_message(
            "canvas_write_blocked",
            confidence_register="blocked",
            allow_humor=False,
        ),
        "action": action,
        "pending_approval": True,
    }


def load_run_for_write_gate(client: Any, org_id: str, run_id: str | None) -> dict[str, Any] | None:
    if not client or not run_id:
        return None
    try:
        rows = (
            client.table("workflow_runs")
            .select("id, status, approval_status, required_approvals")
            .eq("id", run_id)
            .eq("org_id", org_id)
            .limit(1)
            .execute()
        )
        if rows.data:
            return dict(rows.data[0])
    except Exception:  # noqa: BLE001
        return None
    return None


def enrich_canvas_step_config_from_ledger(
    *,
    invoke_action: str,
    config: dict[str, Any] | None,
    task_state: dict[str, Any] | None = None,
    intent_text: str | None = None,
) -> dict[str, Any]:
    """Module B — canvas NL→args via the same ledger/schema path as chat/ReAct."""
    return bind_canvas_step_args(
        invoke_action=invoke_action,
        step_config=config,
        task_state=task_state,
        intent_text=intent_text,
    )
