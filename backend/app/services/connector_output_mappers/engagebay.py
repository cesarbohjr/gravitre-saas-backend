"""EngageBay write-action output mapper — summary (+ optional deep link).

EngageBay's public API returns contact ids on create/update but does not expose a
stable, documented browser deep-link for every tenant. Verified contract for these
actions is therefore: non-empty summary body; ``result_url`` may be null.
"""
from __future__ import annotations

from typing import Any


def extract_contact_id(payload: dict[str, Any] | None, *, fallback_id: str | None = None) -> str | None:
    data = payload if isinstance(payload, dict) else {}
    contact = data.get("contact") if isinstance(data.get("contact"), dict) else data
    for key in ("id", "contact_id", "subscriber_id", "entity_id"):
        value = contact.get(key) if isinstance(contact, dict) else None
        if value is not None and str(value).strip():
            return str(value).strip()
    if fallback_id and str(fallback_id).strip():
        return str(fallback_id).strip()
    return None


def extract_contact_label(
    payload: dict[str, Any] | None,
    *,
    args: dict[str, Any] | None = None,
) -> str:
    data = payload if isinstance(payload, dict) else {}
    contact = data.get("contact") if isinstance(data.get("contact"), dict) else data
    props = contact if isinstance(contact, dict) else {}
    args = args or {}

    email = str(props.get("email") or args.get("email") or "").strip()
    first = str(props.get("first_name") or props.get("firstname") or args.get("first_name") or args.get("firstname") or "").strip()
    last = str(props.get("last_name") or props.get("lastname") or args.get("last_name") or args.get("lastname") or "").strip()
    name = " ".join(bit for bit in (first, last) if bit).strip()
    if name and email:
        return f"{name} <{email}>"
    if name:
        return name
    if email:
        return email
    return "contact"


def summarize_contact_write(
    *,
    action: str,
    result_data: dict[str, Any] | None,
    args: dict[str, Any] | None = None,
) -> str:
    """Human-readable completion line for EngageBay contact create/update."""
    label = extract_contact_label(result_data, args=args)
    contact_id = extract_contact_id(result_data, fallback_id=str((args or {}).get("contact_id") or "").strip() or None)
    verb = "Updated" if action.endswith(".update") else "Created"
    if contact_id:
        return f'{verb} EngageBay contact {label} (id: {contact_id}).'
    return f"{verb} EngageBay contact {label}."


def resolve_contact_result_url(result_data: dict[str, Any] | None) -> str | None:
    """Return a vendor deep link when the API provides one; otherwise None (verified)."""
    data = result_data if isinstance(result_data, dict) else {}
    for key in ("url", "html_url", "link", "permalink", "web_url"):
        value = data.get(key)
        if isinstance(value, str) and value.startswith(("http://", "https://")):
            return value
    contact = data.get("contact")
    if isinstance(contact, dict):
        for key in ("url", "html_url", "link", "permalink", "web_url"):
            value = contact.get(key)
            if isinstance(value, str) and value.startswith(("http://", "https://")):
                return value
    # No stable documented EngageBay UI deep-link pattern — summary-only is final.
    return None
