"""2.0-D — compile governed WRITEs. Never invoke. Never auto-approve."""
from __future__ import annotations

import re
from typing import Any

from app.config import Settings, get_settings
from app.connectors.action_catalog.f1_write_slice import is_f1_write_action
from app.connectors.action_catalog.registry import get_action_spec
from app.services.clarification_policy import format_not_connected_message
from app.services.connector_semantic_registry import connector_display_name
from app.services.write_preflight import preflight_write_action

_SEND_EMAIL = re.compile(
    r"(?is)^\s*(send an email|email this|draft an email|send email|create a draft)\b"
)


async def try_governed_write_compile_turn(
    *,
    message: str,
    org_id: str,
    client: Any,
    settings: Settings | None,
    connected_integrations: list[str] | None,
    task_state: dict[str, Any] | None,
) -> dict[str, Any] | None:
    from app.services.chat_write_intent import DRAFT_INTENT

    asked_for_draft = bool(DRAFT_INTENT.search(message or ""))
    if not _SEND_EMAIL.search(message or "") and not asked_for_draft:
        return None
    connected = [str(v).strip().lower() for v in (connected_integrations or []) if str(v).strip()]
    # "Send an email about the draft proposal" is a send, not a draft.
    draft_only = asked_for_draft
    action_key = "gmail.drafts.create" if draft_only else "gmail.messages.send"
    if "gmail" not in connected:
        return {
            "stop_pipeline": True,
            "dialogue_mode": "answer",
            "message": format_not_connected_message(
                "gmail",
                display_name=connector_display_name("gmail"),
            ),
            "task_state": task_state or {},
            "workflow_status": "connector_not_connected",
            "execution_path": "governed_write_compile",
        }
    # Connected send: the request goes to the shared draft path (pending task,
    # parameter ledger, one approval prompt), which keeps it across turns and
    # asks only for what is missing. Answering here asked for every detail at
    # once and kept nothing, so "Gmail." or "No." on the next turn had no
    # draft to apply to (the Stephanie conversation, 2026-10-11).
    if not draft_only:
        return None
    if not is_f1_write_action(action_key):
        # Gmail drafts are not a governed write yet. Saying so beats "That
        # tool isn't connected yet" (Gmail is connected) or quietly turning
        # the draft into a send.
        return {
            "stop_pipeline": True,
            "dialogue_mode": "answer",
            "message": (
                "I can't save drafts in Gmail yet, so nothing was saved. "
                "I can write the email out here for you to copy, or send it "
                "once you've approved it. Which would you like?"
            ),
            "task_state": task_state or {},
            "workflow_status": "completed",
            "execution_path": "governed_write_compile",
        }
    proof = preflight_write_action(
        action_spec=get_action_spec(action_key),
        context={
            "org_id": org_id,
            "client": client,
            "settings": settings or get_settings(),
            "user_message": message,
            "task_state": task_state or {},
            "connected_integrations": connected,
            "action_key": action_key,
            "proposed_args": {},
        },
    )
    if proof.ok:
        pending_copy = (
            "I can create a Gmail draft after you approve it. Nothing will be sent."
            if draft_only
            else "I can send that email after you approve it. Nothing has been sent."
        )
        return {
            "stop_pipeline": True,
            "dialogue_mode": "confirm",
            "message": pending_copy,
            "task_state": {
                **(task_state or {}),
                "pending_action": {
                    "status": "awaiting_user_confirmation",
                    "action": action_key,
                    "compiled_parameters": proof.safe_parameter_summary(),
                    "write_allowed": False,
                },
            },
            "workflow_status": "waiting_for_approval",
            "execution_path": "governed_write_compile",
            "selected_action": action_key,
        }
    if proof.error_class == "GENUINE_USER_CLARIFICATION_REQUIRED":
        return {
            "stop_pipeline": True,
            "dialogue_mode": "clarifying",
            "message": (
                "I can send it through Gmail after you approve it. "
                "Who should receive it, and what should the subject and body be?"
            ),
            "task_state": task_state or {},
            "workflow_status": "needs clarification",
            "execution_path": "governed_write_compile",
        }
    return {
        "stop_pipeline": True,
        "dialogue_mode": "answer",
        "message": proof.user_message()
        or "I couldn't compile that send yet. Nothing was sent.",
        "task_state": task_state or {},
        "workflow_status": "blocked",
        "execution_path": "governed_write_compile",
        "error_class": proof.error_class,
    }
