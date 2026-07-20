"""Portal-aware HubSpot deep links.

HubSpot requires a portal/hub id in the path. Portal-less URLs like
``https://app.hubspot.com/contacts/objects/0-1/views/all/list`` 404 for most accounts.
Never emit those; return None when hub_id is unknown.
"""
from __future__ import annotations

from typing import Any

OBJECT_TYPE_IDS = {
    "contacts": "0-1",
    "contact": "0-1",
    "companies": "0-2",
    "company": "0-2",
    "deals": "0-3",
    "deal": "0-3",
    "tickets": "0-5",
    "ticket": "0-5",
}


def extract_hub_id(*sources: Any) -> str | None:
    """Pull hub/portal id from connector config, OAuth tokens, or loose dicts."""
    for source in sources:
        if not isinstance(source, dict):
            continue
        for key in ("hub_id", "hubId", "portal_id", "portalId"):
            value = source.get(key)
            if value is None:
                continue
            text = str(value).strip()
            if text and text.lower() not in {"none", "null"}:
                return text
        nested = source.get("config")
        if isinstance(nested, dict):
            found = extract_hub_id(nested)
            if found:
                return found
    return None


def is_portal_scoped_hubspot_url(url: str | None) -> bool:
    """True when URL includes a numeric hub segment after /contacts/."""
    text = (url or "").strip()
    if not text.startswith("https://app.hubspot.com/contacts/"):
        return False
    rest = text[len("https://app.hubspot.com/contacts/") :]
    hub = rest.split("/", 1)[0]
    return hub.isdigit()


def contacts_object_list_url(hub_id: str | None, *, object_type: str = "contacts") -> str | None:
    portal = (hub_id or "").strip()
    if not portal:
        return None
    type_id = OBJECT_TYPE_IDS.get(object_type.lower())
    if not type_id:
        return None
    return f"https://app.hubspot.com/contacts/{portal}/objects/{type_id}/views/all/list"


def record_url(hub_id: str | None, *, object_type: str, record_id: str | None) -> str | None:
    portal = (hub_id or "").strip()
    rid = str(record_id or "").strip()
    type_id = OBJECT_TYPE_IDS.get(object_type.lower())
    if not portal or not rid or not type_id:
        return None
    return f"https://app.hubspot.com/contacts/{portal}/record/{type_id}/{rid}"


def list_membership_url(hub_id: str | None, *, list_id: str | None) -> str | None:
    portal = (hub_id or "").strip()
    lid = str(list_id or "").strip()
    if not portal or not lid:
        return None
    return f"https://app.hubspot.com/contacts/{portal}/lists/{lid}"


def pipelines_url(hub_id: str | None) -> str | None:
    portal = (hub_id or "").strip()
    if not portal:
        return None
    return f"https://app.hubspot.com/contacts/{portal}/objects/0-3/pipelines"


def users_settings_url(hub_id: str | None) -> str | None:
    # Settings URLs are portal-scoped under the account host; without hub_id omit.
    _ = hub_id
    return None


def resolve_search_or_list_result_url(
    hub_id: str | None,
    *,
    object_type: str,
    records: list[dict[str, Any]] | None,
) -> str | None:
    """Prefer a single-record deep link; else portal list URL; never for empty results."""
    rows = [row for row in (records or []) if isinstance(row, dict)]
    if not rows:
        return None
    if len(rows) == 1:
        record = record_url(hub_id, object_type=object_type, record_id=rows[0].get("id"))
        if record:
            return record
    return contacts_object_list_url(hub_id, object_type=object_type)
