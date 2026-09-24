"""Guardrails: user-facing copy must never expose raw connector catalog action keys."""
from __future__ import annotations

import re
from typing import Iterable

# Internal ids like gmail.messages.list (at least vendor.resource.verb — two dots).
RAW_CATALOG_ACTION_KEY = re.compile(
    r"\b[a-z][a-z0-9_]*(?:\.[a-z0-9_]+){2,}\b",
    re.IGNORECASE,
)

_INTERNAL_TOOL_NAME = re.compile(
    r"\b(?:assistant_[a-z0-9_]+|getConnectorStatus|tool_call|function\s+schema)\b",
    re.IGNORECASE,
)


_EMAIL_RE = re.compile(r"[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}", re.I)
_HOST_TLD = frozenset({"app", "com", "io", "net", "org", "co", "ai", "dev", "example", "local"})


def _catalog_key_match_is_identity(text: str, match: re.Match[str]) -> bool:
    """Emails and hostnames must stay exact — they are not catalog action keys."""
    start, end = match.span()
    if start > 0 and text[start - 1] == "@":
        return True
    for email in _EMAIL_RE.finditer(text or ""):
        if email.start() <= start < email.end():
            return True
    last = match.group(0).rsplit(".", 1)[-1].lower()
    return last in _HOST_TLD


def _catalog_key_match_inside_url(text: str, start: int) -> bool:
    """True when a dotted-token match is part of an http(s) URL host (e.g. app.apollo.io)."""
    window = (text or "")[max(0, start - 12) : start]
    return "://" in window


def _iter_catalog_action_key_matches(text: str):
    for match in RAW_CATALOG_ACTION_KEY.finditer(text or ""):
        if _catalog_key_match_inside_url(text, match.start()):
            continue
        if _catalog_key_match_is_identity(text, match):
            continue
        yield match


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
            # Prefer the short catalog name. The auto-generated description
            # ("Create list via hubspot API. Use when you need to…") was leaking
            # into validation-error suffixes and reading like a missing schema.
            name = str(getattr(spec, "name", "") or "").strip()
            if name:
                return name
            description = str(getattr(spec, "description", "") or "").strip()
            if description:
                return description.split(".")[0].strip() or description
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
    return any(True for _ in _iter_catalog_action_key_matches(text))


def scrub_raw_catalog_keys(text: str) -> str:
    """Replace dotted catalog keys with human labels (last-mile safety net)."""
    raw = text or ""

    def _repl(match: re.Match[str]) -> str:
        if _catalog_key_match_inside_url(raw, match.start()):
            return match.group(0)
        if _catalog_key_match_is_identity(raw, match):
            return match.group(0)
        return humanize_catalog_action_key(match.group(0))

    return RAW_CATALOG_ACTION_KEY.sub(_repl, raw)


def scrub_internal_tool_references(text: str) -> str:
    """Remove internal assistant tool identifiers from user-visible copy."""
    cleaned = _INTERNAL_TOOL_NAME.sub("", text or "")
    return re.sub(r"\s{2,}", " ", cleaned).strip()


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


def restore_identity_literals(text: str, literals: Iterable[str] | None) -> str:
    """Put frozen emails/names back if composition or TTS-prep mangled them."""
    out = text or ""
    for raw in literals or []:
        lit = str(raw or "").strip()
        if not lit or lit in out:
            continue
        if "@" in lit:
            local = lit.split("@", 1)[0]
            mangled = re.compile(re.escape(local) + r"@app in [A-Za-z]+", re.I)
            if mangled.search(out):
                out = mangled.sub(lit, out)
    return out


def finalize_user_facing_message(
    text: str,
    *,
    context: str = "",
    identity_literals: Iterable[str] | None = None,
) -> str:
    cleaned = restore_identity_literals((text or "").strip(), identity_literals)
    cleaned = dedupe_repeated_paragraphs(
        scrub_internal_tool_references(scrub_raw_catalog_keys(cleaned))
    )
    cleaned = restore_identity_literals(cleaned, identity_literals)
    assert_no_raw_catalog_action_keys(cleaned, context=context or "user_facing_message")
    return cleaned
