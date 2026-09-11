"""Typed user-facing result envelope — reuse NormalizedResult, do not invent a second schema.

Canonical fields (STA verified-completion + tool layer):

    {success, data, error_code, error_detail}

`error_detail` is an alias of NormalizedResult.error_message. Callers that still
emit `error` / `error_message` are coerced at the invoke boundary so the Composer
never receives a bare string or raw exception.
"""
from __future__ import annotations

from typing import Any

from app.services.tool_types import NormalizedResult, ToolError

ENVELOPE_KEYS = ("success", "data", "error_code", "error_detail")

_ERROR_ALIASES = ("error_detail", "error_message", "error", "message", "detail")
_CODE_ALIASES = ("error_code", "errorCode", "code")


def _first_str(payload: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = payload.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _as_data(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if value is None:
        return {}
    return {"value": value}


def coerce_user_envelope(value: Any, *, action: str = "") -> dict[str, Any]:
    """Normalize any tool/backend payload into the canonical envelope.

    Preserves extra keys (tool, result, candidates, …) so existing chip/ReAct
    consumers keep working. Always emits success/data/error_code/error_detail.
    """
    if isinstance(value, NormalizedResult):
        payload: dict[str, Any] = {
            "success": bool(value.success),
            "data": dict(value.data or {}),
            "error_code": value.error_code,
            "error_detail": value.error_message,
            "error_message": value.error_message,
            "action": value.action or action,
            "connector_id": value.connector_id,
        }
        if value.error_message and "error" not in payload:
            payload["error"] = value.error_message
        if value.success and payload["data"] and "result" not in payload:
            payload["result"] = payload["data"]
        return payload

    if isinstance(value, ToolError):
        detail = str(value) or "Tool invocation failed"
        return {
            "success": False,
            "data": {},
            "error_code": getattr(value, "code", None) or "tool_error",
            "error_detail": detail,
            "error": detail,
            "action": action or None,
        }

    if isinstance(value, BaseException):
        detail = str(value) or value.__class__.__name__
        return {
            "success": False,
            "data": {},
            "error_code": "tool_error",
            "error_detail": detail,
            "error": detail,
            "action": action or None,
        }

    if not isinstance(value, dict):
        text = "" if value is None else str(value)
        return {
            "success": True,
            "data": {"text": text} if text else {},
            "error_code": None,
            "error_detail": None,
            "action": action or None,
        }

    payload = dict(value)
    error_detail = _first_str(payload, _ERROR_ALIASES)
    error_code = _first_str(payload, _CODE_ALIASES)
    explicit_fail = payload.get("success") is False or bool(error_detail) or bool(error_code)
    success = bool(payload.get("success", not explicit_fail))
    if explicit_fail:
        success = False

    data = payload.get("data")
    if not isinstance(data, dict):
        if isinstance(payload.get("result"), dict):
            data = dict(payload["result"])
        elif data is not None:
            data = _as_data(data)
        else:
            data = {}

    if not success and not error_code:
        error_code = "tool_error"
    if success:
        error_code = payload.get("error_code") or payload.get("errorCode") or None
        if not error_detail:
            error_detail = None

    action_name = str(payload.get("action") or payload.get("tool") or action or "").strip() or None

    out: dict[str, Any] = dict(payload)
    out["success"] = success
    out["data"] = data
    out["error_code"] = error_code
    out["error_detail"] = error_detail
    if error_detail and not out.get("error"):
        out["error"] = error_detail
    if action_name and not out.get("action"):
        out["action"] = action_name
    if success and data and "result" not in out:
        out["result"] = data
    return out


def envelope_kind(envelope: dict[str, Any]) -> str:
    """Map a structured envelope onto a Composer kind."""
    if not isinstance(envelope, dict):
        return "canned"
    if envelope.get("success") is not False:
        return "success"
    code = str(envelope.get("error_code") or "").strip().lower()
    if code in {"permission_denied", "missing_scope", "auth_expired"}:
        return "permission"
    if code in {"connector_timeout", "timeout", "statement_timeout"}:
        return "timeout"
    if code in {"validation_error", "channel_not_found", "connector_not_connected"}:
        return "validation"
    return "error"
