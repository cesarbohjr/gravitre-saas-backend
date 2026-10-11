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

# "Send it to Mike instead", "make it go to Mike", "change the recipient to
# Mike Chen": the whole reply only re-addresses the email.
_RECIPIENT_CHANGE_RE = re.compile(
    r"^(?:can\s+you\s+|could\s+you\s+|let'?s\s+)?"
    r"(?:send\s+(?:it|this|that|the\s+(?:e-?mail|message))\s+to|address\s+it\s+to|"
    r"(?:make|have)\s+it\s+go\s+to|it\s+should\s+go\s+to|"
    r"(?:change|switch|set|update)\s+the\s+(?:recipient|address|to\s+address)\s+to|"
    r"the\s+recipient\s+(?:should\s+be|is))\s+(?P<v>.+)$",
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


def parse_recipient_change(message: str) -> tuple[str, str] | None:
    """("address", email) or ("name", name) when the reply only changes who the email goes to."""
    from app.services.recipient_resolution import extract_recipient_name

    text = _LEAD_RE.sub("", (message or "").strip()).strip().rstrip("?").strip()
    m = _RECIPIENT_CHANGE_RE.match(text)
    if not m or "?" in text:
        return None
    value = _clean(m.group("v")).rstrip(".!").strip()
    emails = extract_complete_emails(value)
    if emails:
        return ("address", emails[0]) if len(emails) == 1 else None
    name = extract_recipient_name(f"to {value}", bare_ok=True)
    return ("name", name) if name else None


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


# A sent email that "send it to X instead" can still mean.
_SENT_STATUSES = frozenset({"executed", "completed"})
# A recipient change waiting on the user ("which Mike?"): the name asked
# about and, after a send, where the first email went.
RECIPIENT_CHANGE_KEY = "recipient_change"
# What a re-addressed email must not keep from the old one.
_OLD_RECIPIENT_ARGS = frozenset({"to", "email", "_user_message"})
_OLD_SEND_PARAMS = frozenset(
    {
        "status",
        "provider_record_id",
        "approval_action_id",
        "bound_tool_name",
        "bound_invoke_action",
        "bound_integration",
        "bound_args_digest",
    }
)


def _email_params(pending: Any) -> dict[str, Any] | None:
    if not isinstance(pending, dict) or str(pending.get("type") or "connector_action") != "connector_action":
        return None
    params = safe_normalize_stored_dict(pending, key="params")
    return params if _is_email_send(str(params.get("invoke_action") or "")) else None


def sent_email_write(task_state: dict[str, Any] | None) -> dict[str, Any] | None:
    """The email that already went out, which a new recipient can no longer change."""
    state = task_state if isinstance(task_state, dict) else {}
    pending = state.get("pending_task")
    params = _email_params(pending)
    if params is None or str(pending.get("status") or "") not in _SENT_STATUSES:
        return None
    result = pending.get("result")
    if not isinstance(result, dict) or result.get("success") is not True:
        return None
    return pending if str(safe_normalize_stored_dict(params, key="args").get("to") or "").strip() else None


def open_recipient_change(task_state: dict[str, Any] | None) -> dict[str, Any] | None:
    """The email waiting for the user to say which person they meant, or the address."""
    state = task_state if isinstance(task_state, dict) else {}
    pending = state.get("pending_task")
    marker = state.get(RECIPIENT_CHANGE_KEY)
    if not isinstance(marker, dict) or not marker or _email_params(pending) is None:
        return None
    return pending if str(pending.get("status") or "") == "awaiting_params" else None


def _sent_record_id(sent: dict[str, Any]) -> str:
    params = safe_normalize_stored_dict(sent, key="params")
    result = safe_normalize_stored_dict(sent, key="result")
    structured = safe_normalize_stored_dict(result, key="structured")
    return str(params.get("provider_record_id") or structured.get("provider_record_id") or result.get("entity_id") or "")


def _restaged(base: dict[str, Any], args: dict[str, Any], *, status: str, follows_write: str = "") -> dict[str, Any]:
    """The email with its new recipient: a new action with its own approval identity.

    ``follows_write`` names the sent email this one repeats, so that send's
    success is not mistaken for this one's (see ``existing_successful_write``).
    """
    from app.services.approval_action_binding import bind_plan_dict

    params = {k: v for k, v in safe_normalize_stored_dict(base, key="params").items() if k not in _OLD_SEND_PARAMS}
    params["args"] = args
    params["status"] = status
    if status == "awaiting_confirm":
        params = bind_plan_dict(params)
    keep = {
        k: base[k] for k in ("org_id", "actor_id", "conversation_id", "invoke_action", "follows_write") if base.get(k)
    }
    if follows_write:
        keep["follows_write"] = follows_write
    return {
        **keep,
        "type": "connector_action",
        "status": status,
        "params": params,
        "revision_of": str(base.get("id") or base.get("pending_action_id") or base.get("revision_of") or ""),
    }


async def _change_recipient(
    message: str,
    task_state: dict[str, Any] | None,
    *,
    org_id: str,
    conversation_id: str,
    client: Any,
    settings: Any,
    user_id: str | None,
) -> tuple[str, dict[str, Any]] | None:
    """"Send it to Mike instead": re-address the staged email, or offer a sent one again.

    A name is looked up in the user's own mail (the same lookup a new email
    uses). One match is shown for approval; several, or none, ask, and the
    email waits without a recipient so no yes can send it to the old one.
    A sent email is never changed: the reply says where it went and offers
    the same email to the new recipient, behind a new approval.
    """
    from app.core.logging import get_logger
    from app.services.chat_connector_execution_service import (
        ChatConnectorExecutionService,
    )
    from app.services.connector_action_workflows import format_write_approval_message
    from app.services.conversation_state_service import get_conversation_state_service
    from app.services.recipient_resolution import (
        CANDIDATES_KEY,
        extract_recipient_name,
        ground_email_recipient,
        pick_candidate,
        resolution_question,
        stored_candidates,
    )

    state = task_state if isinstance(task_state, dict) else {}
    change = parse_recipient_change(message)
    picked = None
    marker: dict[str, Any] = {}
    just_sent = False
    base = open_recipient_change(state)
    if base is not None:
        marker = safe_normalize_stored_dict(state, key=RECIPIENT_CHANGE_KEY)
        emails = extract_complete_emails(message)
        if change is None and len(emails) == 1:
            change = ("address", emails[0])
        if change is None:
            picked = pick_candidate(message, stored_candidates(state))
        if change is None and picked is None:
            name = extract_recipient_name(message, bare_ok=True)
            if name is None:
                return None
            change = ("name", name)
    elif change is None:
        return None
    elif revisable_pending_write(state) is not None:
        if change[0] != "name":
            return None  # a typed address is a plain field edit
        base = revisable_pending_write(state)
    else:
        base = sent_email_write(state)
        if base is None:
            return None
        sent_args = safe_normalize_stored_dict(safe_normalize_stored_dict(base, key="params"), key="args")
        marker = {"sent_to": str(sent_args.get("to") or "").strip()}
        just_sent = True

    params = safe_normalize_stored_dict(base, key="params")
    args = {k: v for k, v in safe_normalize_stored_dict(params, key="args").items() if k not in _OLD_RECIPIENT_ARGS}
    resolution = None
    who = ""
    if picked is not None:
        who = picked.name
        args["to"] = picked.address
        if picked.account:
            args["connector_id"] = picked.account
    elif change is not None and change[0] == "address":
        who = change[1]
        args["to"] = change[1]
    else:
        plan = ChatConnectorExecutionService.plan_from_dict({**params, "args": args})
        plan, grounding = await ground_email_recipient(
            plan,
            message,
            {k: v for k, v in state.items() if k != CANDIDATES_KEY},
            org_id=org_id,
            client=client,
            settings=settings,
            connected_integrations=[plan.integration] if plan.integration else None,
            user_id=user_id,
            conversation_id=conversation_id,
        )
        resolution = grounding.recipient if grounding is not None else None
        if resolution is None:
            return None
        args = dict(plan.args)
        if resolution.status == "resolved" and resolution.chosen is not None:
            who = resolution.chosen.name
        else:
            args.pop("to", None)

    follows = _sent_record_id(base) if just_sent else ""
    sent_to = str(marker.get("sent_to") or "")
    lead = f"That email already went to {sent_to}, and I can't unsend it." if just_sent else ""
    candidates: list[dict[str, Any]] = []
    if args.get("to"):
        pending = _restaged(base, args, status="awaiting_confirm", follows_write=follows)
        if not sent_to:
            offer = f"Got it, I changed the recipient to {who}."
        elif just_sent:
            offer = f"I can send the same email to {'the new address' if who == args['to'] else who}."
        else:
            offer = f"Got it, {who}."
        marker = {}
    else:
        pending = _restaged(base, args, status="awaiting_params", follows_write=follows)
        offer = (resolution_question(resolution) if resolution is not None else "") or "Who should it go to instead?"
        if resolution is not None and resolution.status != "unavailable":
            candidates = [c.to_dict() for c in resolution.candidates]
        marker = {**marker, "query": resolution.query if resolution is not None else ""}
    new_params = pending["params"]
    patch: dict[str, Any] = {
        "pending_task": pending,
        "clarified_params": new_params,
        CANDIDATES_KEY: candidates,
        RECIPIENT_CHANGE_KEY: marker,
    }
    if just_sent:
        # The finished plan belongs to the email that already went out.
        patch["execution_plan"] = None
    else:
        plan_dict = execution_plan_with_revised_args(
            state, invoke_action=str(new_params.get("invoke_action") or ""), args=args
        )
        if plan_dict is not None:
            patch["execution_plan"] = plan_dict
    # Keep the ledger in step so a resumed draft does not bring the old
    # recipient back. Slots merge on save, so an old one is blanked, not dropped.
    ledger = get_ledger(state)
    if args.get("to"):
        ledger.upsert("to", str(args["to"]), source="user_message", force=True)
    patch.update(ledger_patch(ledger))
    slots = patch["parameter_ledger"]["slots"]
    for key in ("to", "email") if not args.get("to") else ("email",):
        slots[key] = {"value": "", "source": "user_message", "confidence": "high"}
    state_svc = get_conversation_state_service(settings) if settings else get_conversation_state_service()
    await state_svc.update_task_state(conversation_id, org_id, patch, client=client)
    refreshed = await state_svc.get_task_state(conversation_id, org_id, client=client)
    get_logger(__name__).info(
        "staged_write_recipient_changed conversation_id=%s after_send=%s status=%s",
        conversation_id,
        bool(sent_to),
        pending["status"],
    )
    text = f"{lead} {offer}".strip()
    if pending["status"] == "awaiting_confirm":
        approval = format_write_approval_message(ChatConnectorExecutionService.plan_from_dict(new_params))
        text = f"{text}\n\n{approval}"
    return text, refreshed


async def apply_staged_write_revision(
    message: str,
    task_state: dict[str, Any] | None,
    *,
    org_id: str,
    conversation_id: str | None,
    client: Any = None,
    settings: Any = None,
    user_id: str | None = None,
) -> tuple[str, dict[str, Any]] | None:
    """Save the revised write and return (reply, refreshed state), or None.

    Shared by the text/voice live path and the connector turn, so both
    surfaces change the staged write the same way. A change of recipient by
    name, or after the email went out, goes through ``_change_recipient``.
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
        return await _change_recipient(
            message,
            task_state,
            org_id=org_id,
            conversation_id=conversation_id,
            client=client,
            settings=settings,
            user_id=user_id,
        )
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
