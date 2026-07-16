"""Map tool/connector error_code values to actionable user-facing copy.

Wave 3 — stop LLM-narrated generic failures when a structured error_code exists.
"""
from __future__ import annotations

from typing import Any

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

_TOOL_ERROR_USER_MESSAGES: dict[str, str] = {
    "auth_expired": (
        "Authentication expired for {integration}. "
        "Reconnect it at /connectors, then try again."
    ),
    "permission_denied": (
        "You don't have permission to run this action"
        "{action_suffix}. Ask an admin to grant access, or pick a different tool."
    ),
    "connector_not_connected": (
        "{integration} is not connected for this organization. "
        "Connect it at /connectors, then try again."
    ),
    "channel_not_found": (
        "That Slack channel was not found (or the bot is not a member). "
        "Use a public channel name/id the bot can access, invite the bot, then try again."
    ),
    "missing_scope": (
        "{integration} is connected but missing required permissions"
        "{action_suffix}. Reconnect it at /connectors and approve the requested scopes."
    ),
    "validation_error": (
        "Invalid parameters for this {integration} action{action_suffix}. "
        "Check required fields and try again."
    ),
    "rate_limited": (
        "{integration} rate-limited the request. Wait a moment and try again."
    ),
    "connector_timeout": (
        "{integration} did not respond in time. Try again shortly."
    ),
    "write_approval_required": (
        "This write needs your approval before it runs."
    ),
    "tool_not_available": (
        "That tool isn't connected or permitted for this agent. "
        "Connect it at /connectors or switch mode."
    ),
    "action_not_found": (
        "This action isn't implemented yet for {integration}."
    ),
    "tool_error": (
        "{integration} returned an error{action_suffix}. "
        "Check connector health at /connectors."
    ),
    "unverifiable_output": (
        "The connector action completed but returned no verifiable output "
        "(missing body and result link)."
    ),
}


def _integration_label(integration: str | None) -> str:
    value = str(integration or "").strip().replace("_", " ")
    if not value:
        return "the connector"
    return value.title()


def _action_suffix(action: str | None) -> str:
    value = str(action or "").strip()
    if not value:
        return ""
    return f" ({value})"


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

    template = _TOOL_ERROR_USER_MESSAGES.get(code)
    if template:
        return template.format(
            integration=_integration_label(integration),
            action_suffix=_action_suffix(action),
        ).strip()

    if detail:
        # Avoid dumping huge vendor payloads into chat.
        if len(detail) > 400:
            detail = detail[:397] + "..."
        label = _integration_label(integration)
        if label != "the connector":
            return f"{label} action failed: {detail}"
        return detail
    return "The connector action failed."


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
