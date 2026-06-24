"""User-visible in-app notifications."""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


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
) -> None:
    if not org_id or not user_id:
        return
    row = {
        "org_id": org_id,
        "user_id": user_id,
        "type": notification_type,
        "title": title[:200],
        "body": body[:2000],
        "url": url,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "is_read": False,
        "is_archived": False,
    }
    try:
        client.table("notifications").insert(row).execute()
    except Exception as exc:  # noqa: BLE001
        logger.warning("notification insert failed org_id=%s user_id=%s: %s", org_id, user_id, exc)
