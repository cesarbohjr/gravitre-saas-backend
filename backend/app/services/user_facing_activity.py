"""User-facing live activity labels for chat/voice status.

AI State ↔ Backend State Matrix for streaming status:
internal telemetry (kernel stages, logger names, snake_case codes) never
reaches the user. Unmapped states fail closed to SAFE_FALLBACK.
"""

from __future__ import annotations

import re
from typing import Any

SAFE_STATUS_FALLBACK = "Working on it…"

# Known backend answer_explanation / phase strings → human copy.
# Keys must match the exact strings historically emitted on SSE.
KNOWN_ACTIVITY_LABELS: dict[str, str] = {
    "cognitiveturnkernel pre-act complete": "Reviewing context and memory",
    "routing classified": "Understanding your request",
    "plan ready — running tools": "Running connected tools",
    "plan ready - running tools": "Running connected tools",
    "unified turn live": "Working on your request",
    "orphan_plan_unclear_ask": "Waiting for your direction",
    "retrieve-before-generate": "Looking up a matching plan",
    "retrieve-before-generate (clarify, no fabrication)": "Looking up a matching plan",
    "conversational path (non-task)": "Replying",
    "swarm step-level transparency": "Summarizing agent work",
    "inline vendor preview": "Loading a preview",
    "conversational operator execution": "Running the requested action",
    "multi-step connector orchestration": "Coordinating connected tools",
    "governed connector execution": "Preparing a governed action",
    "react write gated for user approval": "Preparing something for your approval",
    "connector fallback after react": "Trying a connected-tool fallback",
    "analyzing your request…": "Understanding your request",
    "analyzing your request": "Understanding your request",
    "reviewing connected systems and knowledge…": "Checking your connected tools",
    "reviewing connected systems and knowledge": "Checking your connected tools",
    "reviewing context and memory": "Reviewing context and memory",
}

# Prefixes of telemetry-shaped explanations that still have honest user copy.
_PREFIX_LABELS: tuple[tuple[str, str], ...] = (
    ("cognitiveturnkernel", "Reviewing context and memory"),
    ("unified turn live", "Working on your request"),
    ("retrieve-before-generate", "Looking up a matching plan"),
    ("clarification needed", "Figuring out what to ask next"),
    ("routing escalated", "Looking more closely at this request"),
)

_SNAKE_CODE = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)+$")
_LOGGER_LEVEL = re.compile(r"\.(info|debug|warning|error|warn|critical)\b", re.I)
_KERNEL_TOKEN = re.compile(
    r"CognitiveTurnKernel|\bpre-ACT\b|\bkernel\b|cognitive_turn_kernel",
    re.I,
)
_PASCAL_SERVICE = re.compile(
    r"\b(?:[A-Z][a-zA-Z0-9]+){0,3}(?:Kernel|Engine|Orchestrator|Service|Adapter)\b"
)
_CAMEL_ID = re.compile(r"^[a-z]+(?:[A-Z][a-zA-Z0-9]+)+$")
_DOTTED_CATALOG = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z0-9_]+){2,}$", re.I)
_SSE_PREFIX = re.compile(r"^(Running:|Completed:|Step \d+/\d+:)\s*", re.I)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower()).replace("…", "").strip()


def looks_like_internal_status(text: str | None) -> bool:
    """True when a string is telemetry / class / logger shaped, not operator copy."""
    raw = (text or "").strip()
    if not raw:
        return True
    if _KERNEL_TOKEN.search(raw):
        return True
    if _LOGGER_LEVEL.search(raw):
        return True
    if _PASCAL_SERVICE.search(raw):
        return True
    compact = raw.replace("…", "").strip()
    if _SNAKE_CODE.match(compact):
        return True
    if _CAMEL_ID.match(compact):
        return True
    if _DOTTED_CATALOG.match(compact):
        return True
    return False


def specific_connector_status(connectors: list[str] | tuple[str, ...] | None) -> str | None:
    names = []
    for item in connectors or []:
        label = str(item or "").strip().replace("_", " ")
        if not label:
            continue
        names.append(label.title() if label.islower() or "_" in str(item) else label)
    if not names:
        return None
    if len(names) == 1:
        return f"Checking your {names[0]} account"
    shown = names[:3]
    extra = len(names) - len(shown)
    joined = ", ".join(shown)
    if extra > 0:
        return f"Checking {len(names)} connected tools ({joined}, +{extra} more)"
    return f"Checking {len(names)} connected tools ({joined})"


def _apply_known_or_prefix(raw: str, connectors: list[str] | tuple[str, ...] | None) -> str | None:
    mapped = KNOWN_ACTIVITY_LABELS.get(_norm(raw))
    if mapped:
        if "connected" in mapped.lower():
            specific = specific_connector_status(connectors)
            if specific:
                return specific
        return mapped
    lower = raw.lower()
    for prefix, label in _PREFIX_LABELS:
        if lower.startswith(prefix):
            if "connected" in label.lower():
                specific = specific_connector_status(connectors)
                if specific:
                    return specific
            return label
    return None


def sanitize_user_activity_label(
    text: str | None,
    *,
    connectors: list[str] | tuple[str, ...] | None = None,
    fallback: str = SAFE_STATUS_FALLBACK,
) -> str:
    """Map or fail-closed. Never return the raw internal name."""
    raw = (text or "").strip()
    if not raw:
        return fallback
    stripped = _SSE_PREFIX.sub("", raw).strip()
    if stripped and stripped != raw:
        return sanitize_user_activity_label(
            stripped,
            connectors=connectors,
            fallback=fallback,
        )
    known = _apply_known_or_prefix(raw, connectors)
    if known:
        return known
    if looks_like_internal_status(raw):
        return fallback
    return raw


def user_status_payload(
    text: str | None,
    *,
    connectors: list[str] | tuple[str, ...] | None = None,
) -> dict[str, Any]:
    label = sanitize_user_activity_label(text, connectors=connectors)
    return {"label": label, "internal": looks_like_internal_status(text)}
