"""Sanitize visibility payloads — never expose chain-of-thought or hidden prompts."""
from __future__ import annotations

import re
from typing import Any

FORBIDDEN_KEYS = frozenset(
    {
        "chain_of_thought",
        "chain-of-thought",
        "reasoning_trace",
        "reasoning_traces",
        "raw_prompt",
        "system_prompt",
        "hidden_prompt",
        "internal_instructions",
        "consensus_discussion",
        "deliberation",
        "model_token_stream",
        "token_stream",
        "minority_opinions",
        "vote_breakdown",
        "agent_deliberations",
    }
)

FORBIDDEN_KEY_PATTERNS = (
    re.compile(r".*_prompt$"),
    re.compile(r".*trace$"),
    re.compile(r"^prompt_.*"),
)


def _is_forbidden_key(key: str) -> bool:
    lowered = str(key or "").lower()
    if lowered in FORBIDDEN_KEYS:
        return True
    return any(pattern.match(lowered) for pattern in FORBIDDEN_KEY_PATTERNS)


def sanitize_visibility_payload(value: Any) -> Any:
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for key, item in value.items():
            if _is_forbidden_key(str(key)):
                continue
            cleaned[str(key)] = sanitize_visibility_payload(item)
        return cleaned
    if isinstance(value, list):
        return [sanitize_visibility_payload(item) for item in value]
    if isinstance(value, str):
        lowered = value.lower()
        if "chain-of-thought" in lowered or "system prompt" in lowered:
            return "[redacted]"
        return value
    return value


def sanitize_envelope(envelope: dict[str, Any]) -> dict[str, Any]:
    sanitized = sanitize_visibility_payload(envelope)
    sanitized["advisory_only"] = True
    return sanitized
