"""Guardrails: user-facing copy must never expose raw connector catalog action keys."""
from __future__ import annotations

import re
from typing import Iterable

# Internal ids like gmail.messages.list (at least vendor.resource.verb — two dots).
RAW_CATALOG_ACTION_KEY = re.compile(
    r"\b[a-z][a-z0-9_]*(?:\.[a-z0-9_]+){2,}\b",
    re.IGNORECASE,
)


def humanize_catalog_action_key(action_key: str) -> str:
    """Turn a catalog action id into plain language (never echo the dotted key)."""
    key = (action_key or "").strip()
    if not key:
        return ""
    if not RAW_CATALOG_ACTION_KEY.fullmatch(key.lower()):
        return key

    try:
        from app.connectors.action_catalog.registry import get_action_spec

        spec = get_action_spec(key)
        if spec is not None:
            description = str(getattr(spec, "description", "") or "").strip()
            if description:
                return description
    except Exception:  # noqa: BLE001
        pass

    parts = [p for p in key.split(".") if p]
    if len(parts) >= 2:
        vendor = parts[0].replace("_", " ").title()
        verb = parts[-1].replace("_", " ")
        return f"{verb} in {vendor}"
    return key.replace("_", " ").title()


def user_facing_available_action_labels(available_actions: Iterable[str]) -> list[str]:
    """Extract human labels from chat action rows (`key — Display name`)."""
    labels: list[str] = []
    for item in available_actions:
        text = str(item or "").strip()
        if not text:
            continue
        if " — " in text:
            labels.append(text.split(" — ", 1)[1].strip())
        elif " - " in text:
            labels.append(text.split(" - ", 1)[1].strip())
        else:
            labels.append(humanize_catalog_action_key(text))
    return [label for label in labels if label]


def contains_raw_catalog_action_key(text: str) -> bool:
    return bool(RAW_CATALOG_ACTION_KEY.search(text or ""))


def scrub_raw_catalog_keys(text: str) -> str:
    """Replace dotted catalog keys with human labels (last-mile safety net)."""

    def _repl(match: re.Match[str]) -> str:
        return humanize_catalog_action_key(match.group(0))

    return RAW_CATALOG_ACTION_KEY.sub(_repl, text or "")


def dedupe_repeated_paragraphs(text: str) -> str:
    """Collapse exact duplicate paragraphs (model/stream glitch — STA-335)."""
    raw = (text or "").strip()
    if not raw:
        return raw
    if len(raw) >= 20:
        half = len(raw) // 2
        left = raw[:half].strip()
        right = raw[half:].strip()
        if left and left == right:
            return left
    blocks = [b.strip() for b in re.split(r"\n\s*\n", raw) if b.strip()]
    if len(blocks) <= 1:
        lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
        if len(lines) >= 2 and len(set(lines)) == 1:
            return lines[0]
        return raw
    deduped: list[str] = []
    for block in blocks:
        if deduped and deduped[-1] == block:
            continue
        deduped.append(block)
    return "\n\n".join(deduped)


def assert_no_raw_catalog_action_keys(text: str, *, context: str = "") -> None:
    if contains_raw_catalog_action_key(text):
        prefix = f"{context}: " if context else ""
        raise AssertionError(
            f"{prefix}user-facing copy must not contain raw catalog action keys "
            f"(pattern vendor.resource.verb)"
        )


def finalize_user_facing_message(text: str, *, context: str = "") -> str:
    cleaned = dedupe_repeated_paragraphs(scrub_raw_catalog_keys((text or "").strip()))
    assert_no_raw_catalog_action_keys(cleaned, context=context or "user_facing_message")
    return cleaned
