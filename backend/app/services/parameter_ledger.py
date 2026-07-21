"""Conversation-scoped parameter ledger (Module B Phase 1).

Single write/read authority for slots mentioned across turns. Surfaces must
call these APIs — not ad-hoc clarified_params Slack keys or per-connector
awaiting_params staging.

Pattern mirrors catalog_write_authority / execution_outcome: one module,
every surface calls in.
"""
from __future__ import annotations

import json
import re
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from app.core.logging import get_logger
from app.services.chat_connector_models import ConnectorActionPlan

logger = get_logger(__name__)

# Local-part must start at a non-dot boundary so we never match a suffix inside
# a dotted address (e.g. moduleb@x inside sarah.chen.moduleb@x).
EMAIL_RE = re.compile(r"(?<![\w.])([\w+-]+(?:\.[\w+-]+)*@[\w.-]+\.\w+)\b")
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

# Source trust for free-text write-protection. Higher wins on conflict.
# awaiting_params_resume is lowest — a whole-turn dump must never clobber an
# explicit user/schema extract, and side questions must not invent subjects.
_SLOT_SOURCE_RANK: dict[str, int] = {
    "awaiting_params_resume": 1,
    "staged_plan": 2,
    "legacy_clarified_params": 2,
    "schema_param_extractor": 3,
    "user_message": 4,
    "confidence_propose": 3,
}


def _source_rank(source: str | None) -> int:
    return _SLOT_SOURCE_RANK.get(str(source or "").strip(), 2)


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
    "file_id": ("file_id", "item_id", "page_id"),
    "file_name": ("file_name", "filename", "document_name"),
    "file_vendor": ("file_vendor", "vendor"),
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
        force: bool = False,
    ) -> None:
        cleaned = str(value or "").strip()
        if not cleaned or not key:
            return
        existing = self.slots.get(key)
        if (
            not force
            and existing
            and existing.value
            and existing.value != cleaned
            and key in FREE_TEXT_ARG_KEYS
        ):
            # Write-protect: refuse lower-trust overwrite of free-text slots.
            # Typed slots (to/email/channel) stay cue-gated by extractors.
            if _source_rank(source) < _source_rank(existing.source):
                logger.debug(
                    "parameter_ledger_write_protect key=%s refused source=%s kept=%s",
                    key,
                    source,
                    existing.source,
                )
                return
            if source == "awaiting_params_resume" and existing.source != "awaiting_params_resume":
                logger.debug(
                    "parameter_ledger_write_protect key=%s refused resume over %s",
                    key,
                    existing.source,
                )
                return
        self.slots[key] = SlotValue(
            value=cleaned,
            source=source,
            turn_index=turn_index,
            confidence=confidence,
        )


def empty_ledger() -> ParameterLedger:
    return ParameterLedger()


def extract_complete_emails(text: str) -> list[str]:
    """Return complete email addresses from text (no local-part suffix false positives)."""
    if not text:
        return []
    found = EMAIL_RE.findall(text)
    # findall returns group 1 when pattern has one capturing group.
    emails = [str(item) for item in found if str(item).strip()]
    # Drop any residual that is a strict suffix of another match.
    unique = list(dict.fromkeys(emails))
    return [
        email
        for email in unique
        if not any(email != other and other.endswith(email) for other in unique)
    ]


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

    # Mask emails so local-parts like subject.pollution@x never match \bsubject.
    text_for_freeform = EMAIL_RE.sub(" ", text)

    quoted = QUOTED_RE.findall(text_for_freeform)
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
            if re.search(r"\b(issue|ticket|task|subject|titled|called|named)\b", text_for_freeform, re.I):
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
            if re.search(r"\bsubject\b", text_for_freeform, re.I):
                result.upsert(
                    "subject",
                    quoted[0].strip(),
                    source="user_message",
                    turn_index=turn_index,
                )

    # "subject X, body Y" / "subject is X body is Y" unquoted forms.
    # Require a word-boundary subject cue that is not an email local-part
    # (emails already masked above). Prefer explicit is/=/: when present.
    subj_body = re.search(
        r"\bsubject\s*(?:is|=|:)?\s*(.+?)\s*[,—-]?\s*body\s*(?:is|=|:)?\s*(.+)$",
        text_for_freeform,
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
        subj_only = re.search(r"\bsubject\s*(?:is|=|:)\s*(.+)$", text_for_freeform, re.I)
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

    ref = resolve_file_reference(text, result)
    if ref and ref.get("file_id"):
        result.upsert("file_id", str(ref["file_id"]), source="user_message", turn_index=turn_index)
        if ref.get("name"):
            result.upsert("file_name", str(ref["name"]), source="user_message", turn_index=turn_index)
        if ref.get("vendor"):
            result.upsert("file_vendor", str(ref["vendor"]), source="user_message", turn_index=turn_index)
        if ref.get("web_link"):
            result.upsert("file_link", str(ref["web_link"]), source="user_message", turn_index=turn_index)

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
        from app.connectors.action_catalog.action_workflow_schema import iter_workflow_fields

        fields = tuple(iter_workflow_fields(schema))

    if fields:
        for field_spec in fields:
            present = _arg_present_for_keys(filled, field_spec.arg_keys)
            is_free = any(k in FREE_TEXT_ARG_KEYS for k in field_spec.arg_keys)
            value = _ledger_value_for_keys(ledger, field_spec.arg_keys)
            if value is None and "quoted" in field_spec.arg_keys:
                value = ledger.get("quoted")
            # Free-text fields can consume the generic quoted slot.
            if value is None and is_free:
                value = ledger.get("quoted")
            if value is None:
                # Label-based alias: "recipient" → to/email
                label_key = field_spec.label.lower().replace(" ", "_")
                value = ledger.get(label_key) or _ledger_value_for_keys(
                    ledger, SLOT_ALIASES.get(label_key, ())
                )
            if value is None:
                continue
            primary = field_spec.arg_keys[0]
            current = str(filled.get(primary) or "").strip()
            # Prefer higher-trust ledger free-text over stale pending_task.args
            # (subject pollution class: resume dump stuck in args while ledger repaired).
            if present and is_free and current and current != value:
                slot = None
                for k in field_spec.arg_keys:
                    slot = ledger.slots.get(k)
                    if slot and slot.value:
                        break
                # Explicit user/schema extracts repair resume pollution stuck in args.
                if slot and slot.source in {"user_message", "schema_param_extractor"}:
                    filled[primary] = value
                continue
            if present:
                continue
            filled[primary] = value
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

    filled = bind_connected_file_args(invoke_action, filled, ledger)
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


def _is_side_question_not_slot_answer(text: str) -> bool:
    """True when the turn is meta/status chatter, not an answer to a missing field.

    Structural guard for subject/body pollution: filler turns like
    \"what connectors are Connected?\" must not fill free-text slots.
    """
    t = (text or "").strip()
    if not t:
        return False
    lower = t.lower()
    # Explicit slot cues mean this IS an answer (even if phrased as a question).
    if re.search(
        r"\b(subject|body|message|channel|recipient|to)\s*(?:is|=|:)\s*\S",
        lower,
    ):
        return False
    if re.search(
        r"\b(subject|body)\s+[^?]{2,},?\s*body\b",
        lower,
    ):
        return False
    if re.search(r"\b(side note|by the way|btw|unrelated|quick note|quick side)\b", lower):
        return True
    if lower.endswith("?") or re.match(
        r"^(what|which|who|how|why|when|where|are|is|do|does|can|could)\b",
        lower,
    ):
        # Status / readiness questions are never subject/body answers.
        if re.search(
            r"\b(connector|connectors|connected|healthy|status|executable|verified)\b",
            lower,
        ):
            return True
        # Generic interrogatives without a slot cue — do not invent free-text.
        if not re.search(r"\b(subject|body|message|email|recipient|channel)\b", lower):
            return True
    return False


def _followup_fill_text(message: str) -> str | None:
    from app.services.chat_message_normalize import strip_assistant_scope_prefix
    from app.services.chat_connector_models import INTEGRATION_ALIASES

    text = strip_assistant_scope_prefix(message or "")
    if not text:
        return None
    # Pure email reply — not free-text body.
    if EMAIL_RE.fullmatch(text.strip()):
        return None
    if _is_side_question_not_slot_answer(text):
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


_FILE_ORDINAL_RE = re.compile(
    r"\b(?:the\s+)?(?:(\d+)(?:st|nd|rd|th)|first|second|third|fourth|fifth|last)\b(?:\s+(?:one|file|result|document|page))?",
    re.I,
)
_ORDINAL_WORDS = {
    "first": 1,
    "second": 2,
    "third": 3,
    "fourth": 4,
    "fifth": 5,
}


def ingest_connected_file_hits(
    task_state: dict[str, Any] | None,
    hits: list[dict[str, Any]],
    *,
    turn_index: int | None = None,
) -> dict[str, Any]:
    """Persist connected-file search hits in the parameter ledger for follow-up turns."""
    if not hits:
        return task_state if isinstance(task_state, dict) else {}
    ledger = get_ledger(task_state)
    refs: list[dict[str, Any]] = []
    for index, hit in enumerate(hits[:10], start=1):
        if not isinstance(hit, dict):
            continue
        file_id = str(hit.get("file_id") or hit.get("id") or "").strip()
        if not file_id:
            continue
        ref = {
            "index": index,
            "file_id": file_id,
            "name": str(hit.get("name") or "Untitled"),
            "vendor": str(hit.get("vendor") or ""),
            "web_link": hit.get("web_link"),
            "path": hit.get("path"),
        }
        refs.append(ref)
    if not refs:
        return task_state if isinstance(task_state, dict) else {}
    ledger.upsert("file_refs_json", json.dumps(refs), source="connected_files", turn_index=turn_index)
    primary = refs[0]
    ledger.upsert("file_id", primary["file_id"], source="connected_files", turn_index=turn_index)
    ledger.upsert("file_name", primary["name"], source="connected_files", turn_index=turn_index)
    if primary.get("vendor"):
        ledger.upsert("file_vendor", primary["vendor"], source="connected_files", turn_index=turn_index)
    if primary.get("web_link"):
        ledger.upsert("file_link", str(primary["web_link"]), source="connected_files", turn_index=turn_index)
    return merge_ledger_into_task_state(task_state, ledger)


def resolve_file_reference(message: str, ledger: ParameterLedger | None = None) -> dict[str, Any] | None:
    """Resolve ordinal follow-ups ('the second one') to a prior connected-file hit."""
    active = ledger or ParameterLedger()
    raw = active.get("file_refs_json")
    if not raw:
        return None
    try:
        refs = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(refs, list) or not refs:
        return None
    text = (message or "").strip().lower()
    if not text:
        return refs[0] if refs else None
    match = _FILE_ORDINAL_RE.search(text)
    if not match:
        if re.search(r"\b(that|this|same)\s+(?:file|document|page|one)\b", text):
            return refs[0]
        return None
    word = (match.group(0) or "").lower()
    if "last" in word:
        return refs[-1]
    numeric = match.group(1)
    if numeric:
        idx = int(numeric)
    else:
        idx = next((v for k, v in _ORDINAL_WORDS.items() if k in word), 1)
    if idx < 1 or idx > len(refs):
        return None
    return refs[idx - 1]


def bind_connected_file_args(
    invoke_action: str,
    args: dict[str, Any],
    ledger: ParameterLedger,
    message: str | None = None,
) -> dict[str, Any]:
    """Fill file_id/vendor from ledger when follow-up omits explicit ids."""
    action = str(invoke_action or "").lower()
    if "get_file" not in action and "files.content" not in action:
        return args
    bound = dict(args or {})
    if bound.get("file_id") or bound.get("fileId") or bound.get("page_id"):
        return bound
    ref = resolve_file_reference(message or "", ledger)
    if not ref:
        file_id = ledger.get("file_id")
        if file_id:
            bound["file_id"] = file_id
            vendor = ledger.get("file_vendor")
            if vendor and not bound.get("vendor"):
                bound["vendor"] = vendor
            return bound
        return bound
    bound["file_id"] = ref.get("file_id")
    if ref.get("vendor") and not bound.get("vendor"):
        bound["vendor"] = ref.get("vendor")
    return bound
