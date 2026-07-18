"""Platform grounding volume monitor — gate 2 replacement via live telemetry.

Tracks aggregate daily grounding counts against Google's 10k/day/account free tier.
One Gravitree GCP account serves all customers — do not shard per org at Google layer.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from supabase import Client

from app.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)

FREE_TIER_DAILY_LIMIT = 10_000
ALERT_THRESHOLD_RATIO = 0.75  # 75% — within 70–80% band requested


def _today() -> date:
    return datetime.now(timezone.utc).date()


def record_grounding_count(
    client: Client,
    *,
    org_id: str | None,
    count: int = 1,
) -> dict[str, Any]:
    """Increment platform + optional org daily counters; emit alert near free-tier cap."""
    usage_date = _today().isoformat()
    increment = max(int(count or 1), 1)

    platform_total = _increment_counter(client, table="platform_grounding_daily", key={"usage_date": usage_date}, count=increment)
    org_total = None
    if org_id:
        org_total = _increment_counter(
            client,
            table="org_research_lookup_daily",
            key={"usage_date": usage_date, "org_id": org_id},
            count=increment,
        )

    alert = _maybe_emit_alert(client, usage_date=usage_date, platform_total=platform_total)
    return {
        "usage_date": usage_date,
        "platform_grounding_count": platform_total,
        "org_lookup_count": org_total,
        "free_tier_limit": FREE_TIER_DAILY_LIMIT,
        "alert_threshold": int(FREE_TIER_DAILY_LIMIT * ALERT_THRESHOLD_RATIO),
        "alert": alert,
    }


def _increment_counter(client: Client, *, table: str, key: dict[str, Any], count: int) -> int:
    try:
        existing = client.table(table).select("*").match(key).limit(1).execute().data or []
        if existing:
            row = existing[0]
            count_field = "grounding_count" if table == "platform_grounding_daily" else "lookup_count"
            new_total = int(row.get(count_field) or 0) + count
            client.table(table).update({count_field: new_total, "updated_at": datetime.now(timezone.utc).isoformat()}).eq(
                "id", row["id"]
            ).execute()
            return new_total
        count_field = "grounding_count" if table == "platform_grounding_daily" else "lookup_count"
        insert_payload = {
            **key,
            count_field: count,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        client.table(table).insert(insert_payload).execute()
        return count
    except Exception as exc:  # noqa: BLE001
        logger.warning("grounding_counter_increment_failed table=%s error=%s", table, str(exc))
        return count


def _maybe_emit_alert(client: Client, *, usage_date: str, platform_total: int) -> dict[str, Any] | None:
    threshold = int(FREE_TIER_DAILY_LIMIT * ALERT_THRESHOLD_RATIO)
    if platform_total < threshold:
        return None

    severity = "warning" if platform_total < FREE_TIER_DAILY_LIMIT else "critical"
    message = (
        f"Platform grounding volume {platform_total}/{FREE_TIER_DAILY_LIMIT} on {usage_date} "
        f"({severity}) — Google $35/1k overage tier may apply above limit."
    )
    logger.warning("grounding_volume_alert %s", message)

    try:
        rows = client.table("platform_grounding_daily").select("id,alert_sent_at").eq("usage_date", usage_date).limit(1).execute().data or []
        if rows and not rows[0].get("alert_sent_at"):
            client.table("platform_grounding_daily").update(
                {"alert_sent_at": datetime.now(timezone.utc).isoformat(), "last_alert_severity": severity}
            ).eq("id", rows[0]["id"]).execute()
    except Exception:  # noqa: BLE001
        pass

    return {"severity": severity, "message": message, "platform_total": platform_total}


def get_platform_grounding_status(client: Client, settings: Settings | None = None) -> dict[str, Any]:
    _ = settings
    usage_date = _today().isoformat()
    platform_total = 0
    try:
        rows = client.table("platform_grounding_daily").select("*").eq("usage_date", usage_date).limit(1).execute().data or []
        if rows:
            platform_total = int(rows[0].get("grounding_count") or 0)
    except Exception:  # noqa: BLE001
        pass
    threshold = int(FREE_TIER_DAILY_LIMIT * ALERT_THRESHOLD_RATIO)
    return {
        "usage_date": usage_date,
        "platform_grounding_count": platform_total,
        "free_tier_limit": FREE_TIER_DAILY_LIMIT,
        "alert_threshold": threshold,
        "pct_of_free_tier": round((platform_total / FREE_TIER_DAILY_LIMIT) * 100, 2) if FREE_TIER_DAILY_LIMIT else 0,
        "in_overage_tier": platform_total >= FREE_TIER_DAILY_LIMIT,
    }
