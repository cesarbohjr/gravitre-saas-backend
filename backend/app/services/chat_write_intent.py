"""Comprehend connector write intents and gate tool proposals before approval.

All catalog tiers stay visible to chat — this module decides whether to proceed,
ask a clarifying question, or reject a mismatched proposal (never silent remaps).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal

GmailWriteFamily = Literal["single_send", "batch", "draft", "thread", "none"]

EMAIL_SEND_INTENT = re.compile(
    r"(?:\b(?:send|compose|email)\b.+\b(?:email|outlook|microsoft\s*365|o365|gmail)\b)"
    r"|(?:\b(?:outlook|microsoft\s*365|o365|gmail)\b.+\b(?:send|compose|email)\b)"
    r"|(?:\bsend\s+(?:an?\s+)?email\b)"
    r"|(?:\bemail\b.+\b(?:to|@)\b)",
    re.I,
)
GMAIL_EMAIL_MENTION = re.compile(r"\b(?:gmail|send\s+mail|send\s+email|email)\b", re.I)
BATCH_INTENT = re.compile(
    r"\b(?:batch|bulk|multiple\s+messages?|message_ids?|modify\s+messages?\s+in\s+bulk)\b",
    re.I,
)
DRAFT_INTENT = re.compile(r"\b(?:create\s+a?\s*draft|save\s+(?:as\s+)?draft|draft\s+(?:an?\s+)?email)\b", re.I)
THREAD_INTENT = re.compile(
    r"\b(?:thread\s+labels?|label\s+(?:the\s+)?thread|modify\s+thread)\b",
    re.I,
)
SINGLE_SEND_CHOICE = re.compile(
    r"\b(?:single|one\s+email|send\s+one|send\s+email|just\s+send)\b",
    re.I,
)
BATCH_CHOICE = re.compile(r"\bbatch\b|\bbulk\b|\bmultiple\s+messages?\b", re.I)
DRAFT_CHOICE = re.compile(r"\bdraft\b", re.I)
THREAD_CHOICE = re.compile(
    r"\bthread\b|\b(?:label|modify)\s+(?:the\s+)?thread\b|\bthread\s+labels?\b",
    re.I,
)
READ_ONLY_GMAIL = re.compile(r"\b(?:list|show|get|fetch|read|search|find)\b", re.I)

GMAIL_FAMILIES: dict[GmailWriteFamily, tuple[str, str, str]] = {
    "single_send": ("gmail.messages.send", "gmail_messages_send", "Send email"),
    "batch": ("gmail.messages.batch", "gmail_messages_batch", "Batch modify messages"),
    "draft": ("gmail.drafts.create", "gmail_drafts_create", "Create draft"),
    "thread": ("gmail.threads.modify", "gmail_threads_modify", "Modify thread labels"),
}


@dataclass(frozen=True)
class ToolProposalReview:
    action: Literal["accept", "clarify"]
    clarify_message: str = ""
    tool_name: str = ""
    invoke_action: str = ""
    tool_arguments: dict[str, Any] = field(default_factory=dict)
    intent: GmailWriteFamily = "none"


def is_gmail_send_intent(message: str) -> bool:
    return classify_gmail_write_intent(message) == "single_send"


def classify_gmail_write_intent(message: str) -> GmailWriteFamily:
    text = (message or "").strip()
    if not text:
        return "none"
    if READ_ONLY_GMAIL.search(text) and not EMAIL_SEND_INTENT.search(text):
        return "none"
    choice = detect_gmail_action_choice(text)
    if choice:
        return choice
    if BATCH_INTENT.search(text):
        return "batch"
    if DRAFT_INTENT.search(text):
        return "draft"
    if THREAD_INTENT.search(text):
        return "thread"
    if EMAIL_SEND_INTENT.search(text):
        return "single_send"
    if GMAIL_EMAIL_MENTION.search(text) and re.search(
        r"\b(?:write|do|something|help|email)\b", text, re.I
    ):
        return "none"  # too vague — only clarify when a gmail write tool is proposed
    return "none"


def detect_gmail_action_choice(message: str) -> GmailWriteFamily | None:
    text = (message or "").strip()
    if not text:
        return None
    if BATCH_CHOICE.search(text) and not SINGLE_SEND_CHOICE.search(text):
        return "batch"
    if DRAFT_CHOICE.search(text):
        return "draft"
    if THREAD_CHOICE.search(text) and not EMAIL_SEND_INTENT.search(text):
        return "thread"
    if SINGLE_SEND_CHOICE.search(text) or EMAIL_SEND_INTENT.search(text):
        return "single_send"
    return None


def _gmail_family_for_tool(tool_name: str, invoke_action: str | None) -> GmailWriteFamily:
    name = str(tool_name or "").strip().lower()
    invoke = str(invoke_action or "").strip().lower()
    for family, (inv, reg_name, _label) in GMAIL_FAMILIES.items():
        if invoke == inv or name == reg_name:
            return family
    if name.startswith("gmail_") or invoke.startswith("gmail."):
        return "none"
    return "none"


def _missing_required_args(family: GmailWriteFamily, args: dict[str, Any]) -> list[str]:
    merged = dict(args or {})
    if family == "single_send":
        missing: list[str] = []
        if not str(merged.get("to") or merged.get("email") or "").strip():
            missing.append("recipient (to)")
        if not str(merged.get("subject") or "").strip():
            missing.append("subject")
        if not str(merged.get("body") or merged.get("html_body") or merged.get("message") or "").strip():
            missing.append("body")
        return missing
    if family == "batch":
        ids = merged.get("message_ids") or merged.get("ids") or []
        if not ids:
            return ["message IDs to modify"]
        return []
    if family == "draft":
        if not str(merged.get("to") or "").strip():
            return ["draft recipient (to)"]
        return []
    if family == "thread":
        if not str(merged.get("thread_id") or "").strip():
            return ["thread ID"]
        return []
    return []


def _gmail_options_clarify(*, lead: str) -> str:
    options = ", ".join(f"**{label}**" for _, _, label in GMAIL_FAMILIES.values())
    return (
        f"{lead} For Gmail I can: {options}. "
        "Which one do you want — single send, batch, draft, or thread labels?"
    )


def _gmail_mismatch_clarify(
    *,
    intent: GmailWriteFamily,
    proposed_label: str,
    user_message: str,
) -> str:
    _, _, intended_label = GMAIL_FAMILIES[intent]
    snippet = re.sub(r"\s+", " ", (user_message or "").strip())[:120]
    return (
        f"You asked to {intended_label.lower()} ({snippet or 'this request'}), "
        f"but I was about to run **{proposed_label}** instead. "
        f"Should I proceed with **{intended_label}**, or did you mean **{proposed_label}**? "
        "Reply with the action you want (e.g. **send email**, **batch**, **draft**, **thread labels**)."
    )


def build_gmail_write_intent_prompt_section(message: str) -> str:
    intent = classify_gmail_write_intent(message or "")
    if intent == "none":
        return ""
    _, _, label = GMAIL_FAMILIES[intent]
    return (
        "DETECTED GMAIL WRITE INTENT (authoritative — pick the matching tool or ask one clarifying "
        f"question if still ambiguous):\n- User intent: {label} ({intent})\n"
        "- Do not substitute a different Gmail write action unless the user chooses it."
    )


def evaluate_connector_tool_proposal(
    *,
    message: str,
    tool_name: str,
    invoke_action: str | None,
    args: dict[str, Any] | None,
) -> ToolProposalReview:
    """Return accept or a clarifying question — never silently remap tools."""
    name = str(tool_name or "").strip()
    invoke = str(invoke_action or "").strip()
    merged_args = dict(args or {})
    proposed_family = _gmail_family_for_tool(name, invoke)
    if proposed_family == "none":
        return ToolProposalReview(
            action="accept",
            tool_name=name,
            invoke_action=invoke,
            tool_arguments=merged_args,
        )

    intent = classify_gmail_write_intent(message or "")
    _, _, proposed_label = GMAIL_FAMILIES[proposed_family]

    if intent == "none" and proposed_family in {"batch", "draft", "thread"}:
        # Model picked an advanced Gmail action without explicit user wording — confirm.
        return ToolProposalReview(
            action="clarify",
            clarify_message=_gmail_options_clarify(
                lead=f"I can run **{proposed_label}**, but your request did not specify which Gmail email action you need."
            ),
            intent=proposed_family,
        )

    if intent != "none" and intent != proposed_family:
        return ToolProposalReview(
            action="clarify",
            clarify_message=_gmail_mismatch_clarify(
                intent=intent,
                proposed_label=proposed_label,
                user_message=message,
            ),
            intent=intent,
        )

    missing = _missing_required_args(proposed_family, merged_args)
    if missing and proposed_family == "batch":
        return ToolProposalReview(
            action="clarify",
            clarify_message=(
                f"**{proposed_label}** needs {', '.join(missing)}. "
                "Send the message IDs (or ask me to list/search messages first)."
            ),
            intent=proposed_family,
        )

    return ToolProposalReview(
        action="accept",
        tool_name=name,
        invoke_action=invoke,
        tool_arguments=merged_args,
        intent=proposed_family if intent == "none" else intent,
    )


# Backward-compatible alias — callers should migrate to evaluate_connector_tool_proposal.
def correct_gmail_send_tool_proposal(
    *,
    tool_name: str,
    invoke_action: str | None,
    args: dict,
    message: str,
) -> tuple[str, str, dict] | None:
    review = evaluate_connector_tool_proposal(
        message=message,
        tool_name=tool_name,
        invoke_action=invoke_action,
        args=args,
    )
    if review.action != "accept":
        return None
    if review.tool_name == tool_name and review.invoke_action == (invoke_action or ""):
        return None
    return review.tool_name, review.invoke_action, review.tool_arguments
