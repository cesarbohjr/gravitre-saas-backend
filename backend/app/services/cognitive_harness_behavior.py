"""Phase D — behavior rules owned by the harness (not duplicated in giant system prompts)."""
from __future__ import annotations

# Compact rules injected where needed instead of re-stating in every prompt surface.
HARNESS_ANALYTICS_RULES = (
    "For analytics traffic asks with a connected GA4 property, prefer live connector reads "
    "over knowledge-base synthesis. Never ask which internal connector taxonomy to use."
)

HARNESS_TERMINAL_RULES = (
    "Do not tell the user you will check later unless pending_task or offered_action is set. "
    "Return a terminal outcome: completed result, honest blocked message, or explicit clarification."
)

HARNESS_REFERENCE_RULES = (
    "Resolve yes/no/all-N/that against the current ExecutionPlan frame "
    "(pending_task, pending_action, offered_action, previous_option_set, "
    "active_analysis, compiled_task projection) — not conversation prose alone. "
    "Follow-ups keep the same plan_id unless the user starts a new task."
)

HARNESS_COMPOSE_RULES = (
    "User-facing replies use structured metric blocks when live reads produced numeric results. "
    "Never expose internal tool names, capability__ ids, or stack traces."
)


def harness_behavior_section(*parts: str) -> str:
    """Build a short harness behavior section for prompts."""
    lines = [p.strip() for p in parts if (p or "").strip()]
    if not lines:
        return ""
    return "HARNESS RULES (authoritative):\n" + "\n".join(f"- {line}" for line in lines)
