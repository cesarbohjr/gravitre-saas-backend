"""Cron helpers for workflow schedules (STA-47 + SaaS once/timezone)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from apscheduler.triggers.cron import CronTrigger

_CRON_ALIASES = {
    "@hourly": "0 * * * *",
    "@daily": "0 0 * * *",
    "@weekly": "0 0 * * 0",
    "@monthly": "0 0 1 * *",
    "@once": "@once",
}

ONCE_SENTINEL = "@once"


def normalize_cron_expression(cron_expression: str) -> str:
    expr = (cron_expression or "").strip()
    return _CRON_ALIASES.get(expr, expr)


def resolve_timezone(tz_name: str | None) -> timezone | ZoneInfo:
    name = (tz_name or "UTC").strip() or "UTC"
    if name.upper() == "UTC":
        return timezone.utc
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        return timezone.utc


def parse_iso_datetime(value: str | datetime | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(text)
        except ValueError:
            return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def is_once_schedule(
    *,
    schedule_type: str | None = None,
    cron_expression: str | None = None,
) -> bool:
    if str(schedule_type or "").strip().lower() == "once":
        return True
    return normalize_cron_expression(cron_expression or "") == ONCE_SENTINEL


def compute_next_run_at(
    cron_expression: str,
    base: datetime | None = None,
    *,
    tz_name: str | None = "UTC",
    ends_at: str | datetime | None = None,
    schedule_type: str | None = None,
    run_at: str | datetime | None = None,
) -> str | None:
    """Return the next fire time (UTC ISO) after base.

    For one-shot schedules, returns run_at when it is still in the future relative to base;
    otherwise None.
    """
    if base is None:
        base = datetime.now(timezone.utc)
    elif base.tzinfo is None:
        base = base.replace(tzinfo=timezone.utc)
    else:
        base = base.astimezone(timezone.utc)

    if is_once_schedule(schedule_type=schedule_type, cron_expression=cron_expression):
        fire = parse_iso_datetime(run_at)
        if fire is None:
            return None
        if fire <= base:
            return None
        return fire.isoformat()

    expr = normalize_cron_expression(cron_expression)
    if not expr or expr == ONCE_SENTINEL:
        return None
    tz = resolve_timezone(tz_name)
    try:
        trigger = CronTrigger.from_crontab(expr, timezone=tz)
        next_fire = trigger.get_next_fire_time(None, base)
        if next_fire is None:
            return None
        if next_fire.tzinfo is None:
            next_fire = next_fire.replace(tzinfo=timezone.utc)
        next_utc = next_fire.astimezone(timezone.utc)
    except Exception:
        return None

    end = parse_iso_datetime(ends_at)
    if end is not None and next_utc > end:
        return None
    return next_utc.isoformat()


def expand_cron_occurrences(
    cron_expression: str,
    start: datetime,
    end: datetime,
    *,
    max_occurrences: int = 200,
    tz_name: str | None = "UTC",
    ends_at: str | datetime | None = None,
    schedule_type: str | None = None,
    run_at: str | datetime | None = None,
) -> list[str]:
    """Return UTC ISO timestamps for fires in [start, end)."""
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    else:
        start = start.astimezone(timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    else:
        end = end.astimezone(timezone.utc)
    if end <= start:
        return []

    schedule_end = parse_iso_datetime(ends_at)
    hard_end = min(end, schedule_end) if schedule_end is not None else end

    if is_once_schedule(schedule_type=schedule_type, cron_expression=cron_expression):
        fire = parse_iso_datetime(run_at)
        if fire is None:
            return []
        if start <= fire < hard_end:
            return [fire.isoformat()]
        return []

    expr = normalize_cron_expression(cron_expression)
    if not expr or expr == ONCE_SENTINEL:
        return []
    tz = resolve_timezone(tz_name)
    try:
        trigger = CronTrigger.from_crontab(expr, timezone=tz)
    except Exception:
        return []

    occurrences: list[str] = []
    cursor = start
    while len(occurrences) < max_occurrences:
        next_fire = trigger.get_next_fire_time(None, cursor)
        if next_fire is None:
            break
        if next_fire.tzinfo is None:
            next_fire = next_fire.replace(tzinfo=timezone.utc)
        else:
            next_fire = next_fire.astimezone(timezone.utc)
        if next_fire >= hard_end:
            break
        occurrences.append(next_fire.isoformat())
        cursor = next_fire + timedelta(seconds=1)
    return occurrences
