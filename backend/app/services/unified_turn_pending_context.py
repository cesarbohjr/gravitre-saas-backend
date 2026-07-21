"""Structured pending-state context for the unified turn reasoning call."""
from __future__ import annotations

from typing import Any

from app.connectors.action_catalog.action_workflow_schema import get_workflow_schema
from app.services.pending_reply_classifier import build_pending_snapshot, has_pending_family


def _label_for_missing_field(action_key: str, field_key: str) -> str:
    key = str(field_key or "").strip().lower()
    if not key:
        return field_key
    schema = get_workflow_schema(action_key) if action_key else None
    if schema is not None:
        for spec in (*schema.required_fields, *schema.optional_fields):
            if key in {k.lower() for k in spec.arg_keys} or key == str(spec.label or "").lower():
                return str(spec.label or field_key)
    return field_key.replace("_", " ").strip().title()


def build_unified_turn_pending_context(
    task_state: dict[str, Any] | None,
    *,
    last_assistant_message: str | None = None,
) -> str:
    """Human-oriented pending summary for the model (not for end users verbatim)."""
    if not has_pending_family(task_state):
        return ""

    snap = build_pending_snapshot(task_state)
    action_key = snap.invoke_action or ""
    action_label = (snap.action_label or "").strip()
    if action_key and action_label == action_key:
        from app.services.user_facing_copy_guard import humanize_catalog_action_key

        action_label = humanize_catalog_action_key(action_key)

    lines = [
        "PENDING STATE (use for reasoning; never expose internal catalog ids to the user):",
        f"- Status: {snap.status or '(none)'}",
        f"- Pending type: {snap.pending_type or '(none)'}",
    ]
    if action_label:
        lines.append(f"- In-progress action: {action_label}")
    if snap.integration:
        lines.append(f"- Connector: {snap.integration}")
    if snap.plan_goal:
        lines.append(f"- Plan goal: {snap.plan_goal[:400]}")
    if snap.pending_missing:
        pretty = [
            _label_for_missing_field(action_key, item) for item in snap.pending_missing[:12]
        ]
        lines.append(f"- Still needed: {', '.join(pretty)}")
    if snap.hold_prompt_active:
        lines.append("- User was asked whether to hold or abandon the pending item.")
    snippet = (last_assistant_message or "").strip()
    if snippet:
        lines.append(f"- Last assistant message (context): {snippet[:500]}")
    return "\n".join(lines)
