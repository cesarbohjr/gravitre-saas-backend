"""Per-org storage meter, daily snapshots and the plan storage quota.

The meter (STORAGE_METER_ENABLED, default off) calls compute_org_storage_usage once a
day and upserts one org_storage_usage_snapshots row per org. Sizes are approximate by
design: each table's total size (heap, TOAST and indexes, so embeddings and their
vector indexes count) is split between orgs by their share of its rows; files are the
exact object sizes in Supabase Storage. Files an org keeps in its own bucket
(bring-your-own storage) are not on our bill and are not counted.

The quota (STORAGE_QUOTA_ENFORCEMENT_ENABLED, default off) compares the latest
snapshot with the plan's ``storage_bytes`` limit: 80% and above is a warning, 100%
and above refuses *new* connector syncs and uploads with HTTP 402
STORAGE_QUOTA_EXCEEDED. Nothing is ever deleted. Without a snapshot from the last
three days the quota does not act (unknown is never a block). Needs migration
20261020081535_storage_retention_metering.sql (and its parts).
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from app.core.logging import get_logger
from app.services.ingestion_interlock import IngestionHeldError

logger = get_logger(__name__)

CATEGORIES: tuple[str, ...] = ("knowledge", "memories", "conversations", "audit", "files")
WARN_RATIO = 0.8
SNAPSHOT_MAX_AGE = timedelta(days=3)
SNAPSHOT_KEEP_DAYS = 400
_UPSERT_CHUNK = 200


class StorageQuotaExceededError(IngestionHeldError):
    """The org is at or over its plan storage limit; new syncs/uploads are refused (402).

    A subclass of IngestionHeldError so every sync path that already lets the
    interlock's refusal through does the same for this one; its own handler answers
    402 STORAGE_QUOTA_EXCEEDED instead of 503.
    """

    def __init__(self, message: str, *, used_bytes: int, limit_bytes: int) -> None:
        super().__init__(message)
        self.used_bytes = used_bytes
        self.limit_bytes = limit_bytes


def aggregate_usage(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """compute_org_storage_usage rows -> {org_id: {totalBytes, categories{cat: {bytes, rows}}}}."""
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        org_id = str(row.get("org_id") or "")
        category = str(row.get("category") or "")
        if not org_id or category not in CATEGORIES:
            continue
        doc = out.setdefault(
            org_id, {"totalBytes": 0, "categories": {c: {"bytes": 0, "rows": 0} for c in CATEGORIES}}
        )
        size = max(0, int(row.get("bytes") or 0))
        doc["categories"][category]["bytes"] += size
        doc["categories"][category]["rows"] += max(0, int(row.get("row_count") or 0))
        doc["totalBytes"] += size
    return out


def write_storage_snapshots(client: Any, *, now: datetime | None = None) -> int:
    """Compute usage for every org and upsert today's snapshot. Returns orgs written."""
    now = now or datetime.now(UTC)
    res = client.rpc("compute_org_storage_usage", {"p_org_id": None}).execute()
    usage = aggregate_usage([r for r in (res.data or []) if isinstance(r, dict)])
    day = now.date().isoformat()
    rows = [
        {
            "org_id": org_id,
            "snapshot_date": day,
            "captured_at": now.isoformat(),
            "total_bytes": doc["totalBytes"],
            "categories": doc["categories"],
        }
        for org_id, doc in sorted(usage.items())
    ]
    for start in range(0, len(rows), _UPSERT_CHUNK):
        client.table("org_storage_usage_snapshots").upsert(
            rows[start : start + _UPSERT_CHUNK], on_conflict="org_id,snapshot_date"
        ).execute()
    keep_from = (now - timedelta(days=SNAPSHOT_KEEP_DAYS)).date().isoformat()
    client.table("org_storage_usage_snapshots").delete().lt("snapshot_date", keep_from).execute()
    logger.info("storage_meter_snapshots orgs=%s bytes=%s", len(rows), sum(r["total_bytes"] for r in rows))
    return len(rows)


def latest_snapshot(client: Any, org_id: str) -> dict[str, Any] | None:
    res = (
        client.table("org_storage_usage_snapshots")
        .select("snapshot_date, captured_at, total_bytes, categories, method")
        .eq("org_id", org_id)
        .order("captured_at", desc=True)
        .limit(1)
        .execute()
    )
    rows = res.data or []
    return dict(rows[0]) if rows else None


def storage_limit_bytes(entitlements: dict[str, Any] | None) -> int | None:
    limits = (entitlements or {}).get("limits") or {}
    value = limits.get("storage_bytes")
    return None if value is None else int(value)


def quota_state(used: int | None, limit: int | None) -> tuple[str, float | None]:
    """('unknown'|'unlimited'|'ok'|'warn'|'over', ratio)."""
    if used is None:
        return "unknown", None
    if limit is None or limit <= 0:
        return "unlimited", None
    ratio = used / limit
    if ratio >= 1:
        return "over", ratio
    if ratio >= WARN_RATIO:
        return "warn", ratio
    return "ok", ratio


def _fresh(snapshot: dict[str, Any] | None, now: datetime) -> bool:
    if not snapshot:
        return False
    raw = str(snapshot.get("captured_at") or "")
    try:
        captured = datetime.fromisoformat(raw)
    except ValueError:
        return False
    if captured.tzinfo is None:
        captured = captured.replace(tzinfo=UTC)
    return now - captured <= SNAPSHOT_MAX_AGE


def storage_usage_view(
    client: Any, settings: Any, org_id: str, entitlements: dict[str, Any] | None
) -> dict[str, Any]:
    """Payload of GET /api/settings/storage/usage."""
    meter_on = getattr(settings, "storage_meter_enabled", False) is True
    enforcement_on = getattr(settings, "storage_quota_enforcement_enabled", False) is True
    limit = storage_limit_bytes(entitlements)
    view: dict[str, Any] = {
        "meterEnabled": meter_on,
        "enforcementEnabled": enforcement_on,
        "limitBytes": limit,
        "warnRatio": WARN_RATIO,
        "snapshot": None,
        "state": "unknown",
        "percentUsed": None,
        "categories": list(CATEGORIES),
    }
    if not meter_on:
        return view
    try:
        snap = latest_snapshot(client, org_id)
    except Exception as exc:  # noqa: BLE001 - migration not applied yet, or a read error
        logger.warning("storage_usage_read_failed org_id=%s error=%s", org_id, type(exc).__name__)
        snap = None
    if snap:
        used = int(snap.get("total_bytes") or 0)
        state, ratio = quota_state(used, limit)
        view.update(
            {
                "snapshot": {
                    "capturedAt": snap.get("captured_at"),
                    "snapshotDate": snap.get("snapshot_date"),
                    "totalBytes": used,
                    "categories": snap.get("categories") or {},
                    "method": snap.get("method"),
                },
                "state": state,
                "percentUsed": None if ratio is None else round(ratio * 100, 1),
            }
        )
    return view


def storage_quota_block_reason(
    client: Any, settings: Any, org_id: str, *, now: datetime | None = None
) -> StorageQuotaExceededError | None:
    """The refusal for a new sync/upload, or None to proceed. Never blocks on errors."""
    if getattr(settings, "storage_quota_enforcement_enabled", False) is not True:
        return None
    now = now or datetime.now(UTC)
    try:
        snap = latest_snapshot(client, org_id)
        if not _fresh(snap, now):
            return None
        from app.middleware.entitlements import resolve_entitlements

        limit = storage_limit_bytes(resolve_entitlements(settings, org_id))
    except Exception as exc:  # noqa: BLE001 - the quota fails open; it only ever refuses on evidence
        logger.warning("storage_quota_check_failed org_id=%s error=%s", org_id, type(exc).__name__)
        return None
    used = int((snap or {}).get("total_bytes") or 0)
    state, ratio = quota_state(used, limit)
    if state == "warn":
        logger.warning("storage_quota_warning org_id=%s percent=%.1f", org_id, (ratio or 0) * 100)
        return None
    if state != "over" or limit is None:
        return None
    return StorageQuotaExceededError(
        "Your workspace has used its storage allowance "
        f"({_gb(used)} of {_gb(limit)}). New syncs and uploads are paused until space is freed "
        "or the plan is upgraded. Nothing has been deleted.",
        used_bytes=used,
        limit_bytes=limit,
    )


def ensure_storage_quota(client: Any, settings: Any, org_id: str, *, action: str) -> None:
    """Raise StorageQuotaExceededError when enforcement is on and the org is over its limit."""
    refusal = storage_quota_block_reason(client, settings, org_id)
    if refusal is not None:
        logger.warning("storage_quota_refused org_id=%s action=%s", org_id, action)
        raise refusal


def _gb(value: int) -> str:
    return f"{value / (1024 ** 3):.1f} GB"
