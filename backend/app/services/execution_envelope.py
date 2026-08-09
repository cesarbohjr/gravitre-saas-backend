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
    """Conversational operator reply — Module D voice; never expose catalog action ids."""
    from app.services.gravitre_voice import format_operator_message
    from app.services.user_facing_copy_guard import (
        finalize_user_facing_message,
        user_facing_available_action_labels,
    )

    status_clean = status.replace("blocked — ", "").strip()
    status_l = status.lower()
    lines: list[str] = []
    voice_kwargs = {"confidence_register": "blocked", "allow_humor": False}

    if "connector not ready" in status_l or missing_connector:
        connector = missing_connector or "that integration"
        lines.append(
            format_operator_message(
                "connector_connect_to_run",
                integration=connector,
                **voice_kwargs,
            )
        )
        if intent:
            lines.append(f"I was working on: **{intent}**.")
    elif "needs clarification" in status_l:
        lines.append(f"I can help with **{intent}** once I have a few more details.")
    elif (
        "action not matched" in status_l
        or "action not in catalog" in status_l
        or "no matching catalog action" in status_l
        or missing_action
        or matched_action
    ):
        lines.append(format_operator_message("no_executable_action", **voice_kwargs))
        if intent:
            lines.append(f"What you asked for: **{intent}**.")
    else:
        lines.append(
            format_operator_message(
                "blocked",
                blocker=f"Here's where things stand on **{intent}**: {status_clean}.",
                next_action="Tell me which connected app should handle this, in plain language.",
                **voice_kwargs,
            )
        )

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
        lines.append(format_operator_message("missing_parameters_header", **voice_kwargs))
        for item in missing_parameters:
            lines.append(f"- {item}")

    if disambiguation_options:
        lines.append("")
        lines.append("I found a few matches — which one should I use?")
        for option in disambiguation_options[:8]:
            lines.append(f"- {option}")

    if available_actions and (
        "action not" in status_l or "no matching" in status_l or missing_action
    ):
        labels = user_facing_available_action_labels(available_actions)
        if labels:
            lines.append("")
            lines.append("Here's what I can do with this integration right now:")
            for label in labels[:8]:
                lines.append(f"- {label}")

    if next_step:
        lines.append("")
        lines.append(next_step)

    return finalize_user_facing_message(
        "\n".join(lines).strip(),
        context="format_operator_response",
    )


def format_not_executable_message(payload: dict[str, Any]) -> str:
    from app.services.user_facing_copy_guard import finalize_user_facing_message

    metadata = payload.get("metadata") or {}
    if metadata.get("operator_format"):
        text = format_operator_response(
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
        return finalize_user_facing_message(text, context="format_not_executable_message")

    from app.services.gravitre_voice import format_operator_message

    reason = str(payload.get("reason") or "not_implemented")
    next_step = str(payload.get("next_step") or "").strip()
    voice_kwargs = {"confidence_register": "blocked", "allow_humor": False}
    if reason == "missing_connector":
        integration = payload.get("missing_connector") or (payload.get("metadata") or {}).get(
            "missing_connector"
        )
        base = format_operator_message(
            "connector_connect_to_run",
            integration=integration or "the connector",
            **voice_kwargs,
        )
    elif reason == "requires_approval":
        base = format_operator_message(
            "tool_error",
            error_code="write_approval_required",
            **voice_kwargs,
        )
    elif reason == "token_expired":
        base = format_operator_message(
            "tool_error",
            error_code="auth_expired",
            integration=(payload.get("metadata") or {}).get("integration"),
            **voice_kwargs,
        )
    elif reason == "missing_scope":
        base = format_operator_message(
            "tool_error",
            error_code="missing_scope",
            integration=(payload.get("metadata") or {}).get("integration"),
            **voice_kwargs,
        )
    elif reason in {"not_implemented", "unsupported_action"}:
        base = format_operator_message("no_executable_action", **voice_kwargs)
    elif reason == "missing_permission":
        base = format_operator_message(
            "tool_error",
            error_code="permission_denied",
            **voice_kwargs,
        )
    else:
        base = format_operator_message(
            "blocked",
            blocker="This action cannot run right now.",
            next_action=next_step or "Check connectors and try again.",
            **voice_kwargs,
        )
        return finalize_user_facing_message(
            f"{base} {next_step}".strip(),
            context="format_not_executable_message",
        )
    combined = f"{base} {next_step}".strip()
    return finalize_user_facing_message(combined, context="format_not_executable_message")
