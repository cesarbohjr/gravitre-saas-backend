"""STA-314 — heuristic suggest-only recommendation cards.

Hard rules:
- Advisory only — never call ToolRegistry / execute_plan / invoke_tool.
- Cards may include navigation hrefs; they must not include invocation payloads,
  approval tokens, or executable callbacks.
"""
from __future__ import annotations

import logging
from typing import Any

from app.connectors.constants import is_connector_usable

logger = logging.getLogger(__name__)

# Explicit ban list — imported only for unit tests that assert absence.
_FORBIDDEN_IMPORT_NAMES = (
    "ToolRegistry",
    "execute_plan",
    "invoke_tool",
    "apply_integration_suggestion",
)

# Legacy department pack ids → marketplace asset slugs (seed_catalog.LEGACY_PACK_SLUG_MAP).
_LEGACY_PACK_TO_SLUG: dict[str, str] = {
    "sales-ops": "revenue-operations-pack",
    "marketing-ops": "marketing-operations-pack",
    "support-ops": "support-operations-pack",
    "finance-ops": "revenue-operations-pack",
}


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
        label = str(row.get("label") or row.get("display_name") or row.get("name") or vendor).strip() or vendor
        status = str(row.get("status") or row.get("auth_status") or "").strip().lower()
        executable = bool(row.get("executable", row.get("is_executable", True)))
        invocations = int(usage.get(vendor) or 0)

        if status in {"connected", "active", "ready", "ok", "syncing", "healthy"} or row.get("connected") is True:
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
                        confidence=0.9,  # confidence-honesty-ok: stamped by _card → label_confidence
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
                        confidence=0.75,  # confidence-honesty-ok: stamped by _card → label_confidence
                        priority=70,
                        href="/connectors",
                    )
                )
            else:
                missing_packs = [
                    pack_id
                    for pack_id in pack_map.get(vendor, [])
                    if not _pack_installed(pack_id, packs)
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
                            confidence=0.8,  # confidence-honesty-ok: stamped by _card → label_confidence
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


def _pack_installed(pack_id: str, installed: set[str]) -> bool:
    if pack_id in installed:
        return True
    slug = _LEGACY_PACK_TO_SLUG.get(pack_id)
    return bool(slug and slug in installed)


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
    from app.services.confidence_honesty import CONFIDENCE_SOURCE_HEURISTIC, label_confidence

    # Module C / STA-331: heuristic card scores are estimates (STA-286 pattern),
    # not live model intelligence, until Module A outcome volume seasons CF ranking.
    return {
        "id": card_id,
        "kind": kind,
        "title": title,
        "reason": reason,
        "evidence": evidence,
        **label_confidence(confidence, source=CONFIDENCE_SOURCE_HEURISTIC, is_estimate=True),
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


def filter_dismissed_recommendations(
    payload: dict[str, Any],
    dismissed_ids: set[str] | None,
) -> dict[str, Any]:
    """Drop cards the user dismissed (STA-123-style). Pure; no I/O."""
    dismissed = dismissed_ids or set()
    cards = [
        card
        for card in list(payload.get("recommendations") or [])
        if str(card.get("id") or "") not in dismissed
    ]
    return {
        **payload,
        "advisoryOnly": True,
        "actionsTaken": list(payload.get("actionsTaken") or []),
        "recommendations": cards,
        "count": len(cards),
    }


def load_connected_connectors(client: Any, org_id: str) -> list[dict[str, Any]]:
    """Load org connectors using real columns (id, name, type, vendor, status)."""
    try:
        result = (
            client.table("connectors")
            .select("id,name,type,vendor,status")
            .eq("org_id", org_id)
            .is_("deleted_at", "null")
            .execute()
        )
    except Exception as exc:
        logger.warning("heuristic connectors load failed org_id=%s err=%s", org_id, exc)
        return []

    connected: list[dict[str, Any]] = []
    for row in list(result.data or []):
        vendor = str(row.get("type") or row.get("vendor") or "").strip().lower()
        if not vendor:
            continue
        status = str(row.get("status") or "").strip().lower()
        label = str(row.get("name") or vendor).strip() or vendor
        executable = is_connector_usable(status)
        connected.append(
            {
                "id": row.get("id"),
                "vendor": vendor,
                "label": label,
                "status": status or "disconnected",
                "connected": True,
                "executable": executable,
            }
        )
    return connected


def load_usage_by_connector(client: Any, org_id: str, *, lookback_days: int = 30) -> dict[str, int]:
    """Aggregate tool.invoke* audit events via STA-123 fetch_tool_usage_events."""
    from app.services.integration_suggestion_service import (
        aggregate_tool_usage,
        fetch_tool_usage_events,
    )

    try:
        events = fetch_tool_usage_events(client, org_id, lookback_days=lookback_days)
        summary = aggregate_tool_usage(events)
    except Exception as exc:
        logger.warning("heuristic usage load failed org_id=%s err=%s", org_id, exc)
        return {}

    usage: dict[str, int] = {}
    for item in list(summary.get("connectors") or []):
        connector_type = str(item.get("connectorType") or "").strip().lower()
        if not connector_type:
            continue
        usage[connector_type] = int(item.get("totalInvocations") or 0)
    return usage


def load_installed_packs(client: Any, org_id: str) -> set[str]:
    """Union of marketplace_installs (department packs) + legacy org_department_pack_installs."""
    installed: set[str] = set()

    try:
        legacy = (
            client.table("org_department_pack_installs")
            .select("pack_id")
            .eq("org_id", org_id)
            .execute()
        )
        for row in list(legacy.data or []):
            pack_id = str(row.get("pack_id") or "").strip()
            if pack_id:
                installed.add(pack_id)
    except Exception as exc:
        logger.warning("heuristic legacy packs load failed org_id=%s err=%s", org_id, exc)

    try:
        installs = (
            client.table("marketplace_installs")
            .select("asset_id,installed_entity_type,metadata,status")
            .eq("org_id", org_id)
            .eq("status", "active")
            .execute()
        )
        asset_ids: list[str] = []
        for row in list(installs.data or []):
            entity_type = str(row.get("installed_entity_type") or "").strip().lower()
            meta = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
            for key in ("packId", "pack_id"):
                pack_ref = str(meta.get(key) or "").strip()
                if pack_ref:
                    installed.add(pack_ref)
            asset_id = str(row.get("asset_id") or "").strip()
            if asset_id and entity_type in {"department_pack", "intelligence_pack"}:
                asset_ids.append(asset_id)

        if asset_ids:
            assets = (
                client.table("marketplace_assets")
                .select("id,slug,asset_type")
                .in_("id", list(dict.fromkeys(asset_ids)))
                .execute()
            )
            for asset in list(assets.data or []):
                slug = str(asset.get("slug") or "").strip()
                if slug:
                    installed.add(slug)
                for pack_id, mapped_slug in _LEGACY_PACK_TO_SLUG.items():
                    if mapped_slug == slug:
                        installed.add(pack_id)
    except Exception as exc:
        logger.warning("heuristic marketplace packs load failed org_id=%s err=%s", org_id, exc)

    return installed


def load_heuristic_signals(
    client: Any,
    org_id: str,
    *,
    lookback_days: int = 30,
) -> dict[str, Any]:
    """Fetch all signal inputs for the pure builder (no tool execution)."""
    return {
        "connected_connectors": load_connected_connectors(client, org_id),
        "usage_by_connector": load_usage_by_connector(client, org_id, lookback_days=lookback_days),
        "installed_packs": load_installed_packs(client, org_id),
        "lookback_days": lookback_days,
    }


def load_dismissed_card_ids(client: Any, org_id: str, user_id: str) -> set[str]:
    """Load per-user dismissed heuristic card ids (STA-123 dismiss pattern)."""
    try:
        result = (
            client.table("heuristic_recommendation_dismissals")
            .select("card_id")
            .eq("org_id", org_id)
            .eq("user_id", user_id)
            .execute()
        )
    except Exception as exc:
        logger.warning(
            "heuristic dismissals load failed org_id=%s user_id=%s err=%s",
            org_id,
            user_id,
            exc,
        )
        return set()
    return {
        str(row.get("card_id") or "").strip()
        for row in list(result.data or [])
        if row.get("card_id")
    }


def dismiss_heuristic_card(
    client: Any,
    org_id: str,
    user_id: str,
    card_id: str,
) -> dict[str, Any]:
    """Persist a dismiss; idempotent upsert. Never executes tools."""
    card_id = str(card_id or "").strip()
    if not card_id:
        raise ValueError("card_id required")
    row = {
        "org_id": org_id,
        "user_id": user_id,
        "card_id": card_id,
    }
    client.table("heuristic_recommendation_dismissals").upsert(
        row,
        on_conflict="org_id,user_id,card_id",
    ).execute()
    return {"dismissed": True, "cardId": card_id, "advisoryOnly": True}
