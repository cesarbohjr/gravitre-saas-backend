"""Temporal validity for agent memories (Graphiti-style history).

Temporal categories (preference, decision, relationship, procedural) supersede
on a stable ``memory_key`` instead of silent overwrite. Prior values are copied
into ``agent_memory_history`` and remain retrievable.
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.core.logging import get_logger

logger = get_logger(__name__)

TEMPORAL_CATEGORIES = frozenset({"decision", "preference", "relationship", "procedural"})

# Append-only — each event is a new row, not a supersede.
APPEND_ONLY_CATEGORIES = frozenset({"outcome", "episodic", "working"})


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_memory_key(category: str, content: str, explicit: str | None = None) -> str | None:
    """Derive a stable key for temporal facts."""
    if explicit and str(explicit).strip():
        return str(explicit).strip().lower()[:200]
    cat = str(category or "").strip().lower()
    if cat not in TEMPORAL_CATEGORIES:
        return None
    text = re.sub(r"\s+", " ", (content or "").strip().lower())
    if not text:
        return None
    # Prefer an explicit subject prefix when present: "ICP: ..." / "Preference: ..."
    subject = text
    for sep in (":", " — ", " - "):
        if sep in text[:120]:
            subject = text.split(sep, 1)[0].strip()
            break
    subject = subject[:120] or text[:120]
    digest = hashlib.sha256(f"{cat}:{subject}".encode()).hexdigest()[:16]
    return f"{cat}:{digest}"


def _content_equivalent(a: str, b: str) -> bool:
    return re.sub(r"\s+", " ", (a or "").strip().lower()) == re.sub(
        r"\s+", " ", (b or "").strip().lower()
    )


def _copy_to_history(
    client: Any,
    *,
    row: dict[str, Any],
    valid_until: str,
    superseded_by: str | None,
    change_reason: str | None,
) -> None:
    try:
        client.table("agent_memory_history").insert(
            {
                "id": str(uuid4()),
                "memory_id": row.get("id"),
                "org_id": row.get("org_id"),
                "memory_key": row.get("memory_key"),
                "category": row.get("category"),
                "content": row.get("content"),
                "structured_payload": row.get("structured_payload"),
                "valid_from": row.get("valid_from") or row.get("created_at") or _now_iso(),
                "valid_until": valid_until,
                "superseded_by": superseded_by,
                "change_reason": change_reason,
                "source_class": row.get("source_class"),
                "confidence": row.get("confidence"),
                "provenance": row.get("provenance"),
            }
        ).execute()
    except Exception as exc:  # noqa: BLE001
        logger.warning("memory_history_copy_failed memory_id=%s error=%s", row.get("id"), exc)


def get_current_by_key(client: Any, org_id: str, memory_key: str) -> dict[str, Any] | None:
    if not client or not org_id or not memory_key:
        return None
    try:
        rows = (
            client.table("agent_memories")
            .select("*")
            .eq("org_id", org_id)
            .eq("memory_key", memory_key)
            .eq("is_current", True)
            .limit(1)
            .execute()
            .data
            or []
        )
        return rows[0] if rows else None
    except Exception as exc:  # noqa: BLE001
        logger.debug("memory_current_lookup_failed key=%s error=%s", memory_key, exc)
        return None


def get_memory_history(
    client: Any,
    org_id: str,
    memory_key: str,
    *,
    limit: int = 20,
) -> list[dict[str, Any]]:
    if not client or not org_id or not memory_key:
        return []
    try:
        rows = (
            client.table("agent_memory_history")
            .select("*")
            .eq("org_id", org_id)
            .eq("memory_key", memory_key)
            .order("valid_from", desc=True)
            .limit(max(1, min(limit, 100)))
            .execute()
            .data
            or []
        )
        return [r for r in rows if isinstance(r, dict)]
    except Exception as exc:  # noqa: BLE001
        logger.debug("memory_history_lookup_failed key=%s error=%s", memory_key, exc)
        return []


def upsert_temporal_memory(
    client: Any,
    payload: dict[str, Any],
    *,
    change_reason: str | None = None,
) -> dict[str, Any] | None:
    """Insert or supersede a temporal memory row. Never raises."""
    if not client or not payload.get("org_id"):
        return None

    category = str(payload.get("category") or "").strip().lower()
    content = str(payload.get("content") or "").strip()
    if not content:
        return None

    memory_key = payload.get("memory_key") or normalize_memory_key(
        category, content, payload.get("explicit_key")
    )

    if category not in TEMPORAL_CATEGORIES or not memory_key:
        # Append-only path — caller inserts directly.
        return None

    payload = {**payload, "memory_key": memory_key, "is_current": True}
    if "valid_from" not in payload:
        payload["valid_from"] = _now_iso()

    current = get_current_by_key(client, str(payload["org_id"]), memory_key)
    if not current:
        try:
            inserted = client.table("agent_memories").insert(payload).execute().data or []
            return inserted[0] if inserted else payload
        except Exception as exc:  # noqa: BLE001
            logger.debug("memory_temporal_insert_failed error=%s", exc)
            return None

    if _content_equivalent(str(current.get("content") or ""), content):
        return current

    now = _now_iso()
    new_id = str(payload.get("id") or uuid4())
    payload["id"] = new_id
    payload["superseded_by"] = None

    try:
        inserted = client.table("agent_memories").insert(payload).execute().data or []
        new_row = inserted[0] if inserted else payload
        client.table("agent_memories").update(
            {
                "is_current": False,
                "valid_until": now,
                "superseded_by": new_id,
                "updated_at": now,
            }
        ).eq("id", current["id"]).execute()
        _copy_to_history(
            client,
            row=current,
            valid_until=now,
            superseded_by=new_id,
            change_reason=change_reason or "superseded_by_new_value",
        )
        logger.info(
            "memory_temporal_superseded org_id=%s key=%s old_id=%s new_id=%s",
            payload.get("org_id"),
            memory_key,
            current.get("id"),
            new_id,
        )
        return new_row if isinstance(new_row, dict) else payload
    except Exception as exc:  # noqa: BLE001
        logger.warning("memory_temporal_supersede_failed error=%s", exc)
        return None
