"""Share an Intelligence finding with a teammate or channel, in an app the team already uses.

Only internal destinations are offered: Slack channels and people when the
organization has a working Slack connection, and email to people in the
organization when Gravitre can send email. Every share is written to the audit
trail, and the message always carries a link back to the finding in Gravitre.
"""
from __future__ import annotations

import re
import threading
import time
from datetime import datetime, timezone
from typing import Any

from app.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)

APPS = ("slack", "email")
MAX_TITLE = 200
MAX_NOTE = 1000
MAX_SUMMARY = 600
MAX_CHANNELS = 200
# Per person: a share is a deliberate click, so a small ceiling only stops runaway loops.
RATE_LIMIT = 30
RATE_WINDOW_SEC = 3600

AUDIT_ACTION = "intelligence.finding_shared"

_PATH_RE = re.compile(r"^/[A-Za-z0-9/_\-?=&%.#:]*$")
_SLACK_CHANNEL_RE = re.compile(r"^[CGD][A-Z0-9]{6,}$")

_recent: dict[str, list[float]] = {}
_recent_lock = threading.Lock()


class ShareInputError(ValueError):
    """The request names something the share dialog does not offer."""


class ShareDeliveryError(RuntimeError):
    """The destination app refused or could not be reached."""


def _rate_limited(user_id: str, now: float) -> bool:
    with _recent_lock:
        stamps = [t for t in _recent.get(user_id, []) if now - t < RATE_WINDOW_SEC]
        if len(stamps) >= RATE_LIMIT:
            _recent[user_id] = stamps
            return True
        stamps.append(now)
        _recent[user_id] = stamps
        return False


def clean_path(path: str | None) -> str:
    """A link back into Gravitre: a same-site path only, never another host."""
    text = str(path or "").strip() or "/intelligence"
    if not text.startswith("/") or text.startswith("//") or not _PATH_RE.match(text):
        raise ShareInputError("The link must point to a page in Gravitre.")
    return text[:300]


def build_message(*, title: str, summary: str, note: str, sender: str, link: str) -> str:
    """Plain text used for Slack (and the email preview)."""
    lines = []
    if note:
        lines.append(note)
        lines.append("")
    lines.append(f"*{title}*")
    if summary:
        lines.append(summary)
    lines.append("")
    lines.append(f"Shared from Gravitre by {sender} · {link}")
    return "\n".join(lines)


def _members(client: Any, org_id: str) -> list[dict[str, Any]]:
    rows = client.table("organization_members").select("user_id, role").eq("org_id", org_id).execute().data or []
    ids = [str(r["user_id"]) for r in rows if r.get("user_id")]
    if not ids:
        return []
    users = (
        client.table("users").select("auth_user_id, email, full_name").in_("auth_user_id", ids[:500]).execute().data
        or []
    )
    by_id = {str(u.get("auth_user_id")): u for u in users}
    people = []
    for uid in ids:
        user = by_id.get(uid) or {}
        email = str(user.get("email") or "").strip()
        if not email:
            continue
        name = str(user.get("full_name") or "").strip() or email.split("@")[0]
        people.append({"id": uid, "name": name, "email": email})
    people.sort(key=lambda p: p["name"].lower())
    return people


def _slack_token(client: Any, org_id: str, settings: Settings) -> str | None:
    from app.connectors.connector_tool_auth import resolve_slack_bot_token
    from app.connectors.repository import get_connector_by_type

    if settings.disable_connectors:
        return None
    conn = get_connector_by_type(client, org_id, "slack", environment_name="default")
    if not conn:
        return None
    try:
        return resolve_slack_bot_token(
            client, org_id, str(conn["id"]), settings, environment_name=str(conn.get("environment") or "default")
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("share: slack token failed org_id=%s: %s", org_id, exc)
        return None


def _slack_channels(token: str) -> list[dict[str, Any]]:
    from app.connectors.slack import list_conversations

    channels: list[dict[str, Any]] = []
    cursor: str | None = None
    while len(channels) < MAX_CHANNELS:
        page = list_conversations(token, limit=200, cursor=cursor)
        for ch in page.get("channels") or []:
            if ch.get("is_archived"):
                continue
            channels.append(
                {
                    "id": str(ch.get("id")),
                    "name": f"#{ch.get('name')}",
                    "private": bool(ch.get("is_private")),
                    "members": ch.get("num_members"),
                }
            )
        cursor = (page.get("response_metadata") or {}).get("next_cursor") or None
        if not cursor:
            break
    channels.sort(key=lambda c: c["name"])
    return channels[:MAX_CHANNELS]


def email_available(settings: Settings, client: Any, org_id: str) -> bool:
    from app.connectors.repository import get_connector_by_type
    from app.services.notification_email_service import _platform_smtp_configured

    if not settings.notification_email_enabled:
        return False
    if _platform_smtp_configured(settings):
        return True
    if settings.disable_connectors:
        return False
    return bool(get_connector_by_type(client, org_id, "email"))


def share_options(client: Any, org_id: str, settings: Settings, *, user_id: str) -> dict[str, Any]:
    people = [p for p in _members(client, org_id) if p["id"] != user_id]
    apps: list[dict[str, Any]] = []
    unavailable: list[str] = []

    token = _slack_token(client, org_id, settings)
    if token:
        try:
            channels = _slack_channels(token)
            apps.append({"id": "slack", "name": "Slack", "channels": channels, "people": people})
        except ValueError as exc:
            logger.warning("share: slack channel list failed org_id=%s: %s", org_id, exc)
            unavailable.append("Slack")
    else:
        unavailable.append("Slack")

    if email_available(settings, client, org_id):
        apps.append({"id": "email", "name": "Email", "channels": [], "people": people})
    else:
        unavailable.append("Email")

    return {"apps": apps, "unavailable": unavailable}


def _send_slack(token: str, *, channel: str | None, person_email: str | None, text: str) -> str:
    from app.connectors.slack import join_conversation, send_slack_message, slack_api_call

    if person_email:
        try:
            found = slack_api_call(token, "users.lookupByEmail", params={"email": person_email})
        except ValueError as exc:
            raise ShareDeliveryError(
                "Slack couldn't find this person by their email, so the message was not sent."
            ) from exc
        target = str((found.get("user") or {}).get("id") or "")
        if not target:
            raise ShareDeliveryError("Slack couldn't find this person, so the message was not sent.")
    else:
        target = str(channel or "")
    try:
        result = send_slack_message(token, target, text)
    except ValueError as exc:
        if "not_in_channel" in str(exc) and not person_email:
            try:
                join_conversation(token, target)
                result = send_slack_message(token, target, text)
            except ValueError as exc2:
                raise ShareDeliveryError(
                    "Gravitre isn't in that channel yet. Invite the Gravitre app to it in Slack, then share again."
                ) from exc2
        else:
            raise ShareDeliveryError(f"Slack didn't accept the message ({exc}).") from exc
    ts = str(result.get("ts") or "")
    chan = str(result.get("channel") or target)
    return f"https://app.slack.com/archives/{chan}/p{ts.replace('.', '')}" if ts else ""


def _send_email(
    client: Any,
    settings: Settings,
    *,
    org_id: str,
    to_addr: str,
    title: str,
    summary: str,
    note: str,
    sender: str,
    path: str,
) -> None:
    from app.services.notification_email_service import (
        _send_email as deliver,
        _simple_completion_email,
        load_org_email_branding,
    )

    brand = load_org_email_branding(client, org_id, settings)
    # The template escapes the summary, so this stays plain text.
    parts = [note, summary, f"Shared from Gravitre by {sender}."]
    body = " · ".join(p for p in parts if p)
    subject, html_body = _simple_completion_email(
        brand,
        subject_prefix=f"{sender} shared: {title}",
        headline=title,
        summary=body,
        view_url=f"{brand.app_base_url}{path}",
        cta_label="Open in Gravitre",
    )
    if not deliver(settings, to_addr=to_addr, subject=subject, html_body=html_body, client=client, org_id=org_id):
        raise ShareDeliveryError("The email could not be sent. Check email delivery in Settings, then try again.")


def share_finding(
    client: Any,
    org_id: str,
    settings: Settings,
    *,
    user_id: str,
    sender_name: str,
    app: str,
    channel_id: str | None,
    person_id: str | None,
    title: str,
    summary: str,
    note: str,
    path: str | None,
    finding_id: str | None = None,
    now: float | None = None,
) -> dict[str, Any]:
    from app.services.notification_email_service import _app_base_url
    from app.workflows.audit import write_audit_event

    app = (app or "").strip().lower()
    if app not in APPS:
        raise ShareInputError("Choose Slack or Email.")
    title = " ".join(str(title or "").split())[:MAX_TITLE]
    if not title:
        raise ShareInputError("There is nothing to share.")
    summary = " ".join(str(summary or "").split())[:MAX_SUMMARY]
    note = str(note or "").strip()[:MAX_NOTE]
    link_path = clean_path(path)
    if bool(channel_id) == bool(person_id):
        raise ShareInputError("Choose one channel or one person to send to.")
    if channel_id and (app != "slack" or not _SLACK_CHANNEL_RE.match(channel_id)):
        raise ShareInputError("Choose a Slack channel from the list.")

    person = None
    if person_id:
        person = next((p for p in _members(client, org_id) if p["id"] == person_id), None)
        if not person:
            raise ShareInputError("That person isn't in your organization.")

    if _rate_limited(user_id, now if now is not None else time.monotonic()):
        raise ShareInputError("You've shared a lot in the last hour. Try again later.")

    link = f"{_app_base_url(settings)}{link_path}"
    destination: str
    url = ""
    if app == "slack":
        token = _slack_token(client, org_id, settings)
        if not token:
            raise ShareDeliveryError("Slack isn't connected. Connect it in Connectors to share there.")
        text = build_message(title=title, summary=summary, note=note, sender=sender_name, link=link)
        url = _send_slack(token, channel=channel_id, person_email=person["email"] if person else None, text=text)
        destination = person["name"] if person else str(channel_id)
    else:
        if not person:
            raise ShareInputError("Choose a person to email.")
        if not email_available(settings, client, org_id):
            raise ShareDeliveryError("Email delivery is turned off for Gravitre right now.")
        _send_email(
            client,
            settings,
            org_id=org_id,
            to_addr=person["email"],
            title=title,
            summary=summary,
            note=note,
            sender=sender_name,
            path=link_path,
        )
        destination = person["name"]

    write_audit_event(
        client,
        org_id=org_id,
        actor_id=user_id,
        action=AUDIT_ACTION,
        resource_type="intelligence_finding",
        resource_id=org_id,
        metadata={
            "app": app,
            "channel_id": channel_id,
            "person_id": person_id,
            "finding_id": (finding_id or "")[:120] or None,
            "title": title,
            "path": link_path,
        },
    )
    return {
        "shared": True,
        "app": app,
        "destination": destination,
        "url": url or None,
        "sharedAt": datetime.now(timezone.utc).isoformat(),
    }
