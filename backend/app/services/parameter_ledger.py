"""Conversation-scoped parameter ledger (Module B Phase 1).

Single write/read authority for slots mentioned across turns. Surfaces must
call these APIs — not ad-hoc clarified_params Slack keys or per-connector
awaiting_params staging.

Pattern mirrors catalog_write_authority / execution_outcome: one module,
every surface calls in.
"""
from __future__ import annotations

import re
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from app.core.logging import get_logger
from app.services.chat_connector_models import ConnectorActionPlan

logger = get_logger(__name__)

EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w.-]+\.\w+\b")
SLACK_CHANNEL_RE = re.compile(
    r"(#[\w-]+)"
    r"|(?:\bin|to)\s+(?:the\s+)?([a-z0-9_-]+)\s+channel\b"
    r"|(?:\bchannel\s+)([a-z0-9_-]+)\b",
    re.I,
)
QUOTED_RE = re.compile(r"[\"']([^\"']{1,500})[\"']")
PROJECT_KEY_RE = re.compile(r"\bproject\s+([A-Z][A-Z0-9_-]{1,15})\b", re.I)
# Free-text schema keys filled from a follow-up turn when still missing.
FREE_TEXT_ARG_KEYS = frozenset(
    {
        "message",
        "text",
        "body",
        "description",
        "content",
        "note",
        "html_body",
        "comment",
        "subject",
        "summary",
        "title",
        "name",
    }
)

# Semantic aliases — schema-driven binding, not vendor-driven.
SLOT_ALIASES: dict[str, tuple[str, ...]] = {
    "to": ("to", "recipient", "email", "contact_email"),
    "email": ("email", "to", "recipient", "contact_email"),
    "channel": ("channel", "channel_id", "slack_channel"),
    "subject": ("subject",),
    "body": ("body", "message", "text", "html_body", "comment", "description"),
    "message": ("message", "text", "body"),
    "text": ("text", "message", "body"),
    "summary": ("summary", "title", "name"),
    "title": ("title", "summary", "name"),
    "name": ("name", "title", "summary", "list_name", "item_name"),
    "project_key": ("project_key", "project", "project_id"),
    "project": ("project", "project_key", "project_id"),
    "quoted": ("quoted",),
}


@dataclass
class SlotValue:
    value: str
    source: str = "user_message"
    turn_index: int | None = None
    confidence: str = "high"

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "value": self.value,
            "source": self.source,
            "confidence": self.confidence,
        }
        if self.turn_index is not None:
            payload["turn_index"] = self.turn_index
        return payload

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> SlotValue | None:
        if not isinstance(raw, dict):
            return None
        value = str(raw.get("value") or "").strip()
        if not value:
            return None
        turn = raw.get("turn_index")
        return cls(
            value=value,
            source=str(raw.get("source") or "user_message"),
            turn_index=int(turn) if turn is not None else None,
            confidence=str(raw.get("confidence") or "high"),
        )


@dataclass
class ParameterLedger:
    slots: dict[str, SlotValue] = field(default_factory=dict)
    pending_missing: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "slots": {key: slot.to_dict() for key, slot in self.slots.items()},
            "pending_missing": list(self.pending_missing),
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> ParameterLedger:
        if not isinstance(raw, dict):
            return cls()
        slots: dict[str, SlotValue] = {}
        for key, value in (raw.get("slots") or {}).items():
            slot = SlotValue.from_dict(value if isinstance(value, dict) else None)
            if slot:
                slots[str(key)] = slot
        pending = [
            str(item)
            for item in (raw.get("pending_missing") or [])
            if str(item).strip()
        ]
        return cls(slots=slots, pending_missing=pending)

    def get(self, key: str) -> str | None:
        slot = self.slots.get(key)
        if slot and slot.value:
            return slot.value
        for alias in SLOT_ALIASES.get(key, ()):
            alt = self.slots.get(alias)
            if alt and alt.value:
                return alt.value
        return None

    def upsert(
        self,
        key: str,
        value: str,
        *,
        source: str = "user_message",
        turn_index: int | None = None,
        confidence: str = "high",
    ) -> None:
        cleaned = str(value or "").strip()
        if not cleaned or not key:
            return
        self.slots[key] = SlotValue(
            value=cleaned,
            source=source,
            turn_index=turn_index,
            confidence=confidence,
        )


def empty_ledger() -> ParameterLedger:
    return ParameterLedger()


def get_ledger(task_state: dict[str, Any] | None) -> ParameterLedger:
    """Load ledger from task_state, bridging legacy clarified_params Slack keys."""
    state = task_state if isinstance(task_state, dict) else {}
    ledger = ParameterLedger.from_dict(
        state.get("parameter_ledger") if isinstance(state.get("parameter_ledger"), dict) else None
    )
    clarified = state.get("clarified_params") if isinstance(state.get("clarified_params"), dict) else {}
    # One-release bridge: legacy Slack staging → ledger channel.
    legacy_channel = clarified.get("slack_channel")
    if legacy_channel and not ledger.get("channel"):
        ledger.upsert(
            "channel",
            str(legacy_channel).lstrip("#"),
            source="legacy_clarified_params",
            confidence="high",
        )
    for key in ("to", "email", "subject", "body", "project_key", "summary", "name"):
        legacy = clarified.get(key)
        if legacy and not ledger.get(key):
            ledger.upsert(str(key), str(legacy), source="legacy_clarified_params")
    return ledger


def ledger_patch(ledger: ParameterLedger) -> dict[str, Any]:
    return {"parameter_ledger": ledger.to_dict()}


def upsert_slots(
    ledger: ParameterLedger,
    slots: dict[str, str],
    *,
    source: str = "user_message",
    turn_index: int | None = None,
    confidence: str = "high",
) -> ParameterLedger:
    for key, value in slots.items():
        ledger.upsert(
            key,
            value,
            source=source,
            turn_index=turn_index,
            confidence=confidence,
        )
    return ledger


def ingest_message_slots(
    message: str,
    *,
    turn_index: int | None = None,
    ledger: ParameterLedger | None = None,
) -> ParameterLedger:
    """Write-on-mention heuristics — every slot mentioned is recorded immediately."""
    from app.services.chat_message_normalize import strip_assistant_scope_prefix

    text = strip_assistant_scope_prefix(message or "")
    result = ledger or ParameterLedger()
    if not text.strip():
        return result

    email = EMAIL_RE.search(text)
    if email:
        addr = email.group(0)
        result.upsert("to", addr, source="user_message", turn_index=turn_index)
        result.upsert("email", addr, source="user_message", turn_index=turn_index)

    channel = _extract_channel(text)
    if channel:
        result.upsert("channel", channel, source="user_message", turn_index=turn_index)

    project = PROJECT_KEY_RE.search(text)
    if project:
        result.upsert(
            "project_key",
            project.group(1).upper(),
            source="user_message",
            turn_index=turn_index,
        )

    quoted = QUOTED_RE.findall(text)
    if quoted:
        # Keep latest quote as a generic binding target until schema bind.
        result.upsert(
            "quoted",
            quoted[-1].strip(),
            source="user_message",
            turn_index=turn_index,
        )
        if len(quoted) >= 1 and not result.get("summary"):
            # Common: first quote is title/subject for create/send intents.
            if re.search(r"\b(issue|ticket|task|subject|titled|called|named)\b", text, re.I):
                result.upsert(
                    "summary",
                    quoted[0].strip(),
                    source="user_message",
                    turn_index=turn_index,
                )
                result.upsert(
                    "title",
                    quoted[0].strip(),
                    source="user_message",
                    turn_index=turn_index,
                )
            if re.search(r"\bsubject\b", text, re.I):
                result.upsert(
                    "subject",
                    quoted[0].strip(),
                    source="user_message",
                    turn_index=turn_index,
                )

    # "subject X, body Y" / "subject is X body is Y" unquoted forms.
    subj_body = re.search(
        r"\bsubject\s*(?:is|=|:)?\s*(.+?)\s*[,—-]?\s*body\s*(?:is|=|:)?\s*(.+)$",
        text,
        re.I,
    )
    if subj_body:
        result.upsert(
            "subject",
            subj_body.group(1).strip(" .\"'"),
            source="user_message",
            turn_index=turn_index,
        )
        result.upsert(
            "body",
            subj_body.group(2).strip(" .\"'"),
            source="user_message",
            turn_index=turn_index,
        )
    else:
        subj_only = re.search(r"\bsubject\s*(?:is|=|:)\s*(.+)$", text, re.I)
        if subj_only and not result.get("subject"):
            result.upsert(
                "subject",
                subj_only.group(1).strip(" .\"'")[:300],
                source="user_message",
                turn_index=turn_index,
            )

    # "title is X" / "name is X" unquoted forms (Pipedrive/ClickUp/Notion/GitHub).
    title_only = re.search(
        r"\b(?:title|name)\s*(?:is|=|:)\s*(.+?)(?:\s+priority\b|$)",
        text,
        re.I,
    )
    if title_only:
        titled = title_only.group(1).strip(" .\"'")[:300]
        if titled and not result.get("title"):
            result.upsert("title", titled, source="user_message", turn_index=turn_index)
        if titled and not result.get("name"):
            result.upsert("name", titled, source="user_message", turn_index=turn_index)
        if titled and not result.get("summary"):
            result.upsert("summary", titled, source="user_message", turn_index=turn_index)

    return result


def _extract_channel(text: str) -> str | None:
    match = SLACK_CHANNEL_RE.search(text)
    if not match:
        if re.search(r"\b(?:to|in)\s+slack\b", text, re.I):
            return "general"
        return None
    if match.group(1):
        return match.group(1).lstrip("#")
    if match.group(2):
        return match.group(2)
    if match.group(3):
        return match.group(3)
    return None


def bind_args_from_ledger(
    invoke_action: str,
    args: dict[str, Any] | None,
    ledger: ParameterLedger,
) -> dict[str, Any]:
    """Fill missing plan args from ledger using the action's workflow schema."""
    from app.connectors.action_catalog.action_workflow_schema import get_workflow_schema

    filled = dict(args or {})
    schema = get_workflow_schema(invoke_action)
    fields = ()
    if schema:
        fields = (*schema.required_fields, *schema.optional_fields)

    if fields:
        for field_spec in fields:
            if _arg_present_for_keys(filled, field_spec.arg_keys):
                continue
            value = _ledger_value_for_keys(ledger, field_spec.arg_keys)
            if value is None and "quoted" in field_spec.arg_keys:
                value = ledger.get("quoted")
            # Free-text fields can consume the generic quoted slot.
            if value is None and any(k in FREE_TEXT_ARG_KEYS for k in field_spec.arg_keys):
                value = ledger.get("quoted")
            if value is None:
                # Label-based alias: "recipient" → to/email
                label_key = field_spec.label.lower().replace(" ", "_")
                value = ledger.get(label_key) or _ledger_value_for_keys(
                    ledger, SLOT_ALIASES.get(label_key, ())
                )
            if value is not None:
                filled[field_spec.arg_keys[0]] = value
                # Slack dual keys
                if "message" in field_spec.arg_keys and "text" in field_spec.arg_keys:
                    filled.setdefault("text", value)
                    filled.setdefault("message", value)
    else:
        # No schema — bind common aliases into empty args.
        for key in ("to", "email", "channel", "subject", "body", "summary", "project_key", "name"):
            if not str(filled.get(key) or "").strip():
                value = ledger.get(key)
                if value:
                    filled[key] = value

    return filled


def _arg_present_for_keys(args: dict[str, Any], keys: tuple[str, ...]) -> bool:
    return any(str(args.get(key) or "").strip() for key in keys)


def _ledger_value_for_keys(ledger: ParameterLedger, keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = ledger.get(key)
        if value:
            return value
        for alias in SLOT_ALIASES.get(key, ()):
            value = ledger.get(alias)
            if value:
                return value
    return None


def is_awaiting_params(task_state: dict[str, Any] | None) -> bool:
    pending = (task_state or {}).get("pending_task")
    if not isinstance(pending, dict):
        return False
    return (
        str(pending.get("type") or "") == "connector_action"
        and str(pending.get("status") or "") == "awaiting_params"
    )


def missing_required_fields(
    invoke_action: str,
    args: dict[str, Any] | None,
    ledger: ParameterLedger,
) -> list[str]:
    """Live ledger-aware missing required labels — call every turn, never cache."""
    from app.connectors.action_catalog.action_workflow_schema import get_workflow_schema
    from app.services.action_workflow_validation import _field_present

    schema = get_workflow_schema(invoke_action)
    if not schema:
        return []
    filled = bind_args_from_ledger(invoke_action, dict(args or {}), ledger)
    missing: list[str] = []
    for field_spec in schema.required_fields:
        if not _field_present(filled, field_spec):
            missing.append(field_spec.label)
    return missing


def slot_confidence(ledger: ParameterLedger, key: str) -> str:
    """Return high|medium|low for a ledger slot (default high when present)."""
    slot = ledger.slots.get(key)
    if slot is None:
        for alias in SLOT_ALIASES.get(key, ()):
            slot = ledger.slots.get(alias)
            if slot:
                break
    if slot is None or not slot.value:
        return "low"
    conf = (slot.confidence or "high").lower()
    if conf in {"high", "medium", "low"}:
        return conf
    return "high"


def stage_awaiting_params(
    plan: ConnectorActionPlan,
    missing_fields: tuple[str, ...] | list[str] | None = None,
    *,
    ledger: ParameterLedger | None = None,
) -> dict[str, Any]:
    """Build task_state patch: pending_task awaiting_params + ledger pending_missing.

    Always rebinds args from the live ledger before staging so pending_task.args
    advances whenever the ledger already has values.
    """
    active = ledger or ParameterLedger()
    args = bind_args_from_ledger(plan.invoke_action, dict(plan.args or {}), active)
    # Persist known args into ledger slots for resume.
    for key, value in args.items():
        if isinstance(value, str) and value.strip():
            active.upsert(key, value, source="staged_plan")
    # Recompute missing from live ledger+args — never trust a stale caller list alone.
    live_missing = missing_required_fields(plan.invoke_action, args, active)
    if missing_fields is not None and not live_missing:
        # Caller said something was missing but ledger filled it — trust ledger.
        active.pending_missing = []
    elif live_missing:
        active.pending_missing = live_missing
    else:
        active.pending_missing = [str(item) for item in (missing_fields or []) if str(item).strip()]

    params: dict[str, Any] = {
        "tool_name": plan.tool_name,
        "invoke_action": plan.invoke_action,
        "integration": plan.integration,
        "kind": plan.kind,
        "label": plan.label,
        "destructive": plan.destructive,
        "args": args,
        "inferred_fields": list(plan.inferred_fields or ()),
        "inference_sources": dict(plan.inference_sources or {}),
    }
    # Flatten common keys for backward-compatible pending readers.
    for key in ("channel", "to", "email", "subject", "body", "message", "text"):
        if args.get(key):
            params[key] = args[key]

    return {
        **ledger_patch(active),
        "pending_task": {
            "type": "connector_action",
            "status": "awaiting_params",
            "params": params,
        },
        "clarified_params": _clarified_bridge_from_ledger(active, plan),
    }


def _clarified_bridge_from_ledger(
    ledger: ParameterLedger,
    plan: ConnectorActionPlan,
) -> dict[str, str]:
    """Keep clarified_params in sync for older readers during transition."""
    out: dict[str, str] = {}
    channel = ledger.get("channel")
    if channel:
        out["slack_channel"] = channel
        out["channel"] = channel
    for key in ("to", "email", "subject", "body", "project_key", "summary", "name"):
        value = ledger.get(key)
        if value:
            out[key] = value
    if plan.integration == "slack":
        out["intent"] = "slack_send"
    elif plan.integration in {"gmail", "microsoft365"}:
        out["intent"] = "email_send"
    return out


def resume_awaiting_params(
    message: str,
    task_state: dict[str, Any],
) -> tuple[ConnectorActionPlan | None, ParameterLedger, dict[str, Any]]:
    """Resume a staged connector_action by filling missing free-text / typed slots.

    Returns (plan_or_none, updated_ledger, task_state_patch).
    """
    from app.connectors.action_catalog.action_workflow_schema import get_workflow_schema
    from app.services.chat_message_normalize import strip_assistant_scope_prefix

    if not is_awaiting_params(task_state):
        return None, get_ledger(task_state), {}

    pending = task_state.get("pending_task") or {}
    params = dict(pending.get("params") or {})
    invoke_action = str(params.get("invoke_action") or "")
    if not invoke_action:
        return None, get_ledger(task_state), {}

    ledger = ingest_message_slots(
        message,
        turn_index=_next_turn_index(task_state),
        ledger=get_ledger(task_state),
    )
    args = bind_args_from_ledger(invoke_action, dict(params.get("args") or {}), ledger)

    # Follow-up body: fill first missing free-text required field from the message.
    schema = get_workflow_schema(invoke_action)
    followup = _followup_fill_text(message)
    if followup and schema:
        for field_spec in schema.required_fields:
            if _arg_present_for_keys(args, field_spec.arg_keys):
                continue
            primary = field_spec.arg_keys[0]
            if primary in FREE_TEXT_ARG_KEYS or any(
                k in FREE_TEXT_ARG_KEYS for k in field_spec.arg_keys
            ):
                args[primary] = followup
                if "message" in field_spec.arg_keys:
                    args.setdefault("message", followup)
                if "text" in field_spec.arg_keys:
                    args.setdefault("text", followup)
                if "body" in field_spec.arg_keys:
                    args.setdefault("body", followup)
                ledger.upsert(primary, followup, source="awaiting_params_resume")
                break
        else:
            # Optional free-text still missing (e.g. description).
            for field_spec in schema.optional_fields:
                if _arg_present_for_keys(args, field_spec.arg_keys):
                    continue
                primary = field_spec.arg_keys[0]
                if primary in FREE_TEXT_ARG_KEYS:
                    args[primary] = followup
                    ledger.upsert(primary, followup, source="awaiting_params_resume")
                    break
    elif followup and not schema:
        # Fallback for actions without schema: treat follow-up as body/message.
        if not str(args.get("message") or args.get("body") or args.get("text") or "").strip():
            args["message"] = followup
            args.setdefault("text", followup)
            args.setdefault("body", followup)
            ledger.upsert("message", followup, source="awaiting_params_resume")

    # Email-only follow-up (user replied with just an address).
    email = EMAIL_RE.search(strip_assistant_scope_prefix(message or ""))
    if email:
        addr = email.group(0)
        if not str(args.get("to") or "").strip():
            args["to"] = addr
        ledger.upsert("to", addr, source="awaiting_params_resume")
        ledger.upsert("email", addr, source="awaiting_params_resume")

    plan = ConnectorActionPlan(
        tool_name=str(params.get("tool_name") or ""),
        invoke_action=invoke_action,
        integration=str(params.get("integration") or ""),
        kind=str(params.get("kind") or "write"),
        label=str(params.get("label") or ""),
        args=args,
        requires_approval=bool(params.get("requires_approval")),
        approval_reason=params.get("approval_reason"),
        destructive=bool(params.get("destructive")),
        inferred_fields=tuple(str(x) for x in (params.get("inferred_fields") or [])),
        inference_sources=dict(params.get("inference_sources") or {}),
    )
    # Advance pending_task.args from live ledger (root cause of test-1 stall).
    advanced = stage_awaiting_params(plan, ledger=ledger)
    still_missing = list(
        (advanced.get("parameter_ledger") or {}).get("pending_missing") or []
    )
    if not still_missing:
        # All required fields present — keep pending for confirm/execute path,
        # but clear awaiting_params trap by leaving status awaiting_params only
        # when still incomplete; when complete, status stays awaiting_params
        # until process_turn promotes to awaiting_confirm (write gate).
        ledger.pending_missing = []
        advanced["parameter_ledger"] = ledger.to_dict()
        # Mark complete so callers can promote.
        pending_params = dict((advanced.get("pending_task") or {}).get("params") or {})
        pending_params["args"] = dict(plan.args or {})
        for key in ("channel", "to", "email", "subject", "body", "message", "text"):
            if plan.args.get(key):
                pending_params[key] = plan.args[key]
        advanced["pending_task"] = {
            "type": "connector_action",
            "status": "awaiting_params",
            "params": pending_params,
            "resume_complete": True,
        }
    patch = {
        **advanced,
        "clarified_params": _clarified_bridge_from_ledger(ledger, plan),
        "recent_user_messages": [strip_assistant_scope_prefix(message or "")],
    }
    return plan, ledger, patch


def _followup_fill_text(message: str) -> str | None:
    from app.services.chat_message_normalize import strip_assistant_scope_prefix
    from app.services.chat_connector_models import INTEGRATION_ALIASES

    text = strip_assistant_scope_prefix(message or "")
    if not text:
        return None
    # Pure email reply — not free-text body.
    if EMAIL_RE.fullmatch(text.strip()):
        return None
    cleaned = re.sub(
        r"^(?:sure|ok|okay|yes|yep|yeah|please)[,!.]?\s+",
        "",
        text,
        flags=re.I,
    ).strip()
    cleaned = re.sub(
        r"^(?:say|post|send|write)\s+",
        "",
        cleaned,
        flags=re.I,
    ).strip(" \"'")
    if not cleaned or len(cleaned) < 2:
        return None
    # Avoid treating a new connector ask as a body.
    action_verb = re.compile(
        r"\b(create|update|post|send|write|delete|search|find|list)\b",
        re.I,
    )
    connector_mention = re.compile(
        r"\b("
        + "|".join(
            re.escape(alias)
            for aliases in INTEGRATION_ALIASES.values()
            for alias in aliases
        )
        + r")\b",
        re.I,
    )
    if connector_mention.search(cleaned) and action_verb.search(cleaned):
        return None
    return cleaned[:3000]


def _next_turn_index(task_state: dict[str, Any] | None) -> int:
    recent = (task_state or {}).get("recent_user_messages") or []
    return len(recent) + 1 if isinstance(recent, list) else 1


def apply_ledger_to_plan(
    plan: ConnectorActionPlan,
    task_state: dict[str, Any] | None,
) -> ConnectorActionPlan:
    """Bind ledger slots into a freshly matched plan (unprompted cross-turn case)."""
    from dataclasses import replace

    ledger = get_ledger(task_state)
    if not ledger.slots:
        return plan
    args = bind_args_from_ledger(plan.invoke_action, dict(plan.args or {}), ledger)
    if args == (plan.args or {}):
        return plan
    return replace(plan, args=args)


def merge_ledger_into_task_state(
    task_state: dict[str, Any] | None,
    ledger: ParameterLedger,
) -> dict[str, Any]:
    state = deepcopy(task_state) if isinstance(task_state, dict) else {}
    state["parameter_ledger"] = ledger.to_dict()
    return state
