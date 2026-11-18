"""Explicit, fail-closed recovery of an uncertain provider write.

Recovery is a separate operator/worker action, never an implicit retry in
invoke_tool. Readback must be performed using the original connector context.
The database CAS transition prevents concurrent recovery workers from
overwriting a newly changed ledger state.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from app.services.outcome_reconciliation import reconcile_uncertain_write

RecoveryState = Literal["completed", "not_applied", "unknown", "rejected", "error"]


@dataclass(frozen=True)
class RecoveryResult:
    state: RecoveryState
    detail: str


def recover_uncertain_write(
    *,
    ctx: Any,
    idempotency_key: str,
    invoke_action: str,
    original_args: dict[str, Any],
) -> RecoveryResult:
    """Read provider state and durably settle one *already uncertain* claim.

    This does not dispatch a write. A verified absence moves the claim to
    failed, where a subsequent *separately authorized* invocation can claim
    it. An inconclusive read leaves the claim uncertain and blocked.
    """
    if not idempotency_key or not invoke_action or not isinstance(original_args, dict):
        return RecoveryResult("rejected", "missing_recovery_identity")
    if not getattr(ctx, "org_id", None) or getattr(ctx, "client", None) is None:
        return RecoveryResult("rejected", "missing_tenant_or_ledger")
    try:
        response = (
            ctx.client.table("write_invoke_idempotency")
            .select("*")
            .eq("org_id", ctx.org_id)
            .eq("idempotency_key", idempotency_key)
            .limit(1)
            .execute()
        )
        rows = response.data if isinstance(response.data, list) else []
        if len(rows) != 1 or rows[0].get("status") != "uncertain":
            return RecoveryResult("rejected", "ledger_not_uncertain")
        if rows[0].get("invoke_action") != invoke_action:
            return RecoveryResult("rejected", "action_mismatch")
        # Until the ledger durably records the original request payload and
        # connector identity, recovery must not trust caller-supplied arguments.
        # A guessed natural key could otherwise certify an unrelated record.
        stored_args = rows[0].get("original_args")
        stored_connector = rows[0].get("connector_id")
        if not isinstance(stored_args, dict) or not stored_connector:
            return RecoveryResult("unknown", "persisted_recovery_context_missing")
        if stored_args != original_args:
            return RecoveryResult("rejected", "original_arguments_mismatch")
        if str(stored_connector) != str(getattr(ctx, "connector_id", "") or ""):
            return RecoveryResult("rejected", "connector_identity_mismatch")
    except Exception:
        return RecoveryResult("error", "ledger_read_unavailable")

    observed = reconcile_uncertain_write(
        ctx=ctx, invoke_action=invoke_action, args=original_args,
    )
    if observed.state == "unknown":
        return RecoveryResult("unknown", observed.detail)

    status = "completed" if observed.state == "applied" else "failed"
    # Never fabricate a replayable completed result: only a provider-backed
    # verified receipt may be replayed. Absent receipts remain uncertain.
    if status == "completed":
        if not observed.evidence.get("verified"):
            return RecoveryResult("unknown", "provider_evidence_not_verified")
        payload = {
            "success": True,
            "action": invoke_action,
            "data": {"id": observed.resource_id} if observed.resource_id else {},
            "verification": observed.as_dict(),
        }
    else:
        # A negative result is actionable only when the read is authoritative.
        # In particular, list pagination and unsupported action shapes cannot
        # establish absence.
        if observed.detail not in ("requested_values_absent",) and not observed.detail.startswith("no_record_with_"):
            return RecoveryResult("unknown", "absence_not_authoritative")
        payload = {
            "success": False, "action": invoke_action,
            "error_code": "provider_effect_not_applied",
            "verification": observed.as_dict(),
        }
    try:
        res = ctx.client.rpc("reconcile_write_invoke_idempotency", {
            "p_org_id": ctx.org_id,
            "p_key": idempotency_key,
            "p_status": status,
            "p_result": payload,
        }).execute()
        body = res.data if isinstance(res.data, dict) else {}
        if body.get("outcome") != "reconciled":
            return RecoveryResult("rejected", str(body.get("reason") or "ledger_state_changed"))
        return RecoveryResult("completed" if status == "completed" else "not_applied", observed.detail)
    except Exception:
        return RecoveryResult("error", "ledger_reconciliation_unavailable")
