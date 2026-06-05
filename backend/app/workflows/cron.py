"""Cron helpers for workflow schedules (STA-47)."""
from __future__ import annotations

from datetime import datetime, timezone

from apscheduler.triggers.cron import CronTrigger

_CRON_ALIASES = {
    "@hourly": "0 * * * *",
    "@daily": "0 0 * * *",
    "@weekly": "0 0 * * 0",
    "@monthly": "0 0 1 * *",
}


def normalize_cron_expression(cron_expression: str) -> str:
    expr = cron_expression.strip()
    return _CRON_ALIASES.get(expr, expr)


def compute_next_run_at(cron_expression: str, base: datetime | None = None) -> str | None:
    """Return the next fire time (UTC ISO) after base for a standard 5-field cron."""
    if base is None:
        base = datetime.now(timezone.utc)
    elif base.tzinfo is None:
        base = base.replace(tzinfo=timezone.utc)
    else:
        base = base.astimezone(timezone.utc)

    expr = normalize_cron_expression(cron_expression)
    if not expr:
        return None
    try:
        trigger = CronTrigger.from_crontab(expr, timezone=timezone.utc)
        next_fire = trigger.get_next_fire_time(None, base)
        if next_fire is None:
            return None
        if next_fire.tzinfo is None:
            next_fire = next_fire.replace(tzinfo=timezone.utc)
        return next_fire.astimezone(timezone.utc).isoformat()
    except Exception:
        return None
