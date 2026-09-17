"""Phase G — operator-act context for vague prompts and connector reachability.

The chat model must interpret underspecified user text without waiting for a
human restatement. This module emits a compact, JSON-computable block plus
plain-language rules: connected systems are reachable for READ; writes stay
confirm-gated. Silent writes are never authorized here.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from app.connectors.action_catalog.registry import get_vendor_spec
from app.connectors.connector_availability_service import WRITE_ACTION_HINTS

_VAGUE_RE = re.compile(
    r"^(ok|okay|go|please|thanks|help|fix(?:\s+it)?|handle(?:\s+this)?|"
    r"do(?:\s+it)?|do something|make it (?:better|work)|what now|next|"
    r"continue|keep going|resume|pick up)\.?$",
    re.I,
)
_WRITE_RE = re.compile(
    r"\b(create|send|update|delete|publish|post|write|schedule|enroll|"
    r"assign|close|notify|draft|email|message)\b",
    re.I,
)
_READ_RE = re.compile(
    r"\b(list|show|get|fetch|find|search|status|how many|pipeline|what|"
    r"who|which|summarize|open)\b",
    re.I,
)
_CONNECTOR_RE = re.compile(
    r"\b(apollo|hubspot|slack|salesforce|jira|github|notion|stripe|asana|"
    r"gmail|google|ga4|analytics|monday|pipedrive|zendesk|linear|"
    r"quickbooks|xero|plaid|gusto|outlook|teams)\b",
    re.I,
)

_MAX_ACTIONS_READ = 8
_MAX_ACTIONS_WRITE = 6
_MAX_LEDGER_SLOTS = 16
_MAX_SLOT_CHARS = 200
_CRM_VENDORS = frozenset({"hubspot", "salesforce", "pipedrive", "engagebay"})
_FINANCE_VENDORS = frozenset({"quickbooks", "xero", "stripe"})
_SUPPORT_VENDORS = frozenset({"zendesk", "freshdesk", "intercom"})


@dataclass(frozen=True)
class OperatorActContext:
    intent: str
    vague: bool
    connected: list[dict[str, Any]]
    ledger_slots: dict[str, str]
    reachable_actions: list[dict[str, Any]]
    payload: dict[str, Any]
    section: str


def classify_operator_intent(user_text: str) -> str:
    text = (user_text or "").strip()
    if not text:
        return "vague"
    if _VAGUE_RE.match(text) or (len(text) < 24 and not _CONNECTOR_RE.search(text) and not _WRITE_RE.search(text)):
        if _READ_RE.search(text):
            return "read"
        return "vague"
    write = bool(_WRITE_RE.search(text))
    read = bool(_READ_RE.search(text) or _CONNECTOR_RE.search(text))
    if write and read:
        return "mixed"
    if write:
        return "write"
    if read:
        return "read"
    if len(text.split()) <= 4:
        return "vague"
    return "mixed"


def compact_ledger_slots(task_state: dict[str, Any] | None) -> dict[str, str]:
    raw = (task_state or {}).get("parameter_ledger") if isinstance(task_state, dict) else None
    if not isinstance(raw, dict):
        return {}
    slots = raw.get("slots") if isinstance(raw.get("slots"), dict) else raw
    if not isinstance(slots, dict):
        return {}
    out: dict[str, str] = {}
    for key, value in list(slots.items())[:_MAX_LEDGER_SLOTS]:
        if isinstance(value, dict):
            text = str(value.get("value") or "").strip()
        else:
            text = str(value or "").strip()
        if text:
            out[str(key)[:40]] = text[:_MAX_SLOT_CHARS]
    return out


def _compact_actions(vendor: str, *, include_writes: bool) -> list[dict[str, Any]]:
    spec = get_vendor_spec(vendor)
    if spec is None:
        return []
    rows: list[dict[str, Any]] = []
    for action in list(spec.v1)[:_MAX_ACTIONS_READ]:
        rows.append(_action_row(action, write=False))
    if include_writes:
        for action in list(spec.v2)[:_MAX_ACTIONS_WRITE]:
            rows.append(_action_row(action, write=True))
    return rows


def _action_row(action: Any, *, write: bool) -> dict[str, Any]:
    kind = str(getattr(action, "kind", "write" if write else "read") or "read")
    action_id = str(getattr(action, "id", "") or "")
    write_hint = write or kind != "read" or any(h in action_id for h in WRITE_ACTION_HINTS)
    return {
        "id": action_id,
        "kind": "write" if write_hint else "read",
        "name": str(getattr(action, "name", "") or action_id),
        "desc": str(getattr(action, "description", "") or "")[:160],
        "confirm": bool(write_hint or getattr(action, "requires_approval", False)),
    }


def build_operator_act_context(
    *,
    user_text: str,
    connected_integrations: list[str] | None,
    task_state: dict[str, Any] | None = None,
    interrupt: dict[str, Any] | None = None,
) -> OperatorActContext:
    connected = sorted({str(c).strip().lower() for c in (connected_integrations or []) if str(c).strip()})
    intent = classify_operator_intent(user_text)
    vague = intent == "vague"
    ledger_slots = compact_ledger_slots(task_state)
    include_writes = intent in {"write", "mixed", "vague"}
    reachable: list[dict[str, Any]] = []
    connected_rows: list[dict[str, Any]] = []
    for vendor in connected[:12]:
        connected_rows.append(
            {
                "vendor": vendor,
                "read": True,
                "write_gated": True,
            }
        )
        reachable.extend(_compact_actions(vendor, include_writes=include_writes))

    extra = interrupt.get("extra") if isinstance(interrupt, dict) else None
    sole_domains = {
        "crm": sorted(_CRM_VENDORS.intersection(connected)),
        "finance": sorted(_FINANCE_VENDORS.intersection(connected)),
        "support": sorted(_SUPPORT_VENDORS.intersection(connected)),
    }
    payload: dict[str, Any] = {
        "intent": intent,
        "vague": vague,
        "act_on_behalf_of_user": True,
        "build_context_without_human": True,
        "connected": connected_rows,
        "ledger_slots": ledger_slots,
        "reachable_actions": reachable[:40],
        "policy": {
            "silent_writes": False,
            "writes_require_explicit_confirm": True,
            "prefer_connected_read_when_vague": True,
            "disconnected_is_unreachable": True,
            "do_not_ask_unconnected_vendors": True,
        },
        "sole_connected_domains": {k: v for k, v in sole_domains.items() if v},
    }
    if isinstance(extra, dict) and extra:
        payload["interrupt"] = extra

    connected_line = (
        ", ".join(f"{row['vendor']} (read + write-gated)" for row in connected_rows)
        if connected_rows
        else "(none this turn — do not invent connector results)"
    )
    vague_rule = (
        "The user text is underspecified. Infer the goal from ledger_slots, history, "
        "and connected systems. Run a connected READ first when that would fill the gap. "
        "Do not ask the user to restate what chat can compute from this block."
        if vague
        else "Use reachable_actions ids as the executable catalog for this turn."
    )
    section = "\n".join(
        [
            "## Operator Act Context",
            "You act on behalf of the user. Interpret vague or thin prompts using this "
            "block — it is machine-readable JSON plus policy. Connectors listed here are "
            "reachable for READ this turn. Writes are reachable only after explicit user "
            "confirm; never execute a silent write.",
            f"Connected systems: {connected_line}",
            "If a domain has exactly one connected vendor (for example CRM=hubspot), "
            "use that vendor for READ. Do not ask which CRM, finance, or support system "
            "to use when the alternative is not connected this turn.",
            vague_rule,
            "<operator_act_json>",
            json.dumps(payload, separators=(",", ":"), default=str)[:6000],
            "</operator_act_json>",
        ]
    )
    return OperatorActContext(
        intent=intent,
        vague=vague,
        connected=connected_rows,
        ledger_slots=ledger_slots,
        reachable_actions=reachable,
        payload=payload,
        section=section,
    )
