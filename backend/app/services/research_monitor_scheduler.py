"""Research monitor ticks for company intelligence scheduler."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.services.research_service import get_research_service
from app.workflows.repository import get_supabase_client

logger = get_logger(__name__)


async def run_due_research_monitors(settings: Settings | None = None) -> dict[str, Any]:
    active = settings or get_settings()
    client = get_supabase_client(active)
    try:
        rows = (
            client.table("research_monitors")
            .select("*")
            .eq("enabled", True)
            .limit(50)
            .execute()
            .data
            or []
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("research_monitors_query_skipped error=%s", exc)
        return {"checked": 0, "trends": 0}

    research = get_research_service(active)
    now = datetime.now(timezone.utc)
    checked = 0
    trend_count = 0
    for row in rows:
        org_id = str(row.get("org_id") or "")
        topic = str(row.get("topic") or "").strip()
        if not org_id or not topic:
            continue
        interval_hours = int(row.get("check_interval_hours") or 24)
        last_checked = row.get("last_checked_at")
        due = True
        if last_checked:
            try:
                last_dt = datetime.fromisoformat(str(last_checked).replace("Z", "+00:00"))
                due = now - last_dt >= timedelta(hours=interval_hours)
            except (TypeError, ValueError):
                due = True
        if not due:
            continue
        try:
            trends = await research.detect_trends(org_id, topic)
            trend_count += len(trends)
            checked += 1
        except Exception as exc:  # noqa: BLE001
            logger.debug("research_monitor_tick_failed org=%s topic=%s error=%s", org_id, topic, exc)
    return {"checked": checked, "trends": trend_count}
