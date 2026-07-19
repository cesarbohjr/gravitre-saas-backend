"""Gravitree Voice Layer (Module D).

Single source of truth for product persona — calm expert, facts-first,
Connected/Healthy/Executable/Verified vocabulary. Chat, ReAct, canvas turn
copy, errors, notifications, and Meson MUST call into this module rather than
pasting per-surface VOICE prose.

Pattern mirrors catalog_write_authority: one module, every surface calls in.
Module B (conversation_turn_controller) is the planner ownership point for
connector-turn user-facing strings; Meson calls this module directly until it
enters B.
"""
from __future__ import annotations

from typing import Any

VOICE_SECTION_HEADER = "## Voice"

# Canonical readiness / verification vocabulary (CHEV + Verified).
CHEV_TERMS: dict[str, str] = {
    "connected": "Connected",
    "healthy": "Healthy",
    "executable": "Executable",
    "verified": "Verified",
    "configured": "Configured",
    "authenticated": "Authenticated",
}

GRAVITREE_VOICE_RULES: tuple[str, ...] = (
    "Calm expert: capable operator, not a chatbot persona.",
    "Lead with the fact, then the implication, then the one best next move.",
    "Show your work when a fact comes from a tool or connector result — cite the source briefly in plain language.",
    "State uncertainty plainly when you do not know; never invent connector states, metrics, or agent names.",
    "Never hedge with \"I think\" when you have a real answer from tools or state.",
    "Never over-apologize; refuse safety and governance limits plainly.",
    "Use Connected / Healthy / Executable / Verified (and Configured / Authenticated when describing readiness) — not vague \"working\" or \"smart\".",
    "Avoid buzzwords entirely (synergy, leverage, unlock, seamless, delightful, magical).",
    "Humor is light and rare; never cute.",
    "Complete sentences in chat; short bullets only for 3+ items. No report headers like \"Workflow health:\".",
)

_VOICE_SECTION_BODY = (
    "You are Gravitre — a calm expert operator for enterprise automation.\n"
    "Speak the same way on every surface (chat, ReAct, canvas, Meson, errors, notifications).\n"
    "- Lead with the fact. Show your work when citing tools. State uncertainty plainly.\n"
    "- Never hedge with \"I think\" when you have a real answer. Never over-apologize.\n"
    "- Use Connected / Healthy / Executable / Verified for readiness and outcomes.\n"
    "- No buzzwords. Humor light and rare; never cute.\n"
    "- Refuse safety or governance limits plainly. Never invent names, states, or metrics."
)

_TOOL_ERROR_TEMPLATES: dict[str, str] = {
    "auth_expired": (
        "{integration} authentication expired. "
        "Reconnect it at /connectors, then try again."
    ),
    "permission_denied": (
        "You do not have permission to run this action"
        "{action_suffix}. Ask an admin to grant access, or pick a different tool."
    ),
    "connector_not_connected": (
        "{integration} is not Connected for this organization. "
        "Connect it at /connectors, then try again."
    ),
    "channel_not_found": (
        "That Slack channel was not found (or the bot is not a member). "
        "Use a public channel name/id the bot can access, invite the bot, then try again."
    ),
    "missing_scope": (
        "{integration} is Connected but missing required permissions"
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
    "write_approval_required": ("This write needs your approval before it runs."),
    "tool_not_available": (
        "That tool is not Connected or permitted for this agent. "
        "Connect it at /connectors or switch mode."
    ),
    "action_not_found": ("This action is not implemented yet for {integration}."),
    "tool_error": (
        "{integration} returned an error{action_suffix}. "
        "Check connector health at /connectors — it may not be Healthy."
    ),
    "unverifiable_output": (
        "The connector action completed but returned no Verified output "
        "(missing body and result link)."
    ),
}


def chev_term(status: str | None) -> str:
    """Return canonical CHEV / Verified label for a readiness or outcome status."""
    key = str(status or "").strip().lower()
    if key in CHEV_TERMS:
        return CHEV_TERMS[key]
    return str(status or "").strip()


def voice_system_prompt_section() -> str:
    """The one VOICE block for LLM system prompts."""
    rules = "\n".join(f"- {rule}" for rule in GRAVITREE_VOICE_RULES)
    return f"{VOICE_SECTION_HEADER}\n{_VOICE_SECTION_BODY}\n\nRules:\n{rules}"


def apply_voice(system_prompt: str | None) -> str:
    """Idempotently ensure the canonical Voice section is present exactly once."""
    section = voice_system_prompt_section().strip()
    text = (system_prompt or "").strip()
    if not text:
        return section

    # Strip legacy inline VOICE: blocks from older surface prompts.
    cleaned_lines: list[str] = []
    skipping_voice = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("VOICE:"):
            skipping_voice = True
            continue
        if skipping_voice:
            # Legacy VOICE: was a single multi-line clause ending at OUTPUT: or blank role break.
            if stripped.startswith("OUTPUT:") or stripped.startswith("ROLE:") or stripped.startswith("SECURITY"):
                skipping_voice = False
                cleaned_lines.append(line)
            continue
        if stripped == VOICE_SECTION_HEADER or stripped.startswith(f"{VOICE_SECTION_HEADER} "):
            # Drop existing ## Voice section; re-append canonical below.
            skipping_voice = True
            continue
        if skipping_voice:
            if stripped.startswith("## ") and stripped != VOICE_SECTION_HEADER:
                skipping_voice = False
                cleaned_lines.append(line)
            continue
        cleaned_lines.append(line)

    cleaned = "\n".join(cleaned_lines).strip()
    if not cleaned:
        return section
    return f"{cleaned}\n\n{section}"


def domain_focus_section(modifier: str | None) -> str:
    """Wrap a department persona overlay — domain focus only, never replaces Voice."""
    text = (modifier or "").strip()
    if not text:
        return ""
    return f"## Domain focus\n{text}"


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


def format_operator_message(kind: str, **ctx: Any) -> str:
    """Shared shaper for approval / error / notification / turn-facing user strings."""
    key = str(kind or "").strip().lower()

    if key == "pending_plan_cancelled":
        return "Cancelled the pending plan. What should we do instead?"

    if key == "tool_error":
        code = str(ctx.get("error_code") or "").strip().lower()
        template = _TOOL_ERROR_TEMPLATES.get(code)
        if template:
            return template.format(
                integration=_integration_label(ctx.get("integration")),
                action_suffix=_action_suffix(ctx.get("action")),
            ).strip()
        detail = str(ctx.get("error_message") or "").strip()
        if detail:
            if len(detail) > 400:
                detail = detail[:397] + "..."
            label = _integration_label(ctx.get("integration"))
            if label != "the connector":
                return f"{label} action failed: {detail}"
            return detail
        return "The connector action failed."

    if key == "write_approval":
        return _format_write_approval(**ctx)

    if key == "notification_run_title":
        status = str(ctx.get("status") or "").strip().lower()
        source = str(ctx.get("source") or "").strip().lower()
        if source == "chat_orch":
            if status == "failed":
                return "Orchestration run failed"
            if status == "cancelled":
                return "Orchestration run cancelled"
            return "Orchestration run completed"
        if status == "failed":
            return "Workflow run failed"
        if status == "cancelled":
            return "Workflow run cancelled"
        if status == "partial_success":
            return "Workflow run finished with partial success"
        return "Workflow run completed"

    if key == "notification_run_body":
        status = str(ctx.get("status") or "").strip().lower()
        explicit = str(ctx.get("body") or "").strip()
        if explicit:
            return explicit[:2000]
        error_summary = str(ctx.get("error_summary") or "").strip()
        if status == "failed":
            return (error_summary or "Review the run details for step-level errors.")[:2000]
        if status == "cancelled":
            return (error_summary or "Run was cancelled.")[:2000]
        verified_summary = str(ctx.get("verified_summary") or "").strip()
        if verified_summary:
            return verified_summary[:2000]
        return f"Run finished with status {status or 'completed'}."

    if key == "approval_needed_requester":
        label = str(ctx.get("label") or "This write").strip()
        return f"{label} is waiting in the Decision Queue."

    if key == "approval_needed_requester_title":
        return "Request sent for approval"

    raise ValueError(f"Unknown operator message kind: {kind}")


def _format_write_approval(**ctx: Any) -> str:
    vendor = str(ctx.get("vendor") or "the connected app").strip()
    label = str(ctx.get("label") or "this action").strip()
    details = ctx.get("details") if isinstance(ctx.get("details"), dict) else {}
    list_name = str(ctx.get("list_name") or "").strip()
    invoke_action = str(ctx.get("invoke_action") or "").strip()
    is_list_create = bool(list_name) and "lists.create" in invoke_action

    if is_list_create:
        intro = f"I can create a contact list named **{list_name}** in {vendor}."
        if "segment" in label.lower():
            intro = (
                f"Apollo does not expose CRM segments over API the same way, "
                f"but I can create an equivalent contact list named **{list_name}**."
            )
        lines = [intro]
        for key, value in details.items():
            if str(key).lower() == "name":
                continue
            lines.append(f"- {key}: {value}")
        lines.extend(
            [
                "",
                "Reply **yes** to approve and create it, or say what to change "
                "(name, modality, or follow-up criteria to populate it).",
            ]
        )
        return "\n".join(lines)

    lines = [f"I'll run this in {vendor}: **{label}**."]
    if details:
        lines.append("")
        for key, value in details.items():
            lines.append(f"- {key}: {value}")
    lines.extend(["", "Reply **yes** to approve, or say what to change."])
    return "\n".join(lines)


def tool_error_template(error_code: str) -> str | None:
    """Expose voice-owned tool error templates for the error formatter adapter."""
    return _TOOL_ERROR_TEMPLATES.get(str(error_code or "").strip().lower())
