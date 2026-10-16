"""Approved write argument sealing (Release 2).

Fingerprints bind invoke actions to type-preserving argument constraints. They are
not a loose target-id hash: amounts, status, permissions, and message bodies
participate when the action profile requires them.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from app.services.canvas_write_gate import EXTERNAL_WRITE_STEP_TYPES, _iter_definition_steps
from app.services.catalog_write_authority import invoke_action_requires_write_approval
from app.services.tool_service import STEP_TYPE_TO_ACTION

# Identity / routing fields (case preserved except normalized email keys).
_TARGET_ARG_KEYS = frozenset(
    {
        "to",
        "email",
        "channel",
        "channel_id",
        "recipient",
        "recipients",
        "record_id",
        "id",
        "entity_id",
        "contact_id",
        "deal_id",
        "ticket_id",
        "list_id",
        "account_id",
        "company_id",
        "phone",
        "user_id",
    }
)

# Write-effect fields sealed when present on the payload.
_EFFECT_ARG_KEYS = frozenset(
    {
        "amount",
        "value",
        "price",
        "total",
        "quantity",
        "status",
        "stage",
        "pipeline",
        "permissions",
        "permission",
        "role",
        "roles",
        "scope",
        "subject",
        "body",
        "text",
        "html",
        "message",
        "content",
        "description",
        "title",
        "name",
        "properties",
        "fields",
        "payload",
        "data",
    }
)

_EMAIL_KEYS = frozenset({"email", "to", "recipient", "recipients"})

# Action-specific required keys; missing any → fail-closed (no runtime match).
_DEFAULT_REQUIRED_ANY = frozenset({"record_id", "id", "entity_id", "email", "to", "channel_id", "channel"})


def _constraints_satisfied(invoke_action: str, sealed: dict[str, Any]) -> bool:
    action = str(invoke_action or "").strip()
    if action in {"slack.messages.send", "slack.chat.postMessage"}:
        has_channel = "channel_id" in sealed or "channel" in sealed
        has_body = any(k in sealed for k in ("text", "message", "content", "body"))
        return has_channel and has_body
    if action == "gmail.messages.send":
        return "email" in sealed or "to" in sealed
    if any(action.endswith(suffix) for suffix in (".update", ".create", ".delete")):
        return bool(_DEFAULT_REQUIRED_ANY & set(sealed.keys()))
    return True


def _action_profile_keys(invoke_action: str) -> frozenset[str]:
    action = str(invoke_action or "").strip()
    keys = set(_TARGET_ARG_KEYS) | set(_EFFECT_ARG_KEYS)
    return frozenset(keys)


def _normalize_scalar(key: str, val: Any) -> Any:
    if isinstance(val, bool):
        return val
    if isinstance(val, int) and not isinstance(val, bool):
        return val
    if isinstance(val, float):
        return val
    if val is None:
        return None
    text = str(val).strip()
    if not text:
        return None
    if key in _EMAIL_KEYS or key.endswith("_email"):
        return text.lower()
    return text


def _normalize_value(key: str, val: Any) -> Any:
    if isinstance(val, dict):
        out: dict[str, Any] = {}
        for sub_key in sorted(val.keys()):
            normalized = _normalize_value(str(sub_key), val[sub_key])
            if normalized is not None and normalized != "" and normalized != [] and normalized != {}:
                out[str(sub_key)] = normalized
        return out or None
    if isinstance(val, list):
        items = [_normalize_value(key, item) for item in val]
        items = [item for item in items if item is not None and item != ""]
        if not items:
            return None
        if all(isinstance(item, (str, int, float, bool)) for item in items):
            return sorted(items, key=lambda x: json.dumps(x, sort_keys=True, default=str))
        return items
    return _normalize_scalar(key, val)


def _sealed_arguments(invoke_action: str, payload: dict[str, Any] | None) -> dict[str, Any] | None:
    data = payload if isinstance(payload, dict) else {}
    keys = _action_profile_keys(invoke_action)
    out: dict[str, Any] = {}
    for key in sorted(keys):
        if key not in data:
            continue
        val = data[key]
        if val in (None, "", [], {}):
            continue
        normalized = _normalize_value(key, val)
        if normalized is not None and normalized != "" and normalized != [] and normalized != {}:
            out[key] = normalized

    if not _constraints_satisfied(invoke_action, out):
        return None
    return out


def write_target_fingerprint(*, invoke_action: str, payload: dict[str, Any] | None) -> str | None:
    sealed = _sealed_arguments(invoke_action, payload)
    if sealed is None:
        return None
    body = {
        "invoke_action": str(invoke_action or "").strip(),
        "arguments": sealed,
    }
    raw = json.dumps(body, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def allowed_write_targets_from_definition(definition: dict[str, Any] | None) -> list[dict[str, str]]:
    """Target fingerprints sealed from the reviewed workflow definition."""
    out: list[dict[str, str]] = []
    for step in _iter_definition_steps(definition):
        stype = str(step.get("type") or "").strip()
        cfg = step.get("config") if isinstance(step.get("config"), dict) else {}
        action: str | None = None
        if stype in EXTERNAL_WRITE_STEP_TYPES:
            action = STEP_TYPE_TO_ACTION.get(stype)
        elif stype == "invoke_tool":
            action = str(cfg.get("action") or cfg.get("tool_action") or "").strip() or None
        if not action or not invoke_action_requires_write_approval(action):
            continue
        fp = write_target_fingerprint(invoke_action=action, payload=cfg)
        if fp is None:
            out.append({"invoke_action": action, "fingerprint": "__UNSEALED__"})
            continue
        out.append({"invoke_action": action, "fingerprint": fp})
    return sorted(out, key=lambda x: (x["invoke_action"], x["fingerprint"]))


def invoke_target_allowed(
    *,
    invoke_action: str,
    params: dict[str, Any] | None,
    allowed_targets: list[dict[str, str]] | None,
) -> bool:
    if not allowed_targets:
        return False
    scoped = [row for row in allowed_targets if row.get("invoke_action") == invoke_action]
    if not scoped:
        return False
    if any(row.get("fingerprint") == "__UNSEALED__" for row in scoped):
        return False
    fp = write_target_fingerprint(invoke_action=invoke_action, payload=params)
    if fp is None:
        return False
    return any(row.get("fingerprint") == fp for row in scoped)
