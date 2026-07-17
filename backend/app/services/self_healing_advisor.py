"""Self-healing advisor — map tool/API failures to retry / backup / path switches.

Advisory only. Does not mutate workflow graphs or silently retry writes.
"""
from __future__ import annotations

import re
from typing import Any

_PERMISSION = re.compile(r"403|forbidden|permission|scope|unauthorized|401", re.I)
_TIMEOUT = re.compile(r"timeout|timed out|deadline|504|408", re.I)
_RATE = re.compile(r"429|rate.?limit|throttl", re.I)
_NOT_FOUND = re.compile(r"404|not found|missing", re.I)
_TRANSIENT = re.compile(r"500|502|503|econnreset|temporarily|unavailable", re.I)


def classify_failure(error: str | None, *, error_code: Any = None) -> str:
    text = f"{error_code or ''} {error or ''}".strip()
    if not text:
        return "unknown"
    if _PERMISSION.search(text):
        return "permission"
    if _TIMEOUT.search(text):
        return "timeout"
    if _RATE.search(text):
        return "rate_limit"
    if _NOT_FOUND.search(text):
        return "missing_data"
    if _TRANSIENT.search(text):
        return "transient"
    return "unknown"


_BACKUP_CONNECTORS: dict[str, tuple[str, ...]] = {
    "hubspot": ("salesforce", "pipedrive"),
    "salesforce": ("hubspot",),
    "slack": ("microsoft_teams", "gmail"),
    "gmail": ("outlook", "slack"),
    "zendesk": ("freshdesk", "gorgias"),
    "jira": ("asana", "linear"),
    "github": ("gitlab",),
}


def advise_self_heal(
    *,
    tool_results: list[dict[str, Any]] | None = None,
    connected_integrations: list[str] | None = None,
    action: str | None = None,
) -> dict[str, Any]:
    """Return non-destructive heal suggestions for failed tool calls."""
    connected = {c.lower() for c in (connected_integrations or [])}
    suggestions: list[dict[str, Any]] = []
    failures = [
        row
        for row in (tool_results or [])
        if isinstance(row, dict) and (row.get("success") is False or row.get("error"))
    ]
    if not failures:
        return {"hasFailures": False, "suggestions": [], "advisoryOnly": True}

    for row in failures[:8]:
        err = str(row.get("error") or (row.get("result") or {}).get("error") or "")
        code = row.get("error_code") or row.get("errorCode")
        kind = classify_failure(err, error_code=code)
        tool = str(row.get("tool") or row.get("action") or action or "tool")
        vendor = tool.split(".", 1)[0].lower() if "." in tool else tool.lower()

        suggestion: dict[str, Any] = {
            "tool": tool,
            "failureKind": kind,
            "advisoryOnly": True,
            "steps": [],
        }
        if kind == "transient" or kind == "timeout":
            suggestion["steps"].append({"type": "retry", "detail": "Retry once with backoff"})
        elif kind == "rate_limit":
            suggestion["steps"].append(
                {"type": "retry", "detail": "Wait and retry; reduce batch size if listing"}
            )
        elif kind == "permission":
            suggestion["steps"].append(
                {
                    "type": "reconnect",
                    "detail": f"Reconnect {vendor} and grant missing scopes",
                }
            )
        elif kind == "missing_data":
            suggestion["steps"].append(
                {"type": "switch_path", "detail": "Ask user for the missing id/url or search first"}
            )
        else:
            suggestion["steps"].append(
                {"type": "retry", "detail": "Retry once; if persists, surface error to user"}
            )

        backups = [
            b for b in _BACKUP_CONNECTORS.get(vendor, ()) if b in connected and b != vendor
        ]
        if backups and kind in {"permission", "transient", "unknown"}:
            suggestion["steps"].append(
                {
                    "type": "backup_connector",
                    "detail": f"Consider backup path via {backups[0]} (advisory)",
                    "connector": backups[0],
                }
            )
        suggestions.append(suggestion)

    return {
        "hasFailures": True,
        "suggestions": suggestions,
        "advisoryOnly": True,
        "summary": f"{len(suggestions)} failure(s) with heal suggestions",
    }
