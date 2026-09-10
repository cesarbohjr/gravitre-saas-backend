"""Refuse 'I don't have that action' when the conversation already invoked it.

Retrieval poisoning can make the model claim a connected vendor action is
missing immediately after that action actually ran. Prompt text is not enough:
this gate rewrites that claim from structured recent invocation history.
"""
from __future__ import annotations

import re
from typing import Any

from app.services.connected_vendor_knowledge_filter import (
    catalog_vendors_mentioned,
    known_catalog_vendors,
)
from app.services.factual_claim_honesty import _tool_name, _tool_payload

_ACTION_MISSING_CLAIM = re.compile(
    r"(?:"
    r"i (?:don't|do not|can't|cannot) have (?:a |an |the )?.{0,120}action"
    r"|"
    r"(?:needed|required) .{0,80}action.{0,120}(?:aren't|are not|isn't|is not) provided"
    r"|"
    r"action with the required fields (?:loaded|available)"
    r"|"
    r"(?:don't|do not) have .{0,80}(?:list-creation|list creation) action"
    r"|"
    r"i don't have a .{0,80}(?:list-creation|list creation)"
    r")",
    re.I,
)

_MAX_RECENT = 8


def answer_claims_action_missing(answer: str) -> bool:
    text = (answer or "").strip()
    if not text:
        return False
    return bool(_ACTION_MISSING_CLAIM.search(text))


def _vendor_from_action(action: str) -> str:
    raw = str(action or "").strip().lower().replace("-", "_")
    if not raw:
        return ""
    known = known_catalog_vendors()
    if "." in raw:
        head = raw.split(".", 1)[0]
        return head if head in known else ""
    if "_" in raw:
        head = raw.split("_", 1)[0]
        return head if head in known else ""
    return raw if raw in known else ""


def _normalize_action_key(row: dict[str, Any]) -> str:
    known = known_catalog_vendors()
    for key in (
        "invoke_action",
        "invokeAction",
        "action",
        "type",
        "tool",
        "toolName",
        "tool_name",
        "name",
    ):
        value = str(row.get(key) or "").strip()
        if not value:
            continue
        lowered = value.lower().replace("-", "_")
        if "." in lowered and lowered.split(".", 1)[0] in known:
            return lowered
        if "_" in lowered:
            head = lowered.split("_", 1)[0]
            if head in known:
                parts = lowered.split("_")
                if len(parts) >= 3:
                    return f"{parts[0]}.{'.'.join(parts[1:])}"
                return f"{parts[0]}.{parts[1]}" if len(parts) == 2 else lowered
        if lowered in known:
            return lowered
    return ""


def _row_error_code(row: dict[str, Any]) -> str:
    for key in ("error_code", "errorCode"):
        value = str(row.get(key) or "").strip()
        if value:
            return value[:80]
    payload = _tool_payload(row)
    for key in ("error_code", "errorCode"):
        value = str(payload.get(key) or "").strip()
        if value:
            return value[:80]
    output = row.get("output")
    if isinstance(output, dict):
        for key in ("error_code", "errorCode"):
            value = str(output.get(key) or "").strip()
            if value:
                return value[:80]
    return ""


def _dicts_from_task_state(task_state: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    pending = task_state.get("pending_task")
    if isinstance(pending, dict):
        params = pending.get("params") if isinstance(pending.get("params"), dict) else pending
        rows.append(params if isinstance(params, dict) else pending)
        result = pending.get("result")
        if isinstance(result, dict):
            rows.append(result)
    stored = task_state.get("recent_connector_invocations")
    if isinstance(stored, list):
        rows.extend([r for r in stored if isinstance(r, dict)])
    for key in ("approved_actions", "completed_steps"):
        block = task_state.get(key)
        if isinstance(block, list):
            rows.extend([r for r in block if isinstance(r, dict)])
    return rows


def extract_recent_connector_invocations(
    *,
    tool_results: list[dict[str, Any]] | None = None,
    react_result: Any | None = None,
    task_state: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    """Structured recent connector invokes for this turn + conversation state."""
    rows: list[dict[str, Any]] = []
    if tool_results:
        rows.extend([r for r in tool_results if isinstance(r, dict)])
    if react_result is not None:
        calls = getattr(react_result, "tool_calls", None)
        if isinstance(calls, list):
            rows.extend([c for c in calls if isinstance(c, dict)])
        as_dict = react_result.to_dict() if hasattr(react_result, "to_dict") else None
        if isinstance(as_dict, dict):
            for key in ("tool_calls", "toolCalls", "trace"):
                block = as_dict.get(key)
                if isinstance(block, list):
                    rows.extend([c for c in block if isinstance(c, dict)])
    if isinstance(task_state, dict):
        rows.extend(_dicts_from_task_state(task_state))

    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in rows:
        candidates = [row]
        payload = _tool_payload(row) if isinstance(row, dict) else {}
        if payload:
            candidates.append(payload)
        output = row.get("output") if isinstance(row, dict) else None
        if isinstance(output, dict):
            candidates.append(output)
        action = ""
        vendor = ""
        for candidate in candidates:
            action = _normalize_action_key(candidate)
            vendor = _vendor_from_action(action)
            if vendor:
                break
        if not vendor:
            name = _tool_name(row)
            vendor = _vendor_from_action(name)
            if vendor and not action:
                action = name.replace("_", ".", 1) if "_" in name else name
        if not vendor:
            continue
        key = f"{vendor}:{action}"
        if key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "vendor": vendor,
                "action": action,
                "error_code": _row_error_code(row) if isinstance(row, dict) else "",
            }
        )
        if len(out) >= _MAX_RECENT:
            break
    return out


def _display_vendor(vendor: str) -> str:
    if vendor == "hubspot":
        return "HubSpot"
    if vendor == "microsoft365":
        return "Microsoft 365"
    return vendor.replace("_", " ").title()


def _human_action(action: str) -> str:
    raw = (action or "").strip()
    if "." in raw:
        return raw.split(".", 1)[1].replace("_", " ").replace(".", " ")
    return raw.replace("_", " ")


def _rewrite_for_invocations(invocations: list[dict[str, str]]) -> str:
    first = invocations[0]
    vendor = _display_vendor(first["vendor"])
    action = _human_action(first["action"]) or "this action"
    failed = any(
        str(row.get("error_code") or "").lower()
        in {"validation_error", "tool_error", "connector_execution_failed"}
        for row in invocations
    )
    if failed:
        return (
            f"{vendor} {action} is available — it already ran in this conversation and "
            f"{vendor} rejected the parameters. A validation error is not a missing action. "
            f"I can retry with {vendor} defaults instead of searching another vendor's docs."
        )
    return (
        f"{vendor} {action} is available in this conversation — it was already invoked. "
        f"I should not claim that action is missing."
    )


def apply_action_availability_honesty_gate(
    answer: str,
    *,
    tool_results: list[dict[str, Any]] | None = None,
    react_result: Any | None = None,
    task_state: dict[str, Any] | None = None,
) -> str:
    """Rewrite 'I don't have that action' when recent history invoked it."""
    text = (answer or "").strip()
    if not text or not answer_claims_action_missing(text):
        return answer
    invoked = extract_recent_connector_invocations(
        tool_results=tool_results,
        react_result=react_result,
        task_state=task_state,
    )
    if not invoked:
        return answer
    denied_vendors = catalog_vendors_mentioned(text)
    matching = [
        row
        for row in invoked
        if not denied_vendors or row["vendor"] in denied_vendors
    ]
    if not matching:
        return answer
    return _rewrite_for_invocations(matching)


def invocations_state_patch(invocations: list[dict[str, str]]) -> dict[str, Any]:
    if not invocations:
        return {}
    return {"recent_connector_invocations": invocations[:_MAX_RECENT]}
