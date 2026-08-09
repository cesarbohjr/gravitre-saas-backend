"""Platform grounding volume monitor — gate 2 replacement via live telemetry.

Tracks aggregate daily grounding counts against Google's 10k/day/account free tier.
One Gravitre GCP account serves all customers — do not shard per org at Google layer.

Also enforces a hard per-org hourly circuit breaker (default 500/hour) independent of
the 75% platform alert — alerts are post-facto; the circuit breaker blocks runaway cost.
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
DEFAULT_ORG_HOURLY_CIRCUIT_LIMIT = 500


def _today() -> date:
    return datetime.now(timezone.utc).date()


def _current_hour_bucket() -> datetime:
    now = datetime.now(timezone.utc)
    return now.replace(minute=0, second=0, microsecond=0)


def org_hourly_circuit_limit(settings: Settings | None) -> int:
    if settings is None:
        return DEFAULT_ORG_HOURLY_CIRCUIT_LIMIT
    limit = int(getattr(settings, "grounding_org_hourly_circuit_limit", DEFAULT_ORG_HOURLY_CIRCUIT_LIMIT) or 0)
    return max(limit, 0)


def check_org_grounding_circuit(
    client: Client,
    org_id: str,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Return whether this org is blocked by the hourly grounding circuit breaker."""
    limit = org_hourly_circuit_limit(settings)
    hour_bucket = _current_hour_bucket().isoformat()
    if not org_id or limit <= 0:
        return {
            "blocked": False,
            "org_id": org_id,
            "hour_bucket": hour_bucket,
            "hourly_count": 0,
            "hourly_limit": limit,
            "reason": None,
        }

    hourly_count = _read_org_hourly_count(client, org_id=org_id, hour_bucket=hour_bucket)
    blocked = hourly_count >= limit
    reason = None
    if blocked:
        reason = (
            f"Org exceeded hourly grounding circuit limit ({hourly_count}/{limit} in {hour_bucket})"
        )
        logger.warning("grounding_org_circuit_open org_id=%s count=%s limit=%s", org_id, hourly_count, limit)
    return {
        "blocked": blocked,
        "org_id": org_id,
        "hour_bucket": hour_bucket,
        "hourly_count": hourly_count,
        "hourly_limit": limit,
        "reason": reason,
    }


def _read_org_hourly_count(client: Client, *, org_id: str, hour_bucket: str) -> int:
    try:
        rows = (
            client.table("org_grounding_hourly")
            .select("grounding_count")
            .eq("org_id", org_id)
            .eq("hour_bucket", hour_bucket)
            .limit(1)
            .execute()
            .data
            or []
        )
        if rows:
            return int(rows[0].get("grounding_count") or 0)
    except Exception as exc:  # noqa: BLE001
        logger.warning("grounding_hourly_read_failed org_id=%s error=%s", org_id, str(exc))
    return 0


def _increment_org_hourly_count(client: Client, *, org_id: str, hour_bucket: str, count: int) -> int:
    try:
        existing = (
            client.table("org_grounding_hourly")
            .select("*")
            .eq("org_id", org_id)
            .eq("hour_bucket", hour_bucket)
            .limit(1)
            .execute()
            .data
            or []
        )
        now_iso = datetime.now(timezone.utc).isoformat()
        limit = DEFAULT_ORG_HOURLY_CIRCUIT_LIMIT
        if existing:
            row = existing[0]
            new_total = int(row.get("grounding_count") or 0) + count
            update_payload: dict[str, Any] = {
                "grounding_count": new_total,
                "updated_at": now_iso,
            }
            if new_total >= limit and not row.get("circuit_opened_at"):
                update_payload["circuit_opened_at"] = now_iso
            client.table("org_grounding_hourly").update(update_payload).eq("id", row["id"]).execute()
            return new_total

        opened_at = now_iso if count >= limit else None
        client.table("org_grounding_hourly").insert(
            {
                "org_id": org_id,
                "hour_bucket": hour_bucket,
                "grounding_count": count,
                "circuit_opened_at": opened_at,
                "updated_at": now_iso,
            }
        ).execute()
        return count
    except Exception as exc:  # noqa: BLE001
        logger.warning("grounding_hourly_increment_failed org_id=%s error=%s", org_id, str(exc))
        return count


def record_grounding_count(
    client: Client,
    *,
    org_id: str | None,
    count: int = 1,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Increment platform + optional org daily/hourly counters; emit alert near free-tier cap."""
    usage_date = _today().isoformat()
    hour_bucket = _current_hour_bucket().isoformat()
    increment = max(int(count or 1), 1)

    platform_total = _increment_counter(client, table="platform_grounding_daily", key={"usage_date": usage_date}, count=increment)
    org_total = None
    org_hourly_total = None
    circuit = None
    if org_id:
        org_total = _increment_counter(
            client,
            table="org_research_lookup_daily",
            key={"usage_date": usage_date, "org_id": org_id},
            count=increment,
        )
        org_hourly_total = _increment_org_hourly_count(
            client,
            org_id=org_id,
            hour_bucket=hour_bucket,
            count=increment,
        )
        circuit = check_org_grounding_circuit(client, org_id, settings)

    alert = _maybe_emit_alert(client, usage_date=usage_date, platform_total=platform_total)
    return {
        "usage_date": usage_date,
        "hour_bucket": hour_bucket,
        "platform_grounding_count": platform_total,
        "org_lookup_count": org_total,
        "org_hourly_grounding_count": org_hourly_total,
        "org_hourly_circuit": circuit,
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
