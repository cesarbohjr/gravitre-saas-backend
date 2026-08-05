"""Canonical aliases for legacy non vendor.resource.verb action ids (F8).

Callers may still use the short form; resolvers should prefer the canonical id.
"""
from __future__ import annotations

# short / legacy → canonical vendor.resource.verb
ACTION_ID_ALIASES: dict[str, str] = {
    "email.send": "email.messages.send",
    "webhook.post": "webhook.http.post",
    "salesforce.query": "salesforce.soql.query",
    "slack.post_message": "slack.messages.post",
    "slack.search_files": "slack.files.search",
    "slack.get_file_metadata": "slack.files.get_metadata",
    "slack.get_file_content": "slack.files.get_content",
    "microsoft365.search_files": "microsoft365.files.search",
    "microsoft365.get_file_metadata": "microsoft365.files.get_metadata",
    "microsoft365.get_file_content": "microsoft365.files.get_content",
    "google_calendar.freebusy": "google_calendar.calendars.freebusy",
    "notion.search_files": "notion.files.search",
    "notion.get_file_metadata": "notion.files.get_metadata",
    "notion.get_file_content": "notion.files.get_content",
    "notion.search": "notion.pages.search",
    "confluence.search_files": "confluence.files.search",
    "confluence.get_file_metadata": "confluence.files.get_metadata",
    "confluence.get_file_content": "confluence.files.get_content",
    "google_drive.search_files": "google_drive.files.search",
    "google_drive.get_file_metadata": "google_drive.files.get_metadata",
    "google_drive.get_file_content": "google_drive.files.get_content",
    "segment.identify": "segment.traits.identify",
    "segment.track": "segment.events.track",
    "segment.group": "segment.traits.group",
    "segment.alias": "segment.traits.alias",
    "segment.page": "segment.events.page",
    "segment.batch": "segment.events.batch",
}

# Reverse lookup for compatibility.
CANONICAL_TO_ALIASES: dict[str, tuple[str, ...]] = {}
for _alias, _canonical in ACTION_ID_ALIASES.items():
    CANONICAL_TO_ALIASES.setdefault(_canonical, ())
    CANONICAL_TO_ALIASES[_canonical] = (*CANONICAL_TO_ALIASES[_canonical], _alias)


def resolve_canonical_action_id(action_id: str) -> str:
    text = str(action_id or "").strip()
    return ACTION_ID_ALIASES.get(text, text)
