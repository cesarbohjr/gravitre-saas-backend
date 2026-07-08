"""Unified durable notification emission for bell, inbox, and email channels."""
from __future__ import annotations

import logging
from typing import Any, Literal

logger = logging.getLogger(__name__)

NotificationEventType = Literal[
    "run_completed",
    "run_failed",
    "approval_needed",
    "assignment_changed",
    "scheduled_run_completed",
    "scheduled_run_failed",
    "task_completed",
    "agent_created",
    "workflow_created",
    "run_started",
    "system",
]

CANONICAL_EVENT_TYPES: frozenset[str] = frozenset(
    {
        "run_completed",
        "run_failed",
        "approval_needed",
        "assignment_changed",
        "scheduled_run_completed",
        "scheduled_run_failed",
        "task_completed",
        "agent_created",
        "workflow_created",
        "run_started",
        "system",
        "mention",
        "team_invite",
        "assignment_created",
    }
)

_EVENT_TYPE_ALIASES: dict[str, str] = {
    "assignment_created": "assignment_changed",
}


def normalize_event_type(event_type: str) -> str:
    normalized = str(event_type or "system").strip() or "system"
    return _EVENT_TYPE_ALIASES.get(normalized, normalized)


def _resolve_entity_ref(entity_ref: dict[str, Any] | None) -> dict[str, Any]:
    ref = dict(entity_ref or {})
    result_url = ref.get("result_url") or ref.get("url")
    if result_url is not None:
        ref["result_url"] = str(result_url)
    return ref


def _insert_notification_row(
    client: Any,
    *,
    org_id: str,
    user_id: str,
    event_type: str,
    title: str,
    body: str,
    entity_ref: dict[str, Any],
) -> str | None:
    row = {
        "org_id": org_id,
        "user_id": user_id,
        "type": event_type,
        "title": title[:200],
        "body": body[:2000],
        "url": entity_ref.get("result_url"),
        "entity_type": entity_ref.get("entity_type"),
        "entity_id": entity_ref.get("entity_id"),
        "is_read": False,
        "is_archived": False,
    }
    try:
        response = client.table("notifications").insert(row).execute()
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "notification insert failed org_id=%s user_id=%s event_type=%s: %s",
            org_id,
            user_id,
            event_type,
            exc,
        )
        return None
    if response.data and isinstance(response.data, list) and response.data:
        return str(response.data[0].get("id") or "") or None
    return None


def emit_notification(
    client: Any,
    *,
    org_id: str,
    user_id: str,
    event_type: str,
    title: str,
    body: str,
    entity_ref: dict[str, Any] | None = None,
    channel_hints: dict[str, bool] | None = None,
) -> str | None:
    """Persist a notification durably, then optionally trigger ephemeral channels.

    Durable inbox write always happens first so offline users see the event on next fetch.
    Bell push is client-driven today (SWR poll + optional SSE execution cards); there is no
    websocket fanout yet. Email is best-effort and gated by channel_hints plus preferences.
    """
    if not org_id or not user_id:
        return None

    hints = dict(channel_hints or {})
    canonical_type = normalize_event_type(event_type)
    ref = _resolve_entity_ref(entity_ref)

    notification_id = _insert_notification_row(
        client,
        org_id=org_id,
        user_id=user_id,
        event_type=canonical_type,
        title=title,
        body=body,
        entity_ref=ref,
    )
    if notification_id is None:
        return None

    if hints.get("email"):
        _send_email_if_configured(
            client,
            org_id=org_id,
            user_id=user_id,
            event_type=canonical_type,
            title=title,
            body=body,
            entity_ref=ref,
        )

    # Live bell push requires an active session channel; until websocket fanout exists,
    # connected clients pick up durable rows via /api/notifications polling.
    if hints.get("bell", True) and hints.get("require_live_session", False):
        logger.debug(
            "live bell push requested but no session fanout configured notification_id=%s",
            notification_id,
        )

    return notification_id


def _send_email_if_configured(
    client: Any,
    *,
    org_id: str,
    user_id: str,
    event_type: str,
    title: str,
    body: str,
    entity_ref: dict[str, Any],
) -> None:
    try:
        from app.config import get_settings
        from app.services.notification_email_service import email_notifications_enabled

        if not email_notifications_enabled(client, org_id, user_id, event_type):
            return
        logger.info(
            "email channel requested for event_type=%s user_id=%s (delivery wired in Step 5 prefs)",
            event_type,
            user_id,
        )
        _ = (title, body, entity_ref, get_settings())
    except Exception as exc:  # noqa: BLE001
        logger.warning("notification email channel skipped event_type=%s: %s", event_type, exc)


def create_user_notification(
    client: Any,
    *,
    org_id: str,
    user_id: str,
    notification_type: str,
    title: str,
    body: str,
    url: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    channel_hints: dict[str, bool] | None = None,
) -> str | None:
    """Backward-compatible wrapper — prefer emit_notification for new call sites."""
    return emit_notification(
        client,
        org_id=org_id,
        user_id=user_id,
        event_type=notification_type,
        title=title,
        body=body,
        entity_ref={
            "entity_type": entity_type,
            "entity_id": entity_id,
            "result_url": url,
        },
        channel_hints=channel_hints,
    )
