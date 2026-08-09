"""Map tool/connector error_code values to actionable user-facing copy.

Wave 3 — stop LLM-narrated generic failures when a structured error_code exists.
Copy is owned by Module D gravitre_voice; this module is the adapter.
"""
from __future__ import annotations

from typing import Any

from app.services.gravitre_voice import format_operator_message

# Codes that should short-circuit ReAct instead of letting the model paraphrase.
REACT_SHORT_CIRCUIT_ERROR_CODES = frozenset(
    {
        "auth_expired",
        "permission_denied",
        "validation_error",
        "connector_not_connected",
        "channel_not_found",
        "missing_scope",
        "rate_limited",
        "connector_timeout",
        "tool_not_available",
        "action_not_found",
        "tool_error",
    }
)


def format_tool_error_for_user(
    error_code: str | None,
    error_message: str | None = None,
    *,
    integration: str | None = None,
    action: str | None = None,
    reason: str | None = None,
) -> str:
    """Return actionable user copy for a tool/connector failure."""
    code = str(error_code or "").strip().lower()
    detail = str(error_message or "").strip()
    reason_text = str(reason or "").strip().lower()
    action_l = str(action or "").strip().lower()
    integration_l = str(integration or "").strip().lower()

    # Apollo discovery BYO-tier — prefer explicit plan-limit copy over generic permission_denied
    from app.connectors.apollo_discovery_capability import (
        APOLLO_DISCOVERY_USER_MESSAGE,
        is_apollo_discovery_plan_limit_text,
    )

    apollo_discovery_action = any(
        tip in action_l
        for tip in ("people.search", "organizations.search", "companies.search", "contacts.search")
    ) or not action_l
    if (
        integration_l == "apollo"
        or "apollo" in action_l
        or is_apollo_discovery_plan_limit_text(detail)
        or reason_text == "apollo_plan_limit"
        or is_apollo_discovery_plan_limit_text(reason_text)
    ) and (
        reason_text == "apollo_plan_limit"
        or is_apollo_discovery_plan_limit_text(detail)
        or (code == "permission_denied" and apollo_discovery_action and is_apollo_discovery_plan_limit_text(detail))
    ):
        return APOLLO_DISCOVERY_USER_MESSAGE

    # When permission_denied carries the free-plan body even without integration hint
    if code == "permission_denied" and is_apollo_discovery_plan_limit_text(detail):
        return APOLLO_DISCOVERY_USER_MESSAGE

    return format_operator_message(
        "tool_error",
        error_code=code,
        error_message=detail,
        integration=integration,
        action=action,
    )

def integration_from_tool_name(tool_name: str | None) -> str | None:
    """Best-effort vendor from registry tool name (e.g. apollo_lists_create → apollo)."""
    name = str(tool_name or "").strip()
    if not name:
        return None
    if "." in name:
        return name.split(".", 1)[0] or None
    if "_" in name:
        return name.split("_", 1)[0] or None
    return name or None


def format_react_connector_failure(tool_calls: list[dict[str, Any]] | None) -> str | None:
    """Build user copy from the last failed ReAct tool call that has an error_code."""
    if not tool_calls:
        return None
    for call in reversed(list(tool_calls)):
        if not isinstance(call, dict):
            continue
        result = call.get("result") if isinstance(call.get("result"), dict) else {}
        if result.get("success") is True:
            continue
        code = result.get("error_code") or call.get("error_code")
        if not code:
            continue
        if str(code).strip().lower() == "write_approval_required":
            continue
        tool = str(call.get("tool") or call.get("name") or "")
        return format_tool_error_for_user(
            str(code),
            str(result.get("error") or call.get("error") or ""),
            integration=integration_from_tool_name(tool),
            action=str(result.get("action") or ""),
            reason=str((result.get("details") or {}).get("reason") or result.get("reason") or ""),
        )
    return None
