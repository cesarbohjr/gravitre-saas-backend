"""Completed-turn replay so a dropped SSE still recovers persisted assistant text (Phase F4).

In-flight tool resume is out of scope. Redis is the fast path; conversation_messages
is the durable fallback.
"""
from __future__ import annotations

import json
import threading
import time
from typing import Any

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.core.redis_client import get_redis_client

logger = get_logger(__name__)

REPLAY_TTL_SECONDS = 900
_KEY_PREFIX = "chat:replay:"

_lock = threading.Lock()
_local_replays: dict[str, tuple[float, dict[str, Any]]] = {}


def replay_key(org_id: str, conversation_id: str) -> str:
    return f"{_KEY_PREFIX}{org_id}:{conversation_id}"


def _prune_local(now: float) -> None:
    expired = [key for key, (until, _payload) in _local_replays.items() if until <= now]
    for key in expired:
        _local_replays.pop(key, None)


def store_completed_turn(
    org_id: str,
    conversation_id: str | None,
    *,
    user_text: str,
    assistant_text: str,
    tool_results: list[dict[str, Any]] | None = None,
    assistant_message_id: str | None = None,
    settings: Settings | None = None,
) -> str | None:
    """Remember the latest completed turn for this conversation. Returns event_id."""
    oid = (org_id or "").strip()
    cid = (conversation_id or "").strip() if conversation_id else ""
    text = (assistant_text or "").strip()
    if not oid or not cid or not text:
        return None
    event_id = (assistant_message_id or "").strip() or f"replay-{int(time.time() * 1000)}"
    payload = {
        "event_id": event_id,
        "conversation_id": cid,
        "org_id": oid,
        "user_text": (user_text or "").strip(),
        "assistant_text": text,
        "tool_calls": list(tool_results or []),
        "assistant_message_id": event_id,
    }
    raw = json.dumps(payload, separators=(",", ":"))
    key = replay_key(oid, cid)
    redis = get_redis_client(settings or get_settings())
    if redis is not None:
        try:
            redis.setex(key, REPLAY_TTL_SECONDS, raw)
            return event_id
        except Exception as exc:  # noqa: BLE001
            logger.warning("chat replay redis setex failed key=%s error=%s", key, str(exc)[:200])
    with _lock:
        _local_replays[key] = (time.monotonic() + REPLAY_TTL_SECONDS, payload)
    return event_id


def load_completed_turn(
    org_id: str,
    conversation_id: str,
    *,
    last_event_id: str | None = None,
    settings: Settings | None = None,
) -> dict[str, Any] | None:
    oid = (org_id or "").strip()
    cid = (conversation_id or "").strip()
    if not oid or not cid:
        return None
    key = replay_key(oid, cid)
    payload: dict[str, Any] | None = None
    redis = get_redis_client(settings or get_settings())
    if redis is not None:
        try:
            raw = redis.get(key)
            if raw:
                payload = json.loads(raw) if isinstance(raw, str) else json.loads(str(raw))
        except Exception as exc:  # noqa: BLE001
            logger.debug("chat replay redis get failed key=%s error=%s", key, str(exc)[:200])
    if payload is None:
        now = time.monotonic()
        with _lock:
            _prune_local(now)
            stored = _local_replays.get(key)
            if stored:
                payload = dict(stored[1])
    if not isinstance(payload, dict):
        return None
    event_id = str(payload.get("event_id") or "")
    incoming = (last_event_id or "").strip()
    if incoming and event_id and incoming == event_id:
        return {"already_have": True, "event_id": event_id, "conversation_id": cid}
    payload["already_have"] = False
    return payload


def load_completed_turn_from_db(
    settings: Settings,
    *,
    org_id: str,
    user_id: str,
    conversation_id: str,
    last_event_id: str | None = None,
) -> dict[str, Any] | None:
    """Durable fallback: latest assistant row on an owned conversation."""
    from app.workflows.repository import get_supabase_client

    cid = (conversation_id or "").strip()
    oid = (org_id or "").strip()
    uid = (user_id or "").strip()
    if not cid or not oid or not uid:
        return None
    try:
        client = get_supabase_client(settings)
        owned = (
            client.table("conversations")
            .select("id")
            .eq("id", cid)
            .eq("org_id", oid)
            .eq("user_id", uid)
            .limit(1)
            .execute()
        )
        if not owned.data:
            return None
        rows = (
            client.table("conversation_messages")
            .select("id, role, content, tool_calls, created_at")
            .eq("conversation_id", cid)
            .eq("role", "assistant")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if not rows.data:
            return None
        row = rows.data[0]
        event_id = str(row.get("id") or "")
        incoming = (last_event_id or "").strip()
        if incoming and event_id and incoming == event_id:
            return {"already_have": True, "event_id": event_id, "conversation_id": cid}
        return {
            "already_have": False,
            "event_id": event_id,
            "conversation_id": cid,
            "org_id": oid,
            "user_text": "",
            "assistant_text": str(row.get("content") or ""),
            "tool_calls": row.get("tool_calls") if isinstance(row.get("tool_calls"), list) else [],
            "assistant_message_id": event_id,
        }
    except Exception as exc:  # noqa: BLE001
        logger.debug("chat replay db fallback failed conversation_id=%s error=%s", cid, str(exc)[:200])
        return None


def reset_local_replays_for_tests() -> None:
    with _lock:
        _local_replays.clear()
