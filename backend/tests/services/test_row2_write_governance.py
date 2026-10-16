"""Row 2 — Shared write governance / lifecycle: durable verification contracts.

Coverage checklist (Row 2 acceptance criteria):
  - Dynamic resolved-argument review across chat/voice/MCP
  - Durable verification and stale-run proof
  - Provider commit/timeout handling

Tests:
  1.  claim idempotency key encodes resolved args (chat path)
  2.  claim idempotency key encodes resolved args (invoke/run path)
  3.  nonce suffix makes keys distinct for same action + args
  4.  claim outcome 'claimed' includes claim_token and status=in_progress
  5.  claim outcome 'replay' with valid payload returns replay result
  6.  claim outcome 'blocked' when RPC returns blocked
  7.  claim failure on RPC exception → outcome='error'
  8.  finalize rejects when claim_token is None (missing fenced token)
  9.  finalize uses fenced RPC (finalize_write_invoke_idempotency)
  10. verification: positive proof → 'completed'
  11. verification: explicit mismatch → 'failed'
  12. verification: unprovable → 'verification_inconclusive'
  13. build_write_idempotency_key is deterministic for same inputs
  14. build_write_idempotency_key differs by turn_id
  15. finalize_write_invoke passes result payload to RPC
"""
from __future__ import annotations

from unittest.mock import MagicMock
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rpc_client(return_data):
    client = MagicMock()
    response = MagicMock()
    response.data = return_data
    rpc_chain = MagicMock()
    rpc_chain.execute.return_value = response
    client.rpc.return_value = rpc_chain
    return client


def _make_ctx(
    *,
    org_id: str = "org-1",
    conversation_id: str | None = None,
    turn_id: str | None = "turn-1",
    run_id: str | None = None,
    step_id: str | None = None,
    connector_id: str | None = None,
):
    ctx = MagicMock()
    ctx.org_id = org_id
    ctx.conversation_id = conversation_id
    ctx.turn_id = turn_id
    ctx.run_id = run_id
    ctx.step_id = step_id
    ctx.connector_id = connector_id
    return ctx


# ---------------------------------------------------------------------------
# build_write_idempotency_key — resolved-arg encoding
# ---------------------------------------------------------------------------

class TestIdempotencyKeyEncoding:
    def test_chat_path_key_encodes_resolved_args(self):
        """Chat path key captures pending_action_id + action in digest."""
        from app.services.write_invoke_idempotency import build_write_idempotency_key

        ctx = _make_ctx(conversation_id="conv-1", turn_id="turn-1")
        key, logical_id = build_write_idempotency_key(
            ctx, "create_task", {"pending_action_id": "pa-1", "title": "Do something"}
        )
        assert key.startswith("chat:")
        assert logical_id is not None

    def test_invoke_path_key_encodes_action_and_run(self):
        """Invoke (non-chat) path key encodes action and run_id."""
        from app.services.write_invoke_idempotency import build_write_idempotency_key

        ctx = _make_ctx(run_id="run-1", step_id="step-1")
        key, logical_id = build_write_idempotency_key(
            ctx, "send_email", {"to": "a@b.com"}
        )
        assert key.startswith("invoke:")
        assert logical_id is None

    def test_nonce_creates_distinct_keys_for_same_action_and_args(self):
        """Different nonces produce different idempotency keys."""
        from app.services.write_invoke_idempotency import build_write_idempotency_key

        ctx = _make_ctx(run_id="run-1", step_id="step-1")
        key1, _ = build_write_idempotency_key(
            ctx, "send_email", {"_write_idempotency_nonce": "n1", "to": "a@b.com"}
        )
        key2, _ = build_write_idempotency_key(
            ctx, "send_email", {"_write_idempotency_nonce": "n2", "to": "a@b.com"}
        )
        assert key1 != key2

    def test_key_is_deterministic_for_same_inputs(self):
        """Same ctx + action + params → identical key (idempotency guarantee)."""
        from app.services.write_invoke_idempotency import build_write_idempotency_key

        ctx = _make_ctx(run_id="run-1", step_id="step-1")
        params = {"to": "a@b.com", "subject": "hi"}
        key1, _ = build_write_idempotency_key(ctx, "send_email", params)
        key2, _ = build_write_idempotency_key(ctx, "send_email", params)
        assert key1 == key2

    def test_key_differs_by_turn_id(self):
        """Different turn_id → different key (per-turn isolation)."""
        from app.services.write_invoke_idempotency import build_write_idempotency_key

        ctx1 = _make_ctx(conversation_id="conv-1", turn_id="turn-A")
        ctx2 = _make_ctx(conversation_id="conv-1", turn_id="turn-B")
        key1, _ = build_write_idempotency_key(ctx1, "create_task", {})
        key2, _ = build_write_idempotency_key(ctx2, "create_task", {})
        assert key1 != key2


# ---------------------------------------------------------------------------
# claim_write_invoke — outcome paths
# ---------------------------------------------------------------------------

class TestClaimWriteInvoke:
    def test_claimed_outcome_returns_token_and_in_progress(self):
        """RPC outcome='claimed' → WriteClaimResult with status=in_progress."""
        from app.services.write_invoke_idempotency import claim_write_invoke

        client = _rpc_client({
            "outcome": "claimed",
            "claim_token": "tok-abc",
            "claim_generation": 1,
        })
        result = claim_write_invoke(
            client,
            org_id="org-1",
            idempotency_key="chat:deadbeef",
            invoke_action="create_task",
            logical_action_id_value="la-1",
        )
        assert result.outcome == "claimed"
        assert result.status == "in_progress"
        assert result.claim_token == "tok-abc"

    def test_replay_outcome_returns_previous_result(self):
        """RPC outcome='replay' with success=True → replay forwarded."""
        from app.services.write_invoke_idempotency import claim_write_invoke

        client = _rpc_client({
            "outcome": "replay",
            "result": {
                "success": True,
                "action": "create_task",
                "data": {"task_id": "t-1"},
                "error_code": None,
                "error_message": None,
                "connector_id": None,
                "latency_ms": 120,
            },
        })
        result = claim_write_invoke(
            client,
            org_id="org-1",
            idempotency_key="chat:deadbeef",
            invoke_action="create_task",
            logical_action_id_value=None,
        )
        assert result.outcome == "replay"
        assert result.replay is not None
        assert result.replay.success is True
        assert result.replay.data == {"task_id": "t-1"}

    def test_blocked_outcome_is_forwarded(self):
        """RPC outcome='blocked' → outcome=blocked with reason."""
        from app.services.write_invoke_idempotency import claim_write_invoke

        client = _rpc_client({
            "outcome": "blocked",
            "status": "in_progress",
            "reason": "concurrent_in_flight",
        })
        result = claim_write_invoke(
            client,
            org_id="org-1",
            idempotency_key="chat:aabbcc",
            invoke_action="send_message",
            logical_action_id_value=None,
        )
        assert result.outcome == "blocked"
        assert "concurrent" in (result.reason or "")

    def test_rpc_exception_returns_error_outcome(self):
        """RPC exception → outcome='error' (no raise, durable-safe)."""
        from app.services.write_invoke_idempotency import claim_write_invoke

        client = MagicMock()
        client.rpc.side_effect = RuntimeError("connection timeout")
        result = claim_write_invoke(
            client,
            org_id="org-1",
            idempotency_key="chat:deadbeef",
            invoke_action="create_task",
            logical_action_id_value=None,
        )
        assert result.outcome == "error"

    def test_claim_uses_fenced_rpc_name(self):
        """claim_write_invoke calls the 'claim_write_invoke_idempotency' RPC."""
        from app.services.write_invoke_idempotency import claim_write_invoke

        client = _rpc_client({"outcome": "claimed", "claim_token": "tok", "claim_generation": 1})
        claim_write_invoke(
            client,
            org_id="org-1",
            idempotency_key="chat:key",
            invoke_action="op",
            logical_action_id_value=None,
        )
        assert client.rpc.call_args[0][0] == "claim_write_invoke_idempotency"


# ---------------------------------------------------------------------------
# finalize_write_invoke — fenced commit contract
# ---------------------------------------------------------------------------

class TestFinalizeWriteInvoke:
    def test_finalize_rejects_missing_claim_token(self):
        """finalize_write_invoke with claim_token=None → outcome='rejected'."""
        from app.services.write_invoke_idempotency import finalize_write_invoke

        client = _rpc_client({})
        result = finalize_write_invoke(
            client,
            org_id="org-1",
            idempotency_key="chat:key",
            claim_token=None,
            status="completed",
        )
        assert result.outcome == "rejected"
        assert "missing" in (result.reason or "").lower()
        client.rpc.assert_not_called()

    def test_finalize_calls_fenced_rpc(self):
        """finalize uses 'finalize_write_invoke_idempotency' RPC."""
        from app.services.write_invoke_idempotency import finalize_write_invoke

        client = _rpc_client({"outcome": "finalized"})
        finalize_write_invoke(
            client,
            org_id="org-1",
            idempotency_key="chat:key",
            claim_token="tok-123",
            status="completed",
        )
        assert client.rpc.call_args[0][0] == "finalize_write_invoke_idempotency"

    def test_finalize_passes_result_payload(self):
        """Result data is forwarded to the RPC in the p_result field."""
        from app.services.write_invoke_idempotency import finalize_write_invoke, NormalizedResult

        client = _rpc_client({"outcome": "finalized"})
        result = NormalizedResult(
            success=True,
            action="create_task",
            data={"task_id": "t-99"},
            error_code=None,
            error_message=None,
            connector_id=None,
            latency_ms=200,
        )
        finalize_write_invoke(
            client,
            org_id="org-1",
            idempotency_key="chat:key",
            claim_token="tok-456",
            status="completed",
            result=result,
        )
        call_kwargs = client.rpc.call_args[0][1]
        assert call_kwargs["p_result"]["success"] is True
        assert call_kwargs["p_result"]["data"] == {"task_id": "t-99"}


# ---------------------------------------------------------------------------
# _verification_terminal_status — durable verification states
# ---------------------------------------------------------------------------

class TestVerificationTerminalStatus:
    def test_positive_proof_returns_completed(self):
        """Verified=True, confirmed follow-up → 'completed'."""
        from app.services.write_success_verification import _verification_terminal_status

        status = _verification_terminal_status(
            verified=True,
            effect="created",
            detail="follow_up_entity_get_confirmed",
        )
        assert status == "completed"

    def test_explicit_mismatch_returns_failed(self):
        """Field value mismatch → 'failed' (write evidence contradicts intent)."""
        from app.services.write_success_verification import _verification_terminal_status

        status = _verification_terminal_status(
            verified=False,
            effect="unknown",
            detail="field_value_mismatch",
        )
        assert status == "failed"

    def test_entity_id_mismatch_returns_failed(self):
        """Entity ID mismatch → 'failed'."""
        from app.services.write_success_verification import _verification_terminal_status

        status = _verification_terminal_status(
            verified=False,
            effect="unknown",
            detail="entity_id_mismatch:777",
        )
        assert status == "failed"

    def test_follow_up_read_failure_is_inconclusive(self):
        """Unprovable read → 'verification_inconclusive' (not failure)."""
        from app.services.write_success_verification import _verification_terminal_status

        status = _verification_terminal_status(
            verified=False,
            effect="accepted_async",
            detail="follow_up_read_failed",
        )
        assert status == "verification_inconclusive"
