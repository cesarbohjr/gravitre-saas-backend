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

# Only dispatcher metadata is excluded. Every provider argument participates,
# including unknown extension fields; a growing allowlist silently loses binding.
_DISPATCH_KEYS = frozenset({"action", "tool_action", "approval_scope"})
_EMAIL_KEYS = frozenset({"email", "to", "recipient", "recipients", "cc", "bcc"})


def _normalize_value(key: str, value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _normalize_value(str(k), v) for k, v in value.items()}
    if isinstance(value, list):
        # Array order can change provider semantics (patch operations, attachments).
        return [_normalize_value(key, item) for item in value]
    if isinstance(value, str) and (key in _EMAIL_KEYS or key.endswith("_email")):
        return value.strip().lower()
    # Preserve body whitespace, empty values, nulls, case and scalar types.
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    raise ValueError("Approval arguments must be JSON values")


def _sealed_arguments(invoke_action: str, payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(payload, dict) or not payload:
        return None
    try:
        arguments = {key: _normalize_value(key, value) for key, value in payload.items()
                     if key not in _DISPATCH_KEYS}
        json.dumps(arguments, allow_nan=False)
    except (ValueError, TypeError):
        return None
    return arguments or None


def _reviewed_arguments(config: dict[str, Any]) -> dict[str, Any] | None:
    # Dynamic bindings need approval after resolution. Never approve a template
    # as if it were the provider payload reviewed by the user.
    if config.get("param_sources"):
        return None
    static = config.get("params", config.get("args"))
    if isinstance(static, dict):
        result = dict(static)
        if config.get("connector_id") is not None:
            result["connector_id"] = config["connector_id"]
        return result
    return {key: value for key, value in config.items() if key not in _DISPATCH_KEYS}


def write_target_fingerprint(*, invoke_action: str, payload: dict[str, Any] | None) -> str | None:
    sealed = _sealed_arguments(invoke_action, payload)
    if sealed is None:
        return None
    body = {
        "invoke_action": str(invoke_action or "").strip(),
        "arguments": sealed,
    }
    raw = json.dumps(body, sort_keys=True, allow_nan=False)
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
        fp = write_target_fingerprint(invoke_action=action, payload=_reviewed_arguments(cfg))
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
