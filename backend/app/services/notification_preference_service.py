"""Per-user notification channel preferences keyed by canonical event type."""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

PREFERENCE_EVENT_TYPES: tuple[str, ...] = (
    "run_completed",
    "run_failed",
    "approval_needed",
    "assignment_changed",
    "scheduled_run_completed",
    "scheduled_run_failed",
    "task_completed",
    "source_attention",
    "weekly_summary",
)

# Delivery channels. "bell" is the in-app inbox; "slack" is a direct message
# from the workspace's Slack app to the person (matched by email).
CHANNELS: tuple[str, ...] = ("bell", "email", "slack")

DEFAULT_EVENT_PREFERENCES: dict[str, dict[str, bool]] = {
    "run_completed": {"bell_enabled": True, "email_enabled": False},
    "run_failed": {"bell_enabled": True, "email_enabled": True},
    "approval_needed": {"bell_enabled": True, "email_enabled": True},
    "assignment_changed": {"bell_enabled": True, "email_enabled": False},
    "scheduled_run_completed": {"bell_enabled": True, "email_enabled": False},
    "scheduled_run_failed": {"bell_enabled": True, "email_enabled": True},
    "task_completed": {"bell_enabled": True, "email_enabled": False},
    "source_attention": {"bell_enabled": True, "email_enabled": True},
    # In app only until someone opts in, so no org starts getting email it did not ask for.
    "weekly_summary": {"bell_enabled": True, "email_enabled": False},
}


def _pref_key(event_type: str, channel: str) -> str:
    return f"{channel}_{event_type}"


def default_preferences_payload() -> dict[str, bool]:
    payload: dict[str, bool] = {}
    for event_type, channels in DEFAULT_EVENT_PREFERENCES.items():
        payload[_pref_key(event_type, "bell")] = channels["bell_enabled"]
        payload[_pref_key(event_type, "email")] = channels["email_enabled"]
        payload[_pref_key(event_type, "slack")] = channels.get("slack_enabled", False)
    return payload


def merge_preferences(stored: dict[str, Any] | None) -> dict[str, bool]:
    merged = default_preferences_payload()
    if isinstance(stored, dict):
        for key, value in stored.items():
            if isinstance(value, bool):
                merged[str(key)] = value
    return merged


def load_user_notification_preferences(
    client: Any,
    org_id: str,
    user_id: str,
) -> dict[str, bool]:
    if not org_id or not user_id:
        return default_preferences_payload()
    try:
        response = (
            client.table("notification_preferences")
            .select("preferences")
            .eq("org_id", org_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        if response.data:
            raw = response.data[0].get("preferences")
            if isinstance(raw, dict):
                return merge_preferences(raw)
    except Exception as exc:  # noqa: BLE001
        logger.warning("notification preference lookup failed user_id=%s: %s", user_id, exc)
    return default_preferences_payload()


def channel_enabled(
    client: Any,
    org_id: str,
    user_id: str,
    event_type: str,
    channel: str,
) -> bool:
    prefs = load_user_notification_preferences(client, org_id, user_id)
    key = _pref_key(event_type, channel)
    return bool(prefs.get(key, default_preferences_payload().get(key, True)))


def structured_preferences(stored: dict[str, Any] | None) -> dict[str, dict[str, bool]]:
    merged = merge_preferences(stored)
    structured: dict[str, dict[str, bool]] = {}
    for event_type in PREFERENCE_EVENT_TYPES:
        structured[event_type] = {
            "bell_enabled": merged.get(_pref_key(event_type, "bell"), True),
            "email_enabled": merged.get(_pref_key(event_type, "email"), False),
            "slack_enabled": merged.get(_pref_key(event_type, "slack"), False),
        }
    return structured


def flatten_structured_preferences(
    structured: dict[str, Any],
    stored: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Apply a structured update on top of ``stored`` (or the defaults).

    Events and channels missing from ``structured`` keep their stored value,
    so a page that edits four events does not reset the other five. Quiet
    hours ride along under ``quiet_hours``: replaced when the update carries
    them, otherwise kept from ``stored``.
    """
    payload: dict[str, Any] = dict(merge_preferences(stored))
    for event_type in PREFERENCE_EVENT_TYPES:
        row = structured.get(event_type)
        if not isinstance(row, dict):
            continue
        for channel in CHANNELS:
            field = f"{channel}_enabled"
            if field in row:
                payload[_pref_key(event_type, channel)] = bool(row[field])
    incoming_quiet = structured.get(QUIET_HOURS_KEY) if isinstance(structured, dict) else None
    previous_quiet = stored.get(QUIET_HOURS_KEY) if isinstance(stored, dict) else None
    if isinstance(incoming_quiet, dict):
        payload[QUIET_HOURS_KEY] = validate_quiet_hours(incoming_quiet)
    elif isinstance(previous_quiet, dict):
        payload[QUIET_HOURS_KEY] = normalize_quiet_hours(previous_quiet)
    return payload


def default_structured_preferences() -> dict[str, dict[str, bool]]:
    """What "Reset to defaults" in Settings > Notifications restores."""
    return structured_preferences({})


# ---------------------------------------------------------------------------
# Quiet hours: hold email and Slack in a daily window, in the person's own
# time zone. Approvals are urgent and always go out; the in-app inbox always
# keeps every notification.
# ---------------------------------------------------------------------------

QUIET_HOURS_KEY = "quiet_hours"
QUIET_HOURS_BYPASS_EVENTS: frozenset[str] = frozenset({"approval_needed"})
QUIET_HOURS_CHANNELS: frozenset[str] = frozenset({"email", "slack"})
DEFAULT_QUIET_HOURS: dict[str, Any] = {"enabled": False, "from": "20:00", "to": "08:00", "timezone": "UTC"}
_HHMM = re.compile(r"^([01][0-9]|2[0-3]):([0-5][0-9])$")


def _valid_timezone(name: str) -> bool:
    try:
        ZoneInfo(name)
    except Exception:  # noqa: BLE001 — ZoneInfoNotFoundError, ValueError on odd input
        return False
    return True


def validate_quiet_hours(raw: dict[str, Any]) -> dict[str, Any]:
    """Strictly validate an update from the settings page; raises ValueError."""
    start = str(raw.get("from") or DEFAULT_QUIET_HOURS["from"])
    end = str(raw.get("to") or DEFAULT_QUIET_HOURS["to"])
    tz = str(raw.get("timezone") or DEFAULT_QUIET_HOURS["timezone"]).strip()
    if not _HHMM.match(start) or not _HHMM.match(end):
        raise ValueError("Quiet hours need times like 20:00")
    if not _valid_timezone(tz):
        raise ValueError("Quiet hours need an IANA time zone like America/Vancouver")
    return {"enabled": raw.get("enabled") is True, "from": start, "to": end, "timezone": tz}


def normalize_quiet_hours(raw: Any) -> dict[str, Any]:
    """Lenient read of whatever is stored; falls back to the defaults."""
    if not isinstance(raw, dict):
        return dict(DEFAULT_QUIET_HOURS)
    try:
        return validate_quiet_hours(raw)
    except ValueError:
        return dict(DEFAULT_QUIET_HOURS)


def _minutes(hhmm: str) -> int:
    hours, minutes = hhmm.split(":")
    return int(hours) * 60 + int(minutes)


def quiet_hours_active(quiet: dict[str, Any] | None, now: datetime | None = None) -> bool:
    """True when ``now`` falls inside the window (which may cross midnight)."""
    q = normalize_quiet_hours(quiet)
    if not q["enabled"]:
        return False
    start, end = _minutes(q["from"]), _minutes(q["to"])
    if start == end:
        return False
    local = (now or datetime.now(timezone.utc)).astimezone(ZoneInfo(q["timezone"]))
    current = local.hour * 60 + local.minute
    if start < end:
        return start <= current < end
    return current >= start or current < end


def load_quiet_hours(client: Any, org_id: str, user_id: str) -> dict[str, Any]:
    if not org_id or not user_id:
        return dict(DEFAULT_QUIET_HOURS)
    try:
        response = (
            client.table("notification_preferences")
            .select("preferences")
            .eq("org_id", org_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        if response.data:
            raw = response.data[0].get("preferences")
            if isinstance(raw, dict):
                return normalize_quiet_hours(raw.get(QUIET_HOURS_KEY))
    except Exception as exc:  # noqa: BLE001
        logger.warning("quiet hours lookup failed user_id=%s: %s", user_id, exc)
    return dict(DEFAULT_QUIET_HOURS)


def held_by_quiet_hours(
    client: Any,
    org_id: str,
    user_id: str,
    event_type: str,
    channel: str,
    now: datetime | None = None,
) -> bool:
    """Should this email or Slack message be skipped for the person's quiet hours?"""
    if channel not in QUIET_HOURS_CHANNELS or event_type in QUIET_HOURS_BYPASS_EVENTS:
        return False
    return quiet_hours_active(load_quiet_hours(client, org_id, user_id), now)
