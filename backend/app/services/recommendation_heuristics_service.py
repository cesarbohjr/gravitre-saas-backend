"""STA-314 — heuristic suggest-only recommendation cards.

Hard rules:
- Advisory only — never call ToolRegistry / execute_plan / invoke_tool.
- Cards may include navigation hrefs; they must not include invocation payloads,
  approval tokens, or executable callbacks.
"""
from __future__ import annotations

from typing import Any

# Explicit ban list — imported only for unit tests that assert absence.
_FORBIDDEN_IMPORT_NAMES = (
    "ToolRegistry",
    "execute_plan",
    "invoke_tool",
    "apply_integration_suggestion",
)


def build_heuristic_recommendations(
    *,
    connected_connectors: list[dict[str, Any]],
    usage_by_connector: dict[str, int] | None = None,
    installed_packs: set[str] | None = None,
    connector_to_packs: dict[str, list[str]] | None = None,
    lookback_days: int = 30,
) -> dict[str, Any]:
    """Pure heuristic builder. All inputs are pre-fetched; no I/O, no tool calls."""
    usage = usage_by_connector or {}
    packs = installed_packs or set()
    pack_map = connector_to_packs or {
        "hubspot": ["sales-ops", "marketing-ops"],
        "pipedrive": ["sales-ops"],
        "zendesk": ["support-ops"],
        "quickbooks": ["finance-ops"],
        "slack": ["support-ops"],
        "asana": ["ops"],
        "apollo": ["sales-ops"],
        "jira": ["ops"],
    }

    cards: list[dict[str, Any]] = []

    for row in connected_connectors:
        vendor = str(row.get("vendor") or row.get("connector_type") or "").strip().lower()
        if not vendor:
            continue
        label = str(row.get("label") or row.get("display_name") or vendor).strip() or vendor
        status = str(row.get("status") or row.get("auth_status") or "").strip().lower()
        executable = bool(row.get("executable", row.get("is_executable", True)))
        invocations = int(usage.get(vendor) or 0)

        if status in {"connected", "active", "ready", "ok"} or row.get("connected") is True:
            if not executable:
                cards.append(
                    _card(
                        card_id=f"nonexec-{vendor}",
                        kind="connector_non_executable",
                        title=f"{label} is connected but not executable",
                        reason=(
                            f"{label} appears connected yet cannot run actions. "
                            "Open Connectors to repair auth or permissions."
                        ),
                        evidence={
                            "vendor": vendor,
                            "status": status or "connected",
                            "executable": False,
                            "lookbackDays": lookback_days,
                        },
                        confidence=0.9,
                        priority=95,
                        href="/connectors",
                    )
                )
            elif invocations <= 0:
                cards.append(
                    _card(
                        card_id=f"unused-{vendor}",
                        kind="connector_connected_unused",
                        title=f"{label} is connected but unused",
                        reason=(
                            f"{label} is connected with no tool usage in the last "
                            f"{lookback_days} days. Try it from chat or a workflow."
                        ),
                        evidence={
                            "vendor": vendor,
                            "invocations": 0,
                            "lookbackDays": lookback_days,
                        },
                        confidence=0.75,
                        priority=70,
                        href="/connectors",
                    )
                )
            else:
                missing_packs = [
                    pack_id
                    for pack_id in pack_map.get(vendor, [])
                    if pack_id not in packs
                ]
                if missing_packs:
                    pack_id = missing_packs[0]
                    cards.append(
                        _card(
                            card_id=f"pack-{vendor}-{pack_id}",
                            kind="connector_missing_pack",
                            title=f"Add a pack for {label}",
                            reason=(
                                f"{label} has recent usage ({invocations} invocations) but "
                                f"pack '{pack_id}' is not installed."
                            ),
                            evidence={
                                "vendor": vendor,
                                "invocations": invocations,
                                "suggestedPackId": pack_id,
                                "lookbackDays": lookback_days,
                            },
                            confidence=0.8,
                            priority=80,
                            href="/marketplace",
                        )
                    )

    cards.sort(key=lambda item: int(item.get("priority") or 0), reverse=True)
    return {
        "advisoryOnly": True,
        "actionsTaken": [],
        "recommendations": cards,
        "count": len(cards),
    }


def _card(
    *,
    card_id: str,
    kind: str,
    title: str,
    reason: str,
    evidence: dict[str, Any],
    confidence: float,
    priority: int,
    href: str,
) -> dict[str, Any]:
    return {
        "id": card_id,
        "kind": kind,
        "title": title,
        "reason": reason,
        "evidence": evidence,
        "confidence": confidence,
        "priority": priority,
        "advisoryOnly": True,
        "href": href,
        # Explicitly absent: toolName, arguments, approvalId, executeUrl
    }


def assert_no_execute_surface(payload: dict[str, Any]) -> None:
    """Raise AssertionError if payload looks like an executable action envelope."""
    banned_keys = {
        "toolName",
        "tool_name",
        "arguments",
        "approvalId",
        "approval_id",
        "executeUrl",
        "execute_url",
        "invoke_tool",
        "clientSecret",
    }
    stack: list[Any] = [payload]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            for key, value in node.items():
                if key in banned_keys:
                    raise AssertionError(f"executable surface key present: {key}")
                if key in _FORBIDDEN_IMPORT_NAMES:
                    raise AssertionError(f"forbidden name in payload: {key}")
                stack.append(value)
        elif isinstance(node, list):
            stack.extend(node)
