"""Durable write invoke claims and replay (Release 2).

Uses a service-role-only ledger and ``claim_write_invoke_idempotency`` for atomic
reservation before provider invocation. Completed-result caching alone is not
sufficient under concurrency or crash-between-commit scenarios.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Literal

from app.core.logging import get_logger
from app.core.safe_dict import safe_normalize_stored_dict
from app.services.action_lifecycle import logical_action_id
from app.services.tool_types import NormalizedResult, ToolContext, ToolError

logger = get_logger(__name__)

TABLE = "write_invoke_idempotency"
ClaimOutcome = Literal["claimed", "replay", "blocked", "error"]
FinalizeOutcome = Literal["finalized", "rejected", "error"]


@dataclass(frozen=True)
class WriteClaimResult:
    outcome: ClaimOutcome
    status: str | None = None
    replay: NormalizedResult | None = None
    reason: str | None = None
    claim_token: str | None = None
    claim_generation: int | None = None


@dataclass(frozen=True)
class WriteFinalizeResult:
    outcome: FinalizeOutcome
    reason: str | None = None


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
    nonce = str(params.get("_write_idempotency_nonce") or params.get("write_idempotency_nonce") or "").strip()
    connector = str(params.get("connector_id") or ctx.connector_id or "")
    logical_id: str | None = None
    if ctx.conversation_id:
        pending_id = str(params.get("pending_action_id") or params.get("pendingActionId") or "")
        turn = str(ctx.turn_id or params.get("turn_id") or "")
        logical_id = logical_action_id(
            org_id=ctx.org_id,
            conversation_id=str(ctx.conversation_id),
            invoke_action=action,
            pending_action_id=pending_id or turn or None,
            args=params,
        )
        parts = ["chat", logical_id, turn, connector, nonce]
        key = hashlib.sha256(":".join(p for p in parts if p).encode()).hexdigest()
        return f"chat:{key}", logical_id
    lineage = {
        "org_id": ctx.org_id,
        "action": action,
        "run_id": str(ctx.run_id or ""),
        "step_id": str(ctx.step_id or ""),
        "turn_id": str(ctx.turn_id or ""),
        "connector_id": connector,
        "nonce": nonce,
        "args": safe_normalize_stored_dict(params),
    }
    raw = json.dumps(lineage, sort_keys=True, default=str)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"invoke:{digest}", logical_id


def _row_to_result(payload: dict[str, Any] | None) -> NormalizedResult | None:
    if not isinstance(payload, dict) or not payload:
        return None
    return NormalizedResult(
        success=bool(payload.get("success")),
        action=str(payload.get("action") or ""),
        data=payload.get("data") if isinstance(payload.get("data"), dict) else {},
        error_code=payload.get("error_code"),
        error_message=payload.get("error_message"),
        connector_id=payload.get("connector_id"),
        latency_ms=payload.get("latency_ms"),
    )


def claim_write_invoke(
    client: Any,
    *,
    org_id: str,
    idempotency_key: str,
    invoke_action: str,
    logical_action_id_value: str | None,
    lease_seconds: int = 300,
) -> WriteClaimResult:
    try:
        res = client.rpc(
            "claim_write_invoke_idempotency",
            {
                "p_org_id": org_id,
                "p_key": idempotency_key,
                "p_invoke_action": invoke_action,
                "p_logical_action_id": logical_action_id_value,
                "p_lease_seconds": lease_seconds,
            },
        ).execute()
    except Exception as exc:  # noqa: BLE001
        if _missing_table(exc):
            return WriteClaimResult(outcome="error", reason="ledger_missing")
        logger.warning("write_idempotency_claim_failed org_id=%s error=%s", org_id, exc)
        return WriteClaimResult(outcome="error", reason="claim_failed")
    body = res.data if isinstance(res.data, dict) else {}
    outcome = str(body.get("outcome") or "error")
    if outcome == "replay":
        replay = _row_to_result(body.get("result") if isinstance(body.get("result"), dict) else None)
        if replay and replay.success:
            logger.info(
                "write_idempotency_replay org_id=%s key=%s action=%s",
                org_id,
                idempotency_key[:16],
                replay.action,
            )
            return WriteClaimResult(outcome="replay", status="completed", replay=replay)
        return WriteClaimResult(outcome="blocked", status="completed", reason="invalid_replay_payload")
    if outcome == "claimed":
        token = str(body.get("claim_token") or "") or None
        if not token:
            logger.warning("write_idempotency_claim_missing_token org_id=%s key=%s", org_id, idempotency_key[:16])
            return WriteClaimResult(outcome="error", reason="missing_claim_token")
        generation_raw = body.get("claim_generation")
        generation = int(generation_raw) if generation_raw is not None else None
        return WriteClaimResult(
            outcome="claimed",
            status="in_progress",
            claim_token=token,
            claim_generation=generation,
        )
    return WriteClaimResult(
        outcome="blocked",
        status=str(body.get("status") or ""),
        reason=str(body.get("reason") or outcome),
    )


def finalize_write_invoke(
    client: Any,
    *,
    org_id: str,
    idempotency_key: str,
    claim_token: str | None,
    status: Literal["completed", "failed", "uncertain"],
    result: NormalizedResult | None = None,
) -> WriteFinalizeResult:
    if not claim_token:
        logger.warning(
            "write_idempotency_finalize_missing_token org_id=%s key=%s status=%s",
            org_id,
            idempotency_key[:16],
            status,
        )
        return WriteFinalizeResult(outcome="rejected", reason="missing_claim_token")
    payload: dict[str, Any] = {}
    if result is not None:
        payload = {
            "success": result.success,
            "action": result.action,
            "data": result.data,
            "error_code": result.error_code,
            "error_message": result.error_message,
            "connector_id": result.connector_id,
            "latency_ms": result.latency_ms,
        }
    try:
        res = client.rpc(
            "finalize_write_invoke_idempotency",
            {
                "p_org_id": org_id,
                "p_key": idempotency_key,
                "p_claim_token": claim_token,
                "p_status": status,
                "p_result": payload,
            },
        ).execute()
    except Exception as exc:  # noqa: BLE001
        if _missing_table(exc):
            return WriteFinalizeResult(outcome="error", reason="ledger_missing")
        logger.warning(
            "write_idempotency_finalize_failed org_id=%s key=%s status=%s error=%s",
            org_id,
            idempotency_key[:16],
            status,
            exc,
        )
        return WriteFinalizeResult(outcome="error", reason="finalize_failed")
    body = res.data if isinstance(res.data, dict) else {}
    outcome = str(body.get("outcome") or "error")
    if outcome == "finalized":
        return WriteFinalizeResult(outcome="finalized")
    return WriteFinalizeResult(outcome="rejected", reason=str(body.get("reason") or outcome))


def inject_provider_idempotency(params: dict[str, Any], idempotency_key: str) -> dict[str, Any]:
    out = dict(params)
    out.setdefault("_gravitre_idempotency_key", idempotency_key)
    return out


class WriteIdempotencyUnavailable(ToolError):
    code = "write_idempotency_unavailable"
