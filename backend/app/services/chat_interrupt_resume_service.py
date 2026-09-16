"""Phase F6 — resume after cooperative Stop from persisted partial text."""
from __future__ import annotations

import json
import re
import threading
import time
from typing import Any

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.core.redis_client import get_redis_client

logger = get_logger(__name__)

INTERRUPT_TTL_SECONDS = 900
_KEY_PREFIX = "chat:interrupt:"
_CONTINUE_RE = re.compile(
    r"^(continue|keep going|resume|go on|pick up where you left off)[.!?]*$",
    re.IGNORECASE,
)
_PLACEHOLDER_STOP = re.compile(r"^stopped\.?$", re.IGNORECASE)

_lock = threading.Lock()
_local: dict[str, tuple[float, dict[str, Any]]] = {}


def interrupt_key(org_id: str, conversation_id: str) -> str:
    return f"{_KEY_PREFIX}{org_id}:{conversation_id}"


def is_continue_utterance(text: str) -> bool:
    return bool(_CONTINUE_RE.match((text or "").strip()))


def is_stop_placeholder(text: str) -> bool:
    return bool(_PLACEHOLDER_STOP.match((text or "").strip()))


def _prune(now: float) -> None:
    expired = [key for key, (until, _payload) in _local.items() if until <= now]
    for key in expired:
        _local.pop(key, None)


def sanitize_interrupt_extra(extra: dict[str, Any] | None) -> dict[str, Any]:
    """Keep interrupt extras JSON-small and model-computable."""
    if not isinstance(extra, dict):
        return {}
    out: dict[str, Any] = {}
    tools = extra.get("tool_names") or extra.get("tools")
    if isinstance(tools, list):
        names = [str(item).strip()[:80] for item in tools if str(item).strip()]
        if names:
            out["tool_names"] = names[:24]
    pending = extra.get("pending_task")
    if isinstance(pending, dict) and pending:
        slim: dict[str, Any] = {}
        for key in ("action", "tool", "label", "integration", "status", "vendor"):
            if pending.get(key) not in (None, ""):
                slim[key] = str(pending[key])[:160]
        args = pending.get("args") or pending.get("parameters")
        if isinstance(args, dict) and args:
            slim["arg_keys"] = [str(k)[:40] for k in list(args.keys())[:20]]
        if slim:
            out["pending_task"] = slim
    ledger = extra.get("parameter_ledger") or extra.get("ledger")
    if isinstance(ledger, dict):
        slots = ledger.get("slots") if isinstance(ledger.get("slots"), dict) else ledger
        compact: dict[str, str] = {}
        if isinstance(slots, dict):
            for key, value in list(slots.items())[:16]:
                if isinstance(value, dict):
                    text = str(value.get("value") or "").strip()
                else:
                    text = str(value or "").strip()
                if text:
                    compact[str(key)[:40]] = text[:200]
        if compact:
            out["parameter_ledger"] = compact
        missing = ledger.get("pending_missing")
        if isinstance(missing, list) and missing:
            out["pending_missing"] = [str(item)[:40] for item in missing[:12]]
    return out


def store_interrupted_turn(
    org_id: str,
    conversation_id: str | None,
    *,
    user_text: str,
    assistant_text: str,
    settings: Settings | None = None,
    extra: dict[str, Any] | None = None,
) -> bool:
    oid = (org_id or "").strip()
    cid = (conversation_id or "").strip() if conversation_id else ""
    if not oid or not cid:
        return False
    payload: dict[str, Any] = {
        "org_id": oid,
        "conversation_id": cid,
        "user_text": (user_text or "").strip(),
        "assistant_text": (assistant_text or "").strip(),
        "interrupted": True,
    }
    sanitized = sanitize_interrupt_extra(extra)
    if sanitized:
        payload["extra"] = sanitized
    raw = json.dumps(payload, separators=(",", ":"))
    key = interrupt_key(oid, cid)
    redis = get_redis_client(settings or get_settings())
    if redis is not None:
        try:
            redis.setex(key, INTERRUPT_TTL_SECONDS, raw)
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("chat interrupt redis setex failed key=%s error=%s", key, str(exc)[:200])
    with _lock:
        _local[key] = (time.monotonic() + INTERRUPT_TTL_SECONDS, payload)
    return True


def load_interrupted_turn(
    org_id: str,
    conversation_id: str | None,
    *,
    settings: Settings | None = None,
) -> dict[str, Any] | None:
    oid = (org_id or "").strip()
    cid = (conversation_id or "").strip() if conversation_id else ""
    if not oid or not cid:
        return None
    key = interrupt_key(oid, cid)
    redis = get_redis_client(settings or get_settings())
    if redis is not None:
        try:
            raw = redis.get(key)
            if raw:
                if isinstance(raw, bytes):
                    raw = raw.decode("utf-8")
                data = json.loads(raw)
                if isinstance(data, dict):
                    return data
        except Exception as exc:  # noqa: BLE001
            logger.warning("chat interrupt redis get failed key=%s error=%s", key, str(exc)[:200])
    with _lock:
        _prune(time.monotonic())
        hit = _local.get(key)
        if hit is None:
            return None
        until, payload = hit
        if until <= time.monotonic():
            _local.pop(key, None)
            return None
        return dict(payload)


def clear_interrupted_turn(
    org_id: str,
    conversation_id: str | None,
    *,
    settings: Settings | None = None,
) -> None:
    oid = (org_id or "").strip()
    cid = (conversation_id or "").strip() if conversation_id else ""
    if not oid or not cid:
        return
    key = interrupt_key(oid, cid)
    redis = get_redis_client(settings or get_settings())
    if redis is not None:
        try:
            redis.delete(key)
        except Exception as exc:  # noqa: BLE001
            logger.warning("chat interrupt redis delete failed key=%s error=%s", key, str(exc)[:200])
    with _lock:
        _local.pop(key, None)


def merge_history_with_interrupt(
    history: list[dict[str, Any]],
    interrupt: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """Ensure the interrupted user+partial assistant turns are in history."""
    if not interrupt:
        return list(history)
    orig = str(interrupt.get("user_text") or "").strip()
    partial = str(interrupt.get("assistant_text") or "").strip()
    if not orig and not partial:
        return list(history)
    merged = list(history)
    last_content = ""
    last_role = ""
    if merged:
        last_role = str(merged[-1].get("role") or "")
        last_content = str(merged[-1].get("content") or "").strip()
    if partial and last_role == "assistant" and last_content == partial:
        return merged
    if orig and not any(
        str(row.get("role") or "") == "user" and str(row.get("content") or "").strip() == orig
        for row in merged[-4:]
    ):
        merged.append({"role": "user", "content": orig})
    if partial and not is_stop_placeholder(partial):
        merged.append({"role": "assistant", "content": partial})
    return merged


def resume_instruction(interrupt: dict[str, Any] | None, user_text: str) -> str:
    """Extra user-turn instruction when the operator said Continue after Stop."""
    if not interrupt or not is_continue_utterance(user_text):
        return user_text
    orig = str(interrupt.get("user_text") or "").strip()
    partial = str(interrupt.get("assistant_text") or "").strip()
    extra = interrupt.get("extra") if isinstance(interrupt.get("extra"), dict) else {}
    extra_json = ""
    if extra:
        extra_json = (
            "\nInterrupted turn extras (JSON; resume tools/ledger from this, "
            f"do not invent):\n{json.dumps(extra, separators=(',', ':'), default=str)[:2500]}"
        )
    if partial and not is_stop_placeholder(partial):
        return (
            "Continue the interrupted assistant reply from the partial text already "
            "in conversation history. Do not restart from scratch.\n"
            f"Original request: {orig or '(see history)'}"
            f"{extra_json}"
        )
    return (
        "The previous assistant turn was stopped before useful text. Continue the "
        f"original request without treating Stop as the answer.\nOriginal request: {orig or user_text}"
        f"{extra_json}"
    )


def reset_local_interrupts_for_tests() -> None:
    with _lock:
        _local.clear()
