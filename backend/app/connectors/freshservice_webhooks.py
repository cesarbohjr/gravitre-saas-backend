"""Freshservice inbound ticket events (Release 3 measurable workflow).

Freshservice's Workflow Automator "Trigger Webhook" action cannot compute an
HMAC, so each connector gets a generated secret that the automator sends either
as the ``X-Gravitre-Webhook-Secret`` header or as the HTTP Basic password. The
secret is stored encrypted (``connector_webhook_secret_store``) and compared in
constant time.

Recommended automator payload (Freshservice placeholders)::

    {"event": "ticket.updated", "ticket_id": "{{ticket.id_numeric}}",
     "status": "{{ticket.status}}", "priority": "{{ticket.priority}}",
     "subject": "{{ticket.subject}}", "requester_email": "{{ticket.from_email}}",
     "updated_at": "{{ticket.updated_on}}"}

Delivery is deduped on ``event_id`` when sent, else on a digest of
event + ticket id + updated_at + status, so an automator retry of the same
change starts no second run.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
from typing import Any

from app.config import Settings

SECRET_HEADER = "X-Gravitre-Webhook-Secret"
V1_TRIGGER_EVENTS: tuple[str, ...] = ("ticket.created", "ticket.updated", "ticket.status_changed")
_EVENT_ALIASES = {
    "ticket_created": "ticket.created",
    "created": "ticket.created",
    "ticket_updated": "ticket.updated",
    "updated": "ticket.updated",
    "ticket_status_changed": "ticket.status_changed",
    "status_changed": "ticket.status_changed",
}
# Freshservice numeric ticket statuses (API v2).
STATUS_NAMES = {2: "open", 3: "pending", 4: "resolved", 5: "closed"}


def freshservice_inbound_webhook_url(settings: Settings, connector_id: str) -> str | None:
    base = (getattr(settings, "api_public_url", "") or "").strip().rstrip("/")
    if not base:
        return None
    return f"{base}/api/webhooks/freshservice/inbound/{connector_id}"


def _basic_password(authorization: str | None) -> str | None:
    if not authorization or not authorization.lower().startswith("basic "):
        return None
    try:
        decoded = base64.b64decode(authorization.split(" ", 1)[1].strip(), validate=True).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return None
    _user, sep, password = decoded.partition(":")
    return password if sep else None


def verify_freshservice_webhook(
    *,
    secret: str,
    header_secret: str | None,
    authorization: str | None,
) -> bool:
    if not secret:
        return False
    expected = secret.strip().encode("utf-8")
    for candidate in (header_secret, _basic_password(authorization)):
        if candidate and hmac.compare_digest(candidate.strip().encode("utf-8"), expected):
            return True
    return False


def canonical_event(raw: Any) -> str | None:
    text = str(raw or "").strip().lower()
    if text in V1_TRIGGER_EVENTS:
        return text
    return _EVENT_ALIASES.get(text)


def _ticket_id(value: Any) -> str | None:
    text = str(value if value is not None else "").strip().lstrip("#").removeprefix("INC-").removeprefix("SR-")
    return text if text.isascii() and text.isdigit() and int(text) > 0 else None


def normalize_status(value: Any) -> str | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    if text.isdigit():
        return STATUS_NAMES.get(int(text), text)
    return text.lower()


def flatten_inbound_payload(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [dict(p) for p in payload if isinstance(p, dict)]
    if isinstance(payload, dict):
        if isinstance(payload.get("events"), list):
            return [dict(p) for p in payload["events"] if isinstance(p, dict)]
        return [payload]
    return []


def normalize_freshservice_event(event: dict[str, Any]) -> dict[str, Any] | None:
    """Workflow parameters for one ticket event, or None when unusable."""
    ticket_src = event.get("ticket") if isinstance(event.get("ticket"), dict) else event
    ticket_id = _ticket_id(ticket_src.get("id") or event.get("ticket_id") or event.get("id"))
    name = canonical_event(event.get("event") or event.get("event_type")) or "ticket.updated"
    if not ticket_id:
        return None
    status = normalize_status(ticket_src.get("status") or event.get("status"))
    ticket = {
        "id": ticket_id,
        "status": status,
        "priority": ticket_src.get("priority") or event.get("priority"),
        "subject": ticket_src.get("subject") or event.get("subject"),
        "requester_email": ticket_src.get("requester_email")
        or ticket_src.get("from_email")
        or event.get("requester_email"),
        "updated_at": ticket_src.get("updated_at") or event.get("updated_at"),
    }
    return {
        "event": name,
        "ticket_id": ticket_id,
        "ticket": {k: v for k, v in ticket.items() if v not in (None, "")},
        "freshservice_event": {k: v for k, v in event.items() if k != "ticket"},
    }


def freshservice_event_id(event: dict[str, Any], normalized: dict[str, Any]) -> str:
    explicit = str(event.get("event_id") or event.get("eventId") or "").strip()
    if explicit:
        return f"fs:{explicit[:180]}"
    ticket = normalized.get("ticket") or {}
    basis = [normalized.get("event"), normalized.get("ticket_id"), ticket.get("updated_at"), ticket.get("status")]
    if not ticket.get("updated_at"):
        # Without a change timestamp the only stable identity is the payload itself.
        basis.append(json.dumps(event, sort_keys=True, default=str))
    digest = hashlib.sha256("|".join(str(b) for b in basis).encode("utf-8")).hexdigest()[:40]
    return f"fs:{digest}"


def event_matches_trigger(trigger: dict[str, Any], *, event: str, status: str | None) -> bool:
    if not trigger.get("active", True) or not trigger.get("workflow_id"):
        return False
    wanted = canonical_event(trigger.get("event"))
    if wanted != event and not (wanted == "ticket.updated" and event == "ticket.status_changed"):
        return False
    status_filter = normalize_status(trigger.get("status"))
    return not status_filter or status_filter == (status or "")
