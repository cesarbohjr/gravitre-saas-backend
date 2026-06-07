"""Enterprise compliance helpers — PII redaction and SOC2 evidence export (STA-81 / STA-82)."""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Any

EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
CARD_RE = re.compile(r"\b(?:\d[ -]*?){13,19}\b")
PHONE_RE = re.compile(r"\b\+?\d[\d\s().-]{7,}\d\b")


def _hash_value(value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return f"sha256:{digest[:16]}"


def redact_text(value: str, *, mode: str = "standard") -> str:
    """Redact common PII patterns from free text."""
    if not value:
        return value
    text = value
    if mode == "strict":
        text = EMAIL_RE.sub(lambda m: _hash_value(m.group(0)), text)
        text = SSN_RE.sub("[REDACTED_SSN]", text)
        text = CARD_RE.sub("[REDACTED_CARD]", text)
        text = PHONE_RE.sub("[REDACTED_PHONE]", text)
        return text
    text = EMAIL_RE.sub("[REDACTED_EMAIL]", text)
    text = SSN_RE.sub("[REDACTED_SSN]", text)
    text = CARD_RE.sub("[REDACTED_CARD]", text)
    return text


def redact_metadata(metadata: dict[str, Any] | None, *, mode: str = "standard") -> dict[str, Any]:
    if not metadata:
        return {}
    redacted: dict[str, Any] = {}
    for key, value in metadata.items():
        if isinstance(value, str):
            redacted[key] = redact_text(value, mode=mode)
        elif isinstance(value, dict):
            redacted[key] = redact_metadata(value, mode=mode)
        elif isinstance(value, list):
            redacted[key] = [
                redact_metadata(item, mode=mode) if isinstance(item, dict) else redact_text(str(item), mode=mode)
                if isinstance(item, str)
                else item
                for item in value
            ]
        else:
            redacted[key] = value
    return redacted


def build_soc2_evidence_bundle(
    *,
    org_id: str,
    audit_logs: list[dict[str, Any]],
    tool_events: list[dict[str, Any]],
    connector_events: list[dict[str, Any]],
    admin_events: list[dict[str, Any]],
    from_ts: str | None = None,
    to_ts: str | None = None,
    pii_mode: str = "strict",
) -> dict[str, Any]:
    """Assemble exportable SOC2 evidence bundle with redacted metadata."""
    return {
        "orgId": org_id,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "window": {"from": from_ts, "to": to_ts},
        "controls": {
            "toolInvocations": [redact_metadata(row, mode=pii_mode) for row in tool_events],
            "connectorChanges": [redact_metadata(row, mode=pii_mode) for row in connector_events],
            "adminActions": [redact_metadata(row, mode=pii_mode) for row in admin_events],
            "auditLogs": [redact_metadata(row, mode=pii_mode) for row in audit_logs],
        },
        "summary": {
            "toolInvocationCount": len(tool_events),
            "connectorChangeCount": len(connector_events),
            "adminActionCount": len(admin_events),
            "auditLogCount": len(audit_logs),
        },
    }
