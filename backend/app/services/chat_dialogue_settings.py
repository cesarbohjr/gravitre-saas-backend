"""Org-level chat dialogue settings — stored on org_intelligence_engine_settings."""
from __future__ import annotations

from typing import Any

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.workflows.repository import get_supabase_client

logger = get_logger(__name__)

DEFAULT_DIALOGUE_SETTINGS: dict[str, Any] = {
    "clarification_threshold": 0.65,
    "escalation_threshold": 0.40,
    "proactive_suggestions_enabled": True,
    "max_suggestions_per_response": 2,
    "consensus_enabled": True,
    "sentiment_detection_enabled": True,
    "memory_retention_days": 90,
}


def merge_dialogue_settings(raw: dict[str, Any] | None) -> dict[str, Any]:
    merged = dict(DEFAULT_DIALOGUE_SETTINGS)
    if raw:
        merged.update({k: v for k, v in raw.items() if v is not None})
    return merged


async def load_chat_dialogue_settings(
    org_id: str,
    settings: Settings | None = None,
    *,
    client: Any | None = None,
) -> dict[str, Any]:
    active_settings = settings or get_settings()
    db = client or get_supabase_client(active_settings)
    try:
        rows = (
            db.table("org_intelligence_engine_settings")
            .select("dialogue_settings, default_persona")
            .eq("org_id", org_id)
            .limit(1)
            .execute()
            .data
            or []
        )
        if rows:
            row = rows[0]
            merged = merge_dialogue_settings(row.get("dialogue_settings") or {})
            merged["default_persona"] = row.get("default_persona") or "friendly_assistant"
            return merged
    except Exception as exc:  # noqa: BLE001
        logger.debug("load_chat_dialogue_settings fallback org_id=%s error=%s", org_id, exc)
    return {**DEFAULT_DIALOGUE_SETTINGS, "default_persona": "friendly_assistant"}


async def save_chat_dialogue_settings(
    org_id: str,
    updates: dict[str, Any],
    settings: Settings | None = None,
    *,
    client: Any | None = None,
) -> dict[str, Any]:
    active_settings = settings or get_settings()
    db = client or get_supabase_client(active_settings)
    current = await load_chat_dialogue_settings(org_id, active_settings, client=db)
    dialogue_patch = {k: updates[k] for k in DEFAULT_DIALOGUE_SETTINGS if k in updates}
    merged = merge_dialogue_settings({**current, **dialogue_patch})
    payload: dict[str, Any] = {
        "org_id": org_id,
        "dialogue_settings": {
            k: merged[k]
            for k in DEFAULT_DIALOGUE_SETTINGS
        },
    }
    if "default_persona" in updates:
        payload["default_persona"] = updates["default_persona"]
    try:
        db.table("org_intelligence_engine_settings").upsert(payload).execute()
    except Exception as exc:  # noqa: BLE001
        logger.warning("save_chat_dialogue_settings failed org_id=%s error=%s", org_id, exc)
    return merged
