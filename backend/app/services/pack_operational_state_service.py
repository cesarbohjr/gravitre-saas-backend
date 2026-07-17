"""Intelligence pack operational state — living KPI + signal context (Tier 3)."""
from __future__ import annotations

import json
from typing import Any

from app.core.logging import get_logger
from app.intelligence_packs.shared.kpis import PACK_VENDOR_MAP, pack_kpi_summary

logger = get_logger(__name__)

_MAX_PACKS = 3
_MAX_SIGNALS = 5
_MAX_CACHE_ROWS = 3


def extract_pack_ids(knowledge_assignments: list[dict[str, Any]] | None) -> list[str]:
    """Collect unique intelligence pack ids from agent knowledge assignments."""
    seen: set[str] = set()
    ordered: list[str] = []
    for row in knowledge_assignments or []:
        if not isinstance(row, dict):
            continue
        meta = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        pack_id = str(meta.get("intelligence_pack_id") or meta.get("intelligencePackId") or "").strip()
        if pack_id and pack_id not in seen:
            seen.add(pack_id)
            ordered.append(pack_id)
    return ordered[:_MAX_PACKS]


def _recent_signals(client: Any, *, org_id: str, vendors: tuple[str, ...]) -> list[dict[str, Any]]:
    if not vendors:
        return []
    try:
        query = (
            client.table("external_signals")
            .select("id, vendor, title, summary, signal_type, observed_at")
            .eq("org_id", org_id)
            .order("observed_at", desc=True)
            .limit(_MAX_SIGNALS)
        )
        if len(vendors) == 1:
            query = query.eq("vendor", vendors[0])
        else:
            query = query.in_("vendor", list(vendors))
        result = query.execute()
        return [row for row in (result.data or []) if isinstance(row, dict)]
    except Exception as exc:  # noqa: BLE001
        logger.debug("pack_state_signals_skipped org_id=%s err=%s", org_id, exc)
        return []


def _recent_cache_rows(client: Any, *, vendors: tuple[str, ...]) -> list[dict[str, Any]]:
    if not vendors:
        return []
    try:
        query = (
            client.table("knowledge_pack_cache")
            .select("id, vendor, cache_key, expires_at")
            .order("expires_at", desc=True)
            .limit(_MAX_CACHE_ROWS)
        )
        if len(vendors) == 1:
            query = query.eq("vendor", vendors[0])
        else:
            query = query.in_("vendor", list(vendors))
        result = query.execute()
        return [row for row in (result.data or []) if isinstance(row, dict)]
    except Exception as exc:  # noqa: BLE001
        logger.debug("pack_state_cache_skipped err=%s", exc)
        return []


def build_pack_operational_section(
    client: Any,
    *,
    org_id: str,
    knowledge_assignments: list[dict[str, Any]] | None,
) -> str:
    """Assemble markdown operational state for installed intelligence packs."""
    pack_ids = extract_pack_ids(knowledge_assignments)
    if not pack_ids:
        return ""

    sections: list[str] = []
    for pack_id in pack_ids:
        try:
            kpis = pack_kpi_summary(client, org_id=org_id, pack_id=pack_id)
        except Exception as exc:  # noqa: BLE001
            logger.debug("pack_kpi_summary_skipped pack=%s err=%s", pack_id, exc)
            kpis = {"packId": pack_id, "installed": False}

        vendors = tuple(PACK_VENDOR_MAP.get(pack_id, ()))
        signals = _recent_signals(client, org_id=org_id, vendors=vendors)
        cache_rows = _recent_cache_rows(client, vendors=vendors)

        lines = [
            f"### {pack_id}",
            f"- installed: {bool(kpis.get('installed'))}",
            f"- signals: {kpis.get('signalsCount', 0)} | entities: {kpis.get('entitiesCount', 0)}",
            f"- agents: {kpis.get('agentCount', 0)} | workflows: {kpis.get('workflowCount', 0)}",
        ]
        platform_health = kpis.get("platformHealth")
        if isinstance(platform_health, dict):
            lines.append(
                "- platform health: "
                f"score={platform_health.get('overallScore')} "
                f"grade={platform_health.get('grade')} "
                f"pending_approvals={platform_health.get('pendingApprovals')}"
            )
        if signals:
            lines.append("- recent signals:")
            for signal in signals:
                title = str(signal.get("title") or signal.get("summary") or "Signal")[:120]
                vendor = str(signal.get("vendor") or "")
                lines.append(f"  - [{vendor}] {title}")
        if cache_rows:
            lines.append("- cache snapshots:")
            for row in cache_rows:
                lines.append(
                    f"  - {row.get('vendor')}:{row.get('cache_key')} (expires {row.get('expires_at')})"
                )
        sections.append("\n".join(lines))

    if not sections:
        return ""
    return "<pack_operational_state>\n" + "\n\n".join(sections) + "\n</pack_operational_state>"


def build_pack_operational_dict(
    client: Any,
    *,
    org_id: str,
    knowledge_assignments: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    """Structured operational snapshot for explainability and tests."""
    pack_ids = extract_pack_ids(knowledge_assignments)
    packs: list[dict[str, Any]] = []
    for pack_id in pack_ids:
        try:
            summary = pack_kpi_summary(client, org_id=org_id, pack_id=pack_id)
        except Exception as exc:  # noqa: BLE001
            summary = {"packId": pack_id, "error": str(exc)}
        packs.append(summary)
    return {"packIds": pack_ids, "packs": packs}


def pack_state_prompt_preview(section: str, *, max_chars: int = 4000) -> str:
    text = (section or "").strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 20] + "\n… [truncated]"


def pack_state_json(section: str) -> str:
    return json.dumps({"sectionLength": len(section or ""), "hasContent": bool(section)})
