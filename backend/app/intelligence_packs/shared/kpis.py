"""Phase 3.5 — shared intelligence-pack KPI summary (org-scoped)."""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Vendors that feed Phase 1.5 shared tables for each pack.
PACK_VENDOR_MAP: dict[str, tuple[str, ...]] = {
    "executive-intelligence-pack": ("fred", "sec_edgar", "world_bank", "oecd"),
    "msp-intelligence-pack": ("nvd", "cisa_kev"),
    "sales-intelligence-pack": (),  # CRM-backed; no gravitree shared vendors yet
    "customer-success-intelligence-pack": (),  # CRM/support-backed; no gravitree shared vendors
    "marketing-intelligence-pack": (),
    "support-intelligence-pack": (),
}


def pack_kpi_summary(client: Any, *, org_id: str, pack_id: str) -> dict[str, Any]:
    """Aggregate install + Phase 1.5 ingestion KPIs for one intelligence pack."""
    pid = (pack_id or "").strip()
    vendors = list(PACK_VENDOR_MAP.get(pid, ()))

    installed = False
    install_id: str | None = None
    agent_count = 0
    workflow_count = 0
    asset_id: str | None = None

    try:
        assets = (
            client.table("marketplace_assets")
            .select("id,slug,asset_type")
            .eq("slug", pid)
            .limit(1)
            .execute()
        )
        asset_rows = assets.data or []
        if asset_rows:
            asset_id = str(asset_rows[0]["id"])
            installs = (
                client.table("marketplace_installs")
                .select("id,status,metadata")
                .eq("org_id", org_id)
                .eq("asset_id", asset_id)
                .eq("status", "active")
                .limit(5)
                .execute()
            )
            for row in installs.data or []:
                installed = True
                install_id = str(row.get("id") or install_id or "")
                meta = row.get("metadata") or {}
                agent_ids = meta.get("agentIds") or meta.get("agent_ids") or []
                workflow_ids = meta.get("workflowIds") or meta.get("workflow_ids") or []
                if isinstance(agent_ids, list):
                    agent_count = max(agent_count, len(agent_ids))
                if isinstance(workflow_ids, list):
                    workflow_count = max(workflow_count, len(workflow_ids))
                # Demo bundles also store singular keys
                if meta.get("agentId") or meta.get("agent_id"):
                    agent_count = max(agent_count, 1)
                if meta.get("workflowId") or meta.get("workflow_id"):
                    workflow_count = max(workflow_count, 1)
    except Exception as exc:  # noqa: BLE001
        logger.debug("pack_kpi_install_lookup_skipped pack=%s err=%s", pid, exc)

    signals_count = _count_table(
        client,
        "external_signals",
        org_id=org_id,
        vendors=vendors,
    )
    entities_count = _count_table(
        client,
        "external_entities",
        org_id=org_id,
        vendors=vendors,
    )
    cache_touches = _count_entities_with_cache(client, org_id=org_id, vendors=vendors)
    assignments_count = _count_assignments(client, org_id=org_id, pack_id=pid)

    by_vendor: dict[str, dict[str, int]] = {}
    for vendor in vendors:
        by_vendor[vendor] = {
            "signals": _count_table(client, "external_signals", org_id=org_id, vendors=[vendor]),
            "entities": _count_table(client, "external_entities", org_id=org_id, vendors=[vendor]),
        }

    return {
        "packId": pid,
        "installed": installed,
        "installId": install_id,
        "assetId": asset_id,
        "agentCount": agent_count,
        "workflowCount": workflow_count,
        "signalsCount": signals_count,
        "entitiesCount": entities_count,
        "cacheTouches": cache_touches,
        "assignmentsCount": assignments_count,
        "vendors": by_vendor,
    }


def _count_table(
    client: Any,
    table: str,
    *,
    org_id: str,
    vendors: list[str] | tuple[str, ...],
) -> int:
    if not vendors:
        return 0
    try:
        q = client.table(table).select("id", count="exact").eq("org_id", org_id)
        if len(vendors) == 1:
            q = q.eq("vendor", vendors[0])
        else:
            q = q.in_("vendor", list(vendors))
        result = q.limit(1).execute()
        return int(getattr(result, "count", None) or 0)
    except Exception as exc:  # noqa: BLE001
        logger.debug("pack_kpi_count_skipped table=%s err=%s", table, exc)
        return 0


def _count_entities_with_cache(
    client: Any,
    *,
    org_id: str,
    vendors: list[str] | tuple[str, ...],
) -> int:
    if not vendors:
        return 0
    try:
        q = (
            client.table("external_entities")
            .select("id", count="exact")
            .eq("org_id", org_id)
            .not_.is_("source_cache_id", "null")
        )
        if len(vendors) == 1:
            q = q.eq("vendor", vendors[0])
        else:
            q = q.in_("vendor", list(vendors))
        result = q.limit(1).execute()
        return int(getattr(result, "count", None) or 0)
    except Exception as exc:  # noqa: BLE001
        logger.debug("pack_kpi_cache_touches_skipped err=%s", exc)
        return 0


def _count_assignments(client: Any, *, org_id: str, pack_id: str) -> int:
    try:
        result = (
            client.table("agent_knowledge_assignments")
            .select("id", count="exact")
            .eq("org_id", org_id)
            .contains("metadata", {"intelligence_pack_id": pack_id})
            .limit(1)
            .execute()
        )
        return int(getattr(result, "count", None) or 0)
    except Exception as exc:  # noqa: BLE001
        logger.debug("pack_kpi_assignments_skipped err=%s", exc)
        return 0
