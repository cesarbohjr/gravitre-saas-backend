"""Structured execution status envelopes for chat and connector actions."""
from __future__ import annotations

from typing import Any, Literal

NotExecutableReason = Literal[
    "missing_scope",
    "missing_connector",
    "missing_permission",
    "not_implemented",
    "requires_approval",
    "token_expired",
    "unsupported_action",
]


def build_not_executable(
    reason: NotExecutableReason | str,
    *,
    next_step: str = "",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "status": "not_executable",
        "reason": reason,
        "next_step": next_step,
        "metadata": metadata or {},
    }


def format_operator_response(
    *,
    intent: str,
    status: str,
    matched_action: str | None = None,
    result: str = "",
    missing_connector: str | None = None,
    missing_action: str | None = None,
    missing_parameters: list[str] | None = None,
    known: dict[str, Any] | None = None,
    disambiguation_options: list[str] | None = None,
    available_actions: list[str] | None = None,
    next_step: str = "",
    planned: dict[str, Any] | None = None,
) -> str:
    """Conversational operator reply — status + next step without rigid field labels."""
    status_clean = status.replace("blocked — ", "").strip()
    lines: list[str] = []

    if "connector not ready" in status or missing_connector:
        connector = missing_connector or "that integration"
        lines.append(f"I can't run **{intent}** yet because {connector} isn't ready.")
    elif "action not matched" in status and matched_action:
        lines.append(
            f"I understand you want to **{intent}**, and `{matched_action}` is available — "
            "I just need a clearer phrasing to map it safely."
        )
    elif "action not in catalog" in status or missing_action:
        lines.append(f"I can't complete **{intent}** with the actions that are currently wired up.")
        if missing_action:
            lines.append(f"The missing capability is `{missing_action}`.")
    elif "no matching catalog action" in status:
        lines.append(f"I couldn't map **{intent}** to a specific connector action yet.")
    else:
        lines.append(f"Here's where things stand on **{intent}**: {status_clean}.")

    if result:
        lines.append("")
        lines.append(result)

    display_known = dict(known or {})
    if planned:
        display_known = {**display_known, **planned}
    known_bits = [f"{key}: {value}" for key, value in display_known.items() if value]
    if known_bits:
        lines.append("")
        lines.append("What I already have:")
        for bit in known_bits:
            lines.append(f"- {bit}")

    if missing_parameters:
        lines.append("")
        lines.append("Still needed:")
        for item in missing_parameters:
            lines.append(f"- {item}")

    if disambiguation_options:
        lines.append("")
        lines.append("I found a few matches — which one should I use?")
        for option in disambiguation_options[:8]:
            lines.append(f"- {option}")

    if available_actions and (
        "action not" in status or "no matching" in status or missing_action
    ):
        lines.append("")
        lines.append("Available actions on this connector:")
        for action in available_actions[:8]:
            lines.append(f"- {action}")

    if next_step:
        lines.append("")
        lines.append(next_step)

    return "\n".join(lines).strip()


def format_not_executable_message(payload: dict[str, Any]) -> str:
    metadata = payload.get("metadata") or {}
    if metadata.get("operator_format"):
        return format_operator_response(
            intent=str(metadata.get("intent") or "Connector action"),
            status=str(metadata.get("status") or "blocked"),
            matched_action=metadata.get("matched_action"),
            result=str(metadata.get("result") or ""),
            missing_connector=metadata.get("missing_connector"),
            missing_action=metadata.get("missing_action"),
            missing_parameters=metadata.get("missing_parameters"),
            known=metadata.get("known"),
            disambiguation_options=metadata.get("disambiguation_options"),
            available_actions=metadata.get("available_actions"),
            next_step=str(payload.get("next_step") or metadata.get("next_step") or ""),
            planned=metadata.get("planned"),
        )

    reason = str(payload.get("reason") or "not_implemented")
    next_step = str(payload.get("next_step") or "").strip()
    labels = {
        "missing_scope": "This action needs a connector scope that is not configured.",
        "missing_connector": "This integration is not connected in this workspace.",
        "missing_permission": "Your role does not allow this action.",
        "not_implemented": "No catalog action matches this request yet.",
        "requires_approval": "This action requires explicit approval before it can run.",
        "token_expired": "The connector is configured, but authentication has expired.",
        "unsupported_action": "This connector action is not supported yet.",
    }
    base = labels.get(reason, "This action cannot run right now.")
    return f"{base} {next_step}".strip()
