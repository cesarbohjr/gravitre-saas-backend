"""Revise a staged write when the user changes a detail before approving.

"Actually, make the subject Weekly update" while an email waits for a yes must
change the staged email, not leave it as it was. A revised write is a new
action: it gets a fresh approval identity, so a yes given to the old details
can never send the new ones (or the reverse).
"""
from __future__ import annotations

import re
from typing import Any

from app.core.safe_dict import safe_normalize_stored_dict
from app.services.parameter_ledger import (
    extract_complete_emails,
    get_ledger,
    ledger_patch,
)

# Writes whose details can be revised by plain field edits.
_REVISABLE_STATUSES = frozenset({"awaiting_confirm"})

_LEAD_RE = re.compile(
    r"^(?:(?:oh|ok(?:ay)?|wait|hmm|no|sorry|actually|um|uh|and|also|but|please)\b[\s,.!-]*)+",
    re.IGNORECASE,
)
_TRAIL_RE = re.compile(r"[\s,]*\b(?:instead|please|thanks|thank\s+you)\s*[.!]*\s*$", re.IGNORECASE)
_FIELD = r"(?:the\s+)?(?:email\s+|e-mail\s+)?"

_SUBJECT_RES = (
    re.compile(
        r"^(?:can\s+you\s+|could\s+you\s+|let'?s\s+)?"
        r"(?:make|change|set|update|switch|put)\s+" + _FIELD + r"subject(?:\s+line)?"
        r"\s*(?:to\s*:?\s*(?:be\s+|say\s+)?|as\s+|say\s+|:\s*|\s)(?P<v>.+)$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^" + _FIELD + r"subject(?:\s+line)?\s+(?:should\s+(?:be|say|read)|"
        r"needs\s+to\s+be|will\s+be|can\s+be)\s*:?\s*(?P<v>.+)$",
        re.IGNORECASE,
    ),
    re.compile(r"^(?:use|call\s+it)\s+(?P<v>.+?)\s+(?:as|for)\s+the\s+subject(?:\s+line)?$", re.IGNORECASE),
)
_BODY_RES = (
    re.compile(
        r"^(?:can\s+you\s+|could\s+you\s+|let'?s\s+)?"
        r"(?:make|have)\s+(?:it|the\s+(?:email|message|body))\s+say\s*:?\s*(?P<v>.+)$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?:can\s+you\s+|could\s+you\s+|let'?s\s+)?"
        r"(?:make|change|set|update|switch)\s+" + _FIELD + r"(?:message|body|text)"
        r"\s*(?:to\s*:?\s*(?:say\s+)?|:\s*)(?P<v>.+)$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^" + _FIELD + r"(?:message|body|text)\s+(?:should\s+(?:be|say|read)|"
        r"needs\s+to\s+say|will\s+say)\s*:?\s*(?P<v>.+)$",
        re.IGNORECASE,
    ),
    re.compile(r"^(?:tell|let)\s+(?:her|him|them)\s+(?:know\s+)?(?:that\s+)?(?P<v>.+?)\s+instead\W*$", re.IGNORECASE),
)
_RECIPIENT_RE = re.compile(
    r"\b(?:send\s+it\s+to|send\s+(?:this|that|the\s+email)\s+to|address\s+it\s+to|"
    r"change\s+the\s+(?:recipient|address|to\s+address)\s+to|use|go\s+to|"
    r"the\s+(?:recipient|address)\s+(?:should\s+be|is))\b",
    re.IGNORECASE,
)

_FIELD_WORDS = {"subject": "the subject", "body": "the message", "to": "the recipient"}


def _clean(value: str) -> str:
    v = _TRAIL_RE.sub("", value or "").strip()
    v = v.strip(" \"'“”‘’")
    return v.strip()


def _subject_value(raw: str) -> str:
    v = _clean(raw).rstrip(".!")
    return v.strip(" \"'“”")[:300]


def _body_value(raw: str) -> str:
    v = _clean(raw)
    if not v:
        return ""
    v = v[0].upper() + v[1:]
    if v[-1] not in ".!?":
        v += "."
    return v


def _is_email_send(invoke_action: str) -> bool:
    action = (invoke_action or "").lower()
    return action.split(".", 1)[0] in {"gmail", "outlook", "microsoft_outlook"} and "send" in action


def parse_field_edits(message: str, *, invoke_action: str) -> dict[str, str]:
    """Explicit field changes in one reply ("make the subject X"), or {}."""
    if not _is_email_send(invoke_action):
        return {}
    text = (message or "").strip()
    text = _LEAD_RE.sub("", text).strip()
    if not text or "?" in text:
        return {}
    edits: dict[str, str] = {}
    for pattern in _SUBJECT_RES:
        m = pattern.match(text)
        if m:
            value = _subject_value(m.group("v"))
            if value:
                edits["subject"] = value
            break
    if not edits:
        for pattern in _BODY_RES:
            m = pattern.match(text)
            if m:
                value = _body_value(m.group("v"))
                if value:
                    edits["body"] = value
                break
    if not edits and _RECIPIENT_RE.search(text):
        emails = extract_complete_emails(text)
        if len(emails) == 1:
            edits["to"] = emails[0]
    return edits


def revisable_pending_write(task_state: dict[str, Any] | None) -> dict[str, Any] | None:
    """The staged connector write the user can still change, or None."""
    state = task_state if isinstance(task_state, dict) else {}
    pending = state.get("pending_task")
    if not isinstance(pending, dict):
        return None
    if str(pending.get("type") or "connector_action") != "connector_action":
        return None
    if str(pending.get("status") or "") not in _REVISABLE_STATUSES:
        return None
    if pending.get("execution_claim_id"):
        return None
    params = pending.get("params")
    if not isinstance(params, dict) or not params.get("invoke_action"):
        return None
    if str(params.get("kind") or "write").lower() == "read":
        return None
    return pending


def revise_pending_write(
    message: str,
    task_state: dict[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, str]] | None:
    """Apply the user's edits to the staged write.

    Returns (new pending_task, edits) or None when the reply changes nothing.
    The new pending task carries a new id and approval binding, so the old
    approval cannot run the changed action.
    """
    from app.services.approval_action_binding import bind_plan_dict

    pending = revisable_pending_write(task_state)
    if pending is None:
        return None
    params = safe_normalize_stored_dict(pending, key="params")
    args = safe_normalize_stored_dict(params, key="args")
    edits = parse_field_edits(message, invoke_action=str(params.get("invoke_action") or ""))
    edits = {k: v for k, v in edits.items() if str(args.get(k) or "") != v}
    if not edits:
        return None
    args.update(edits)
    params["args"] = args
    params = bind_plan_dict(params)
    revised = {
        **{k: v for k, v in pending.items() if k not in {"id", "pending_action_id", "expires_at"}},
        "params": params,
        "status": "awaiting_confirm",
        "revision_of": str(pending.get("id") or pending.get("pending_action_id") or ""),
    }
    return revised, edits


def describe_edits(edits: dict[str, str]) -> str:
    names = [_FIELD_WORDS.get(k, k) for k in edits]
    if len(names) == 1:
        return f"Got it, I changed {names[0]}."
    return f"Got it, I changed {', '.join(names[:-1])} and {names[-1]}."


def execution_plan_with_revised_args(
    task_state: dict[str, Any] | None,
    *,
    invoke_action: str,
    args: dict[str, Any],
) -> dict[str, Any] | None:
    """Carry the revised details onto the matching ExecutionPlan step.

    The plan-first resolver prefers the step's args over pending_task, so a
    step still holding the old details would send them.
    """
    state = task_state if isinstance(task_state, dict) else {}
    raw = state.get("execution_plan")
    if not isinstance(raw, dict) or not isinstance(raw.get("steps"), list):
        return None
    changed = False
    steps: list[Any] = []
    for step in raw["steps"]:
        if not isinstance(step, dict):
            steps.append(step)
            continue
        meta = step.get("meta") if isinstance(step.get("meta"), dict) else {}
        action = str(step.get("action_key") or meta.get("invoke_action") or "")
        if action == invoke_action and isinstance(meta.get("args"), dict) and meta.get("args"):
            steps.append({**step, "meta": {**meta, "args": dict(args)}})
            changed = True
        else:
            steps.append(step)
    if not changed:
        return None
    return {**raw, "steps": steps}


async def apply_staged_write_revision(
    message: str,
    task_state: dict[str, Any] | None,
    *,
    org_id: str,
    conversation_id: str | None,
    client: Any = None,
    settings: Any = None,
) -> tuple[str, dict[str, Any]] | None:
    """Save the revised write and return (reply, refreshed state), or None.

    Shared by the text/voice live path and the connector turn, so both
    surfaces change the staged write the same way.
    """
    from app.core.logging import get_logger
    from app.services.chat_connector_execution_service import (
        ChatConnectorExecutionService,
    )
    from app.services.connector_action_workflows import format_write_approval_message
    from app.services.conversation_state_service import get_conversation_state_service

    if not conversation_id or not org_id:
        return None
    revision = revise_pending_write(message, task_state)
    if revision is None:
        return None
    revised, edits = revision
    params = revised["params"]
    patch: dict[str, Any] = {"pending_task": revised, "clarified_params": params}
    plan_dict = execution_plan_with_revised_args(
        task_state,
        invoke_action=str(params.get("invoke_action") or ""),
        args=safe_normalize_stored_dict(params, key="args"),
    )
    if plan_dict is not None:
        patch["execution_plan"] = plan_dict
    # The ledger remembers the user's latest words for each field; keep it in
    # step so a later resume does not bring the old value back.
    ledger = get_ledger(task_state)
    for key, value in edits.items():
        ledger.upsert(key, value, source="user_message", force=True)
    patch.update(ledger_patch(ledger))
    state_svc = get_conversation_state_service(settings) if settings else get_conversation_state_service()
    await state_svc.update_task_state(conversation_id, org_id, patch, client=client)
    refreshed = await state_svc.get_task_state(conversation_id, org_id, client=client)
    plan = ChatConnectorExecutionService.plan_from_dict(params)
    get_logger(__name__).info(
        "staged_write_revised conversation_id=%s fields=%s",
        conversation_id,
        ",".join(sorted(edits)),
    )
    return f"{describe_edits(edits)}\n\n{format_write_approval_message(plan)}", refreshed
