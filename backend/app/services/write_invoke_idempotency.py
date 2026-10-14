"""Stable idempotency keys for connector write invokes (Release 2).

Pairs with ``logical_action_id`` for chat and run/step lineage for canvas so a
retry after an ambiguous failure does not duplicate provider side effects when
the first attempt actually succeeded.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from app.core.logging import get_logger
from app.core.safe_dict import safe_normalize_stored_dict
from app.services.action_lifecycle import logical_action_id
from app.services.tool_types import NormalizedResult, ToolContext

logger = get_logger(__name__)

TABLE = "write_invoke_idempotency"
_STATUS_COMPLETED = "completed"


def _missing_table(exc: Exception) -> bool:
    text = str(exc)
    return TABLE in text and ("42P01" in text or "PGRST205" in text or "does not exist" in text.lower())


def build_write_idempotency_key(
    ctx: ToolContext,
    action: str,
    params: dict[str, Any] | None,
) -> tuple[str, str | None]:
    """Return (idempotency_key, logical_action_id)."""
    params = params if isinstance(params, dict) else {}
    logical_id: str | None = None
    if ctx.conversation_id:
        pending_id = str(params.get("pending_action_id") or params.get("pendingActionId") or "")
        logical_id = logical_action_id(
            org_id=ctx.org_id,
            conversation_id=str(ctx.conversation_id),
            invoke_action=action,
            pending_action_id=pending_id or None,
            args=params,
        )
        return f"chat:{logical_id}", logical_id
    lineage = {
        "org_id": ctx.org_id,
        "action": action,
        "run_id": str(ctx.run_id or ""),
        "step_id": str(ctx.step_id or ""),
        "turn_id": str(ctx.turn_id or ""),
        "connector_id": str(params.get("connector_id") or ctx.connector_id or ""),
        "args": safe_normalize_stored_dict(params),
    }
    raw = json.dumps(lineage, sort_keys=True, default=str)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"invoke:{digest}", logical_id


def _row_to_result(row: dict[str, Any]) -> NormalizedResult | None:
    result = row.get("result") if isinstance(row.get("result"), dict) else {}
    if not result:
        return None
    return NormalizedResult(
        success=bool(result.get("success")),
        action=str(result.get("action") or ""),
        data=result.get("data") if isinstance(result.get("data"), dict) else {},
        error_code=result.get("error_code"),
        error_message=result.get("error_message"),
        connector_id=result.get("connector_id"),
        latency_ms=result.get("latency_ms"),
    )


def lookup_completed_write(client: Any, *, org_id: str, idempotency_key: str) -> NormalizedResult | None:
    try:
        rows = (
            client.table(TABLE)
            .select("result,status")
            .eq("org_id", org_id)
            .eq("idempotency_key", idempotency_key)
            .eq("status", _STATUS_COMPLETED)
            .limit(1)
            .execute()
            .data
            or []
        )
    except Exception as exc:  # noqa: BLE001
        if _missing_table(exc):
            return None
        logger.warning(
            "write_idempotency_lookup_failed org_id=%s key=%s error=%s",
            org_id,
            idempotency_key[:16],
            exc,
        )
        return None
    if not rows:
        return None
    parsed = _row_to_result(rows[0])
    if parsed and parsed.success:
        logger.info(
            "write_idempotency_replay org_id=%s key=%s action=%s",
            org_id,
            idempotency_key[:16],
            parsed.action,
        )
    return parsed if parsed and parsed.success else None


def record_completed_write(
    client: Any,
    *,
    org_id: str,
    idempotency_key: str,
    invoke_action: str,
    logical_action_id_value: str | None,
    result: NormalizedResult,
) -> None:
    row = {
        "org_id": org_id,
        "idempotency_key": idempotency_key,
        "invoke_action": invoke_action,
        "logical_action_id": logical_action_id_value,
        "status": _STATUS_COMPLETED,
        "result": {
            "success": result.success,
            "action": result.action,
            "data": result.data,
            "error_code": result.error_code,
            "error_message": result.error_message,
            "connector_id": result.connector_id,
            "latency_ms": result.latency_ms,
        },
    }
    try:
        client.table(TABLE).upsert(row, on_conflict="org_id,idempotency_key").execute()
    except Exception as exc:  # noqa: BLE001
        if _missing_table(exc):
            return
        logger.warning(
            "write_idempotency_record_failed org_id=%s key=%s error=%s",
            org_id,
            idempotency_key[:16],
            exc,
        )


def inject_provider_idempotency(params: dict[str, Any], idempotency_key: str) -> dict[str, Any]:
    """Pass stable key to HTTP executors that honor Idempotency-Key."""
    out = dict(params)
    out.setdefault("_gravitre_idempotency_key", idempotency_key)
    return out
