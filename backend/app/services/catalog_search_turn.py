"""3.0-E deterministic catalog search — eligible ActionSpecs, not an LLM dump."""
from __future__ import annotations

import re
from typing import Any

from app.services.jit_tool_discovery import (
    HARD_CAP_ELIGIBLE,
    MAX_ELIGIBLE_TOOLS,
    search_eligible_action_specs,
)

_CATALOG_INTENT = re.compile(
    r"(?is)\b("
    r"search(?:ing)? (?:the )?(?:tool )?catalog"
    r"|tool catalog"
    r"|action schema"
    r"|which (?:connected )?(?:tools|actions)"
    r"|what (?:tools|actions) (?:can|do) i"
    r")\b"
)


def match_catalog_search_intent(message: str) -> bool:
    return bool(_CATALOG_INTENT.search(message or ""))


_READ_ONLY = re.compile(r"(?is)\bread[- ]only\b|do not create")
_CAPABILITIES = re.compile(r"(?is)\b(which (?:connected )?(?:tools|actions)|what (?:tools|actions) (?:can|do) i)\b")


def try_catalog_search_turn(
    *,
    message: str,
    connected_integrations: list[str] | None,
    capability_id: str | None = None,
) -> dict[str, Any] | None:
    if not match_catalog_search_intent(message or ""):
        return None
    connected = [str(v).strip().lower() for v in (connected_integrations or []) if str(v).strip()]
    include_writes = bool(_CAPABILITIES.search(message or "")) and not bool(_READ_ONLY.search(message or ""))
    found = search_eligible_action_specs(
        query=message or "",
        capability_id=capability_id,
        connected=connected,
        include_writes=include_writes,
        max_results=MAX_ELIGIBLE_TOOLS,
    )
    if len(found) > HARD_CAP_ELIGIBLE:
        found = found[:HARD_CAP_ELIGIBLE]
    names = [row.action_id for row in found]
    mentioned_github = bool(re.search(r"\bgithub\b", message or "", re.I))
    github_excluded = mentioned_github and "github" not in set(connected)
    lines = []
    writes = 0
    for row in found[:16]:
        label = str(row.name or "").strip() or row.action_id
        if row.governed_write:
            writes += 1
            gate = "WRITE, approval required — not executed"
        elif row.f1_read:
            gate = "READ, connected"
        else:
            gate = f"{row.kind} READ, connected"
        lines.append(f"- {label} ({row.vendor}; {gate})")
    intro = (
        "Here are connected actions that match that search. This is a catalog lookup, not a live provider run."
        if include_writes
        else "Here are connected READ actions that match that search. This is a catalog lookup, not a live provider run."
    )
    if writes:
        intro += " WRITE capabilities are listed only as discoverable; they still require the canonical approval path and were not started."
    body_bits = [
        intro,
        "\n".join(lines) if lines else "No eligible connected actions matched.",
        f"I found {len(found)} eligible action{'s' if len(found) != 1 else ''} (cap {HARD_CAP_ELIGIBLE}).",
    ]
    if github_excluded:
        body_bits.append("GitHub is not connected on this org, so GitHub issue tools are not eligible.")
    body = "\n\n".join(body_bits)
    return {
        "stop_pipeline": True,
        "dialogue_mode": "answer",
        "message": body,
        "workflow_status": "completed",
        "execution_path": "catalog_search_eligible",
        "eligible_action_ids": names,
        "eligible_count": len(found),
        "hard_cap": HARD_CAP_ELIGIBLE,
        "github_excluded": github_excluded,
        "writes_started": False,
        "writes_listed": writes,
        "include_writes": include_writes,
    }
