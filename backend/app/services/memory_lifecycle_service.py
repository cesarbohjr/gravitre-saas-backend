"""Deterministic memory lifecycle — explicit forget/deactivate rules."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def deactivate_memory(
    client: Any,
    *,
    org_id: str,
    memory_id: str,
    reason: str,
    user_id: str | None = None,
) -> bool:
    """Hard deactivate — deterministic, not model discretion. Never raises."""
    if not client or not org_id or not memory_id:
        return False
    if not (reason or "").strip():
        return False
    try:
        rows = (
            client.table("agent_memories")
            .select("id,org_id,is_active")
            .eq("id", memory_id)
            .eq("org_id", org_id)
            .limit(1)
            .execute()
            .data
            or []
        )
        if not rows:
            return False
        client.table("agent_memories").update(
            {
                "is_active": False,
                "is_current": False,
                "valid_until": _now_iso(),
                "updated_at": _now_iso(),
            }
        ).eq("id", memory_id).eq("org_id", org_id).execute()
        logger.info(
            "memory_deactivated org_id=%s memory_id=%s reason=%s user_id=%s",
            org_id,
            memory_id,
            reason[:120],
            user_id,
        )
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("memory_deactivate_failed memory_id=%s error=%s", memory_id, exc)
        return False


def forget_by_key(
    client: Any,
    *,
    org_id: str,
    memory_key: str,
    reason: str,
    user_id: str | None = None,
) -> int:
    """Deactivate all current rows for a temporal key. Returns count deactivated."""
    if not client or not org_id or not memory_key:
        return 0
    count = 0
    try:
        rows = (
            client.table("agent_memories")
            .select("id")
            .eq("org_id", org_id)
            .eq("memory_key", memory_key)
            .eq("is_active", True)
            .execute()
            .data
            or []
        )
        for row in rows:
            if deactivate_memory(
                client,
                org_id=org_id,
                memory_id=str(row["id"]),
                reason=reason,
                user_id=user_id,
            ):
                count += 1
    except Exception as exc:  # noqa: BLE001
        logger.warning("memory_forget_by_key_failed key=%s error=%s", memory_key, exc)
    return count


def apply_forget_request(
    client: Any,
    *,
    org_id: str,
    message: str,
    user_id: str | None = None,
) -> dict[str, Any]:
    """Parse explicit forget-this phrasing and deactivate matching memories."""
    import re

    text = (message or "").strip()
    result: dict[str, Any] = {"matched": False, "deactivated": 0, "memory_ids": []}
    if not text:
        return result

    lower = text.lower()
    if not re.search(r"\bforget\b", lower):
        return result

    # "forget ICP" / "forget the icp employee range"
    needle = re.sub(r"(?i)^.*?\bforget\b\s+(?:the\s+)?", "", text).strip()
    if len(needle) < 3:
        return result

    result["matched"] = True
    try:
        rows = (
            client.table("agent_memories")
            .select("id,content,memory_key")
            .eq("org_id", org_id)
            .eq("is_active", True)
            .order("created_at", desc=True)
            .limit(50)
            .execute()
            .data
            or []
        )
        needle_l = needle.lower()
        for row in rows:
            content = str(row.get("content") or "").lower()
            if needle_l in content or content in needle_l:
                if deactivate_memory(
                    client,
                    org_id=org_id,
                    memory_id=str(row["id"]),
                    reason=f"user_forget:{needle[:120]}",
                    user_id=user_id,
                ):
                    result["deactivated"] += 1
                    result["memory_ids"].append(str(row["id"]))
    except Exception as exc:  # noqa: BLE001
        result["error"] = str(exc)[:200]
    return result
