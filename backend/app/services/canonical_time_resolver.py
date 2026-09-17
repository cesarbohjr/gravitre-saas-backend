"""Deterministic calendar-window resolver for F1 READ preflight (no LLM)."""
from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

_MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}

_PHRASE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("today", re.compile(r"\btoday\b", re.I)),
    ("yesterday", re.compile(r"\byesterday\b", re.I)),
    ("year_to_date", re.compile(r"\b(?:year[\s-]*to[\s-]*date|ytd)\b", re.I)),
    ("last_quarter", re.compile(r"\blast\s+quarter\b", re.I)),
    ("this_quarter", re.compile(r"\bthis\s+quarter\b", re.I)),
    ("last_week", re.compile(r"\blast\s+week\b", re.I)),
    ("this_week", re.compile(r"\bthis\s+week\b", re.I)),
    ("last_month", re.compile(r"\b(?:last|previous)\s+(?:calendar\s+)?month\b", re.I)),
    ("this_month", re.compile(r"\bthis\s+month\b", re.I)),
    ("last_30_days", re.compile(r"\b(?:last|past)\s+30\s+days\b", re.I)),
    (
        "named_month",
        re.compile(
            r"\b(?:in\s+)?(january|february|march|april|may|june|july|august|"
            r"september|october|november|december)\s*(20\d{2})?\b",
            re.I,
        ),
    ),
)


@dataclass(frozen=True)
class TimeWindow:
    start: date
    end: date
    timezone: str
    interpretation: str
    source_phrase: str

    @property
    def start_iso(self) -> str:
        return self.start.isoformat()

    @property
    def end_iso(self) -> str:
        return self.end.isoformat()

    def as_dict(self) -> dict[str, str]:
        return {
            "start": self.start_iso,
            "end": self.end_iso,
            "timezone": self.timezone,
            "interpretation": self.interpretation,
            "source_phrase": self.source_phrase,
        }


def _zone(name: str | None) -> ZoneInfo:
    tz_name = str(name or "UTC").strip() or "UTC"
    try:
        return ZoneInfo(tz_name)
    except Exception:  # noqa: BLE001
        return ZoneInfo("UTC")


def _today(timezone_name: str | None, *, now: datetime | None = None) -> tuple[date, str]:
    tz_name = str(timezone_name or "UTC").strip() or "UTC"
    tz = _zone(tz_name)
    current = now.astimezone(tz) if now is not None else datetime.now(tz)
    return current.date(), str(tz)


def _week_bounds(day: date) -> tuple[date, date]:
    start = day - timedelta(days=day.weekday())
    end = start + timedelta(days=6)
    return start, end


def _quarter_bounds(day: date) -> tuple[date, date]:
    q = (day.month - 1) // 3
    start_month = q * 3 + 1
    start = date(day.year, start_month, 1)
    end_month = start_month + 2
    end = date(day.year, end_month, calendar.monthrange(day.year, end_month)[1])
    return start, end


def detect_time_phrase(text: str) -> tuple[str, str] | None:
    raw = str(text or "")
    for key, pattern in _PHRASE_PATTERNS:
        match = pattern.search(raw)
        if match:
            return key, match.group(0)
    return None


def resolve_time_window(
    text: str | None,
    *,
    timezone_name: str | None = None,
    now: datetime | None = None,
    phrase_key: str | None = None,
) -> TimeWindow | None:
    """Resolve business-language windows. 'last month' is the previous calendar month."""
    detected = (phrase_key, phrase_key) if phrase_key else detect_time_phrase(text or "")
    if not detected:
        return None
    key, phrase = detected
    today, tz_label = _today(timezone_name, now=now)

    if key == "today":
        start = end = today
        interpretation = "calendar_day"
    elif key == "yesterday":
        start = end = today - timedelta(days=1)
        interpretation = "previous_calendar_day"
    elif key == "this_week":
        start, end = _week_bounds(today)
        end = min(end, today)
        interpretation = "current_iso_week_monday_sunday"
    elif key == "last_week":
        this_start, _ = _week_bounds(today)
        end = this_start - timedelta(days=1)
        start = end - timedelta(days=6)
        interpretation = "previous_iso_week_monday_sunday"
    elif key == "this_month":
        start = date(today.year, today.month, 1)
        end = today
        interpretation = "current_calendar_month_to_date"
    elif key == "last_month":
        first_this = date(today.year, today.month, 1)
        end = first_this - timedelta(days=1)
        start = date(end.year, end.month, 1)
        interpretation = "previous_calendar_month"
    elif key == "last_30_days":
        end = today
        start = today - timedelta(days=29)
        interpretation = "rolling_30_calendar_days"
    elif key == "this_quarter":
        start, q_end = _quarter_bounds(today)
        end = min(q_end, today)
        interpretation = "current_calendar_quarter_to_date"
    elif key == "last_quarter":
        this_start, _ = _quarter_bounds(today)
        end = this_start - timedelta(days=1)
        start, _unused = _quarter_bounds(end)
        interpretation = "previous_calendar_quarter"
    elif key == "year_to_date":
        start = date(today.year, 1, 1)
        end = today
        interpretation = "calendar_year_to_date"
    elif key == "named_month":
        named = re.search(
            r"(january|february|march|april|may|june|july|august|september|october|november|december)\s*(20\d{2})?",
            phrase,
            re.I,
        )
        if not named:
            return None
        month = _MONTHS[named.group(1).lower()]
        year = int(named.group(2)) if named.group(2) else today.year
        if named.group(2) is None and month > today.month:
            year -= 1
        start = date(year, month, 1)
        end = date(year, month, calendar.monthrange(year, month)[1])
        interpretation = "named_calendar_month"
    else:
        return None

    return TimeWindow(
        start=start,
        end=end,
        timezone=tz_label,
        interpretation=interpretation,
        source_phrase=phrase,
    )
