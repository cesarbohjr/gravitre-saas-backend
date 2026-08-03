"""Unified durable notification emission for bell, inbox, and email channels."""
from __future__ import annotations

import logging
import uuid
from typing import Any, Literal

logger = logging.getLogger(__name__)


def _is_uuid(value: Any) -> bool:
    """True when value is a real UUID — notifications.entity_id is uuid-typed."""
    text = str(value or "").strip()
    if not text:
        return False
    try:
        uuid.UUID(text)
        return True
    except (TypeError, ValueError):
        return False

NotificationEventType = Literal[
    "run_completed",
    "run_failed",
    "run_cancelled",
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
        "run_cancelled",
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
    # Agent lifecycle aliases → canonical Module A / bell types
    "agent_started": "run_started",
    "agent_discovery": "task_completed",
    "agent_task_completed": "task_completed",
}

_AGENT_ACTIVITY_ENTITY_TYPES = frozenset(
    {"agent", "agent_job", "workflow_run", "operator"}
)


def normalize_event_type(event_type: str) -> str:
    normalized = str(event_type or "system").strip() or "system"
    return _EVENT_TYPE_ALIASES.get(normalized, normalized)


def _resolve_entity_ref(entity_ref: dict[str, Any] | None) -> dict[str, Any]:
    """Normalize refs for the notifications table.

    ``notifications.entity_id`` is uuid. Vendor ids (HubSpot list_id ``\"19\"``,
    Apollo contact ints, etc.) must never be written there — keep them as
    ``external_entity_id`` / activity metadata instead.
    """
    ref = dict(entity_ref or {})
    result_url = ref.get("result_url") or ref.get("url")
    if result_url is not None:
        ref["result_url"] = str(result_url)

    raw_entity_id = ref.get("entity_id")
    if raw_entity_id is not None and not _is_uuid(raw_entity_id):
        vendor = str(raw_entity_id).strip()
        if vendor:
            ref["external_entity_id"] = str(ref.get("external_entity_id") or vendor)
            activity = dict(ref.get("activity_metadata") or {})
            activity.setdefault("external_entity_id", vendor)
            ref["activity_metadata"] = activity
        ref.pop("entity_id", None)
    elif raw_entity_id is not None:
        ref["entity_id"] = str(raw_entity_id).strip()
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
    entity_id = entity_ref.get("entity_id")
    if entity_id is not None and not _is_uuid(entity_id):
        # Defense in depth — never send non-UUID to the uuid column.
        entity_id = None
    row = {
        "org_id": org_id,
        "user_id": user_id,
        "type": event_type,
        "title": title[:200],
        "body": body[:2000],
        "url": entity_ref.get("result_url"),
        "entity_type": entity_ref.get("entity_type"),
        "entity_id": entity_id,
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


def _record_connector_activity(
    client: Any,
    *,
    org_id: str,
    user_id: str,
    event_type: str,
    title: str,
    body: str,
    entity_ref: dict[str, Any],
    notification_id: str | None,
) -> None:
    entity_type = str(entity_ref.get("entity_type") or "").strip().lower()
    if entity_type == "connector":
        source = "connector_write"
    elif entity_type in _AGENT_ACTIVITY_ENTITY_TYPES:
        source = "agent"
    else:
        return
    from app.services.activity_feed_service import record_activity_event

    if event_type in {"run_failed", "scheduled_run_failed"}:
        status = "failed"
    elif event_type in {"run_started", "approval_needed"}:
        status = "running" if event_type == "run_started" else "pending"
    else:
        status = "completed"
    metadata = dict(entity_ref.get("activity_metadata") or {})
    if notification_id:
        metadata["notification_id"] = notification_id
    record_activity_event(
        client,
        org_id=org_id,
        user_id=user_id,
        source=source,
        event_type=event_type,
        title=title,
        body=body,
        status=status,
        entity_type=entity_type,
        entity_id=str(entity_ref.get("entity_id") or "") or None,
        url=entity_ref.get("result_url"),
        integration=str(entity_ref.get("integration") or "") or None,
        metadata=metadata,
    )


def _publish_live_notification(
    *,
    org_id: str,
    user_id: str,
    notification_id: str,
    event_type: str,
    title: str,
    body: str,
    entity_ref: dict[str, Any],
) -> None:
    from app.services.notification_live_bus import publish

    publish(
        org_id,
        user_id,
        {
            "id": notification_id,
            "type": event_type,
            "title": title,
            "body": body,
            "entity_type": entity_ref.get("entity_type"),
            "entity_id": entity_ref.get("entity_id"),
            "url": entity_ref.get("result_url"),
        },
    )


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
    email_context: dict[str, Any] | None = None,
) -> str | None:
    """Persist a notification durably, then optionally trigger ephemeral channels."""
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

    from app.services.notification_preference_service import channel_enabled

    bell_allowed = channel_enabled(client, org_id, user_id, canonical_type, "bell")
    email_allowed = channel_enabled(client, org_id, user_id, canonical_type, "email")

    if hints.get("email") and email_allowed:
        _send_email_if_configured(
            client,
            org_id=org_id,
            user_id=user_id,
            event_type=canonical_type,
            title=title,
            body=body,
            entity_ref=ref,
            email_context=email_context,
        )

    if hints.get("bell", True) and not bell_allowed:
        logger.debug(
            "bell channel disabled by preference notification_id=%s event_type=%s",
            notification_id,
            canonical_type,
        )

    if hints.get("bell", True) and bell_allowed:
        _publish_live_notification(
            org_id=org_id,
            user_id=user_id,
            notification_id=notification_id,
            event_type=canonical_type,
            title=title,
            body=body,
            entity_ref=ref,
        )

    _record_connector_activity(
        client,
        org_id=org_id,
        user_id=user_id,
        event_type=canonical_type,
        title=title,
        body=body,
        entity_ref=ref,
        notification_id=notification_id,
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
    email_context: dict[str, Any] | None = None,
) -> None:
    try:
        from app.config import get_settings
        from app.services.notification_email_service import (
            email_notifications_enabled,
            send_assignment_completion_email,
            send_marketplace_install_email,
            send_swarm_completion_email,
            send_workflow_completion_email,
        )

        settings = get_settings()
        if not settings.notification_email_enabled:
            return
        if not email_notifications_enabled(client, org_id, user_id, event_type):
            return

        ctx = dict(email_context or {})
        kind = str(ctx.get("kind") or "").strip()
        if kind == "workflow_completion":
            send_workflow_completion_email(
                client,
                settings,
                org_id=org_id,
                user_id=user_id,
                run_id=str(ctx.get("run_id") or ""),
                workflow_name=str(ctx.get("workflow_name") or "Workflow"),
                final_status=str(ctx.get("final_status") or "completed"),
            )
            return
        if kind == "swarm_completion":
            send_swarm_completion_email(
                client,
                settings,
                org_id=org_id,
                user_id=user_id,
                swarm_run_id=str(ctx.get("swarm_run_id") or ""),
                objective=str(ctx.get("objective") or "Multi-agent run"),
                final_recommendation=ctx.get("final_recommendation"),
                final_confidence=ctx.get("final_confidence"),
                decision_method=str(ctx.get("decision_method") or "majority_vote"),
                subtasks=list(ctx.get("subtasks") or []),
                dissenting_opinions=list(ctx.get("dissenting_opinions") or []),
            )
            return
        if kind == "assignment_completion":
            send_assignment_completion_email(
                client,
                settings,
                org_id=org_id,
                user_id=user_id,
                job_id=str(ctx.get("job_id") or ""),
                task_title=str(ctx.get("task_title") or title),
                requires_approval=bool(ctx.get("requires_approval")),
            )
            return
        if kind == "marketplace_install":
            send_marketplace_install_email(
                client,
                settings,
                org_id=org_id,
                user_id=user_id,
                asset_title=str(ctx.get("asset_title") or title),
                asset_type=str(ctx.get("asset_type") or ""),
                view_path=str(ctx.get("view_path") or entity_ref.get("result_url") or "/marketplace/installed"),
            )
            return

        logger.info(
            "email channel requested without dispatch context event_type=%s user_id=%s",
            event_type,
            user_id,
        )
        _ = (title, body, entity_ref)
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
