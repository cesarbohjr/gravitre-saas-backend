"""Per-user notification channel preferences keyed by canonical event type."""
from __future__ import annotations

import logging
from typing import Any

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
) -> dict[str, bool]:
    """Apply a structured update on top of ``stored`` (or the defaults).

    Events and channels missing from ``structured`` keep their stored value,
    so a page that edits four events does not reset the other five.
    """
    payload = merge_preferences(stored)
    for event_type in PREFERENCE_EVENT_TYPES:
        row = structured.get(event_type)
        if not isinstance(row, dict):
            continue
        for channel in CHANNELS:
            field = f"{channel}_enabled"
            if field in row:
                payload[_pref_key(event_type, channel)] = bool(row[field])
    return payload
