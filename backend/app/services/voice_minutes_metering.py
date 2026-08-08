"""Voice Minutes metering — clone of research_lookup_metering pattern."""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from supabase import Client

from app.billing.service import derive_idempotency_key, get_plan_for_org
from app.billing.voice_minutes_plan_rates import (
    included_voice_minutes_for_plan,
    overage_usd_per_voice_minute,
)
from app.core.logging import get_logger

logger = get_logger(__name__)


def _month_start() -> date:
    now = datetime.now(timezone.utc)
    return date(now.year, now.month, 1)


def _month_end(start: date) -> date:
    if start.month == 12:
        return date(start.year + 1, 1, 1)
    return date(start.year, start.month + 1, 1)


def record_voice_minutes(
    client: Client,
    *,
    org_id: str,
    minutes: float,
    source_id: str,
    conversation_id: str | None = None,
    agent_id: str | None = None,
    stt_seconds: float = 0.0,
    tts_seconds: float = 0.0,
) -> dict[str, Any]:
    """Record voice session minutes (quantity stored as whole minutes, ceil)."""
    import math

    qty = max(int(math.ceil(float(minutes or 0.0))), 0)
    if qty <= 0 and (stt_seconds or tts_seconds):
        qty = max(int(math.ceil(max(stt_seconds, tts_seconds) / 60.0)), 1)
    if qty <= 0:
        return {"recorded": False, "reason": "zero_minutes"}

    period_start = _month_start()
    period_end = _month_end(period_start)
    metadata = {
        "source": "voice_session",
        "source_id": source_id,
        "conversation_id": conversation_id,
        "agent_id": agent_id,
        "stt_seconds": float(stt_seconds or 0),
        "tts_seconds": float(tts_seconds or 0),
        "raw_minutes": float(minutes or 0),
    }
    idempotency_key = derive_idempotency_key(
        org_id,
        "voice_minutes",
        period_start,
        metadata={"source": "voice_session", "source_id": source_id},
    )
    payload = {
        "org_id": org_id,
        "metric_type": "voice_minutes",
        "quantity": qty,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "metadata": metadata,
        "idempotency_key": idempotency_key,
    }
    inserted = False
    try:
        resp = (
            client.table("usage_records")
            .upsert(payload, on_conflict="org_id,idempotency_key", ignore_duplicates=True)
            .execute()
        )
        inserted = bool(resp.data)
    except Exception as exc:  # noqa: BLE001
        logger.warning("voice_minutes_usage_insert_failed org_id=%s error=%s", org_id, str(exc))
        try:
            client.table("usage_records").insert(payload).execute()
            inserted = True
        except Exception as inner:  # noqa: BLE001
            logger.warning("voice_minutes_usage_fallback_failed org_id=%s error=%s", org_id, str(inner))

    plan = get_plan_for_org(client, org_id)
    plan_code = str(plan.get("code") or "node")
    included = included_voice_minutes_for_plan(plan, plan_code=plan_code)
    overage_rate = overage_usd_per_voice_minute(plan)

    month_total = 0
    try:
        rows = (
            client.table("usage_records")
            .select("quantity")
            .eq("org_id", org_id)
            .eq("metric_type", "voice_minutes")
            .gte("recorded_at", period_start.isoformat())
            .execute()
            .data
            or []
        )
        month_total = sum(int(r.get("quantity") or 0) for r in rows)
    except Exception:  # noqa: BLE001
        pass

    overage = max(month_total - included, 0)
    return {
        "recorded": inserted,
        "org_id": org_id,
        "plan_code": plan_code,
        "included_minutes_per_month": included,
        "month_total_minutes": month_total,
        "overage_minutes": overage,
        "overage_usd_estimate": round(overage * overage_rate, 2) if overage else 0.0,
        "overage_rate_usd": overage_rate,
        "quantity_recorded": qty,
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
    }
