"""What disconnecting a connector removes, and what it has removed so far.

The disconnect dialog and the Connectors page read this so their copy follows the
switches that actually run (relay, dry run, memory lineage, provider revoke)
instead of promising a deletion that is off or in test mode. Read-only.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app.connectors.provider_revoke import SUPPORTED_VENDORS
from app.core.logging import get_logger
from app.services.memory_source_liveness import liveness_enabled

logger = get_logger(__name__)

RECENT_DAYS = 90
MAX_REMOVALS = 50


def removal_policy(settings: Any) -> dict[str, Any]:
    """The disconnect behaviour the current switches produce."""
    relay = getattr(settings, "domain_event_relay_enabled", False) is True
    # Same convention as the purge: anything but an explicit False keeps it a plan.
    dry_run = getattr(settings, "source_purge_dry_run", True) is not False
    if not relay:
        mode = "off"
    elif dry_run:
        mode = "test"
    else:
        mode = "on"
    lineage = liveness_enabled(settings)
    return {
        # off: nothing is removed yet; test: a receipt lists what would be removed; on: removed.
        "dataRemoval": mode,
        # Memories and customer observations learned from the source stop being read at once,
        # and are part of the purge.
        "memoriesIncluded": lineage,
        "providerRevokeEnabled": getattr(settings, "connector_provider_revoke_on_disconnect", False) is True,
        "providerRevokeVendors": sorted(SUPPORTED_VENDORS),
        "deletionPropagationEnabled": getattr(settings, "source_deletion_propagation_enabled", False) is True,
    }


def _status(receipt: dict[str, Any] | None, mode: str) -> str:
    if receipt is None:
        return "queued" if mode != "off" else "not_started"
    return "planned" if receipt.get("dry_run") is not False else "removed"


def list_removals(client: Any, org_id: str, mode: str, *, now: datetime | None = None) -> list[dict[str, Any]]:
    """Connectors disconnected in the last RECENT_DAYS, each with its latest receipt."""
    since = ((now or datetime.now(timezone.utc)) - timedelta(days=RECENT_DAYS)).isoformat()
    res = (
        client.table("connectors")
        .select("id, name, vendor, type, deleted_at")
        .eq("org_id", org_id)
        .gte("deleted_at", since)
        .order("deleted_at", desc=True)
        .limit(MAX_REMOVALS)
        .execute()
    )
    connectors = [r for r in (res.data or []) if r.get("deleted_at")]
    if not connectors:
        return []
    ids = [str(r["id"]) for r in connectors]
    receipts: dict[str, dict[str, Any]] = {}
    try:
        rec = (
            client.table("source_purge_receipts")
            .select("connector_id, vendor, disconnected_at, dry_run, counts, created_at")
            .eq("org_id", org_id)
            .in_("connector_id", ids)
            .order("created_at", desc=True)
            .execute()
        )
        for r in rec.data or []:
            # Newest first; a live receipt outranks a dry-run plan for the same disconnect.
            cid = str(r.get("connector_id"))
            held = receipts.get(cid)
            if held is None or (held.get("dry_run") is not False and r.get("dry_run") is False):
                receipts[cid] = r
    except Exception as exc:  # noqa: BLE001
        # Receipts table missing in an environment: show the disconnects without receipts.
        logger.warning("data_removal_receipts_unavailable org_id=%s error=%s", org_id, type(exc).__name__)
    out: list[dict[str, Any]] = []
    for c in connectors:
        receipt = receipts.get(str(c["id"]))
        counts = receipt.get("counts") if receipt and isinstance(receipt.get("counts"), dict) else {}
        out.append(
            {
                "connectorId": str(c["id"]),
                "name": c.get("name") or c.get("vendor") or c.get("type") or "Connector",
                "vendor": c.get("vendor") or c.get("type") or "",
                "disconnectedAt": c.get("deleted_at"),
                "status": _status(receipt, mode),
                "receiptAt": receipt.get("created_at") if receipt else None,
                "counts": counts,
            }
        )
    return out
