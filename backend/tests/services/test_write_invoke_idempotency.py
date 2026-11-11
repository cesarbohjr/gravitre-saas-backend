from types import SimpleNamespace
from unittest.mock import MagicMock

from app.services.tool_types import NormalizedResult, ToolContext
from app.services.write_invoke_idempotency import (
    WriteClaimResult,
    build_write_idempotency_key,
    claim_write_invoke,
    finalize_write_invoke,
)


def test_build_key_differs_by_turn_id():
    base = dict(
        settings=SimpleNamespace(),
        client=MagicMock(),
        org_id="org-1",
        actor_id="u1",
        conversation_id="conv-1",
    )
    ctx_a = ToolContext(**base, turn_id="turn-1")
    ctx_b = ToolContext(**{**base, "turn_id": "turn-2"})
    params = {"pending_action_id": "pa-1", "email": "a@example.com"}
    ka, _ = build_write_idempotency_key(ctx_a, "gmail.messages.send", params)
    kb, _ = build_write_idempotency_key(ctx_b, "gmail.messages.send", params)
    assert ka != kb


def test_build_key_nonce_allows_intentional_repeat():
    ctx = ToolContext(
        settings=SimpleNamespace(),
        client=MagicMock(),
        org_id="org-1",
        actor_id="u1",
        conversation_id="conv-1",
        turn_id="turn-1",
    )
    params = {"pending_action_id": "pa-1", "_write_idempotency_nonce": "second-send"}
    k1, _ = build_write_idempotency_key(ctx, "gmail.messages.send", params)
    k2, _ = build_write_idempotency_key(
        ctx, "gmail.messages.send", {**params, "_write_idempotency_nonce": "third-send"}
    )
    assert k1 != k2


def test_claim_replay_from_rpc():
    client = MagicMock()
    client.rpc.return_value.execute.return_value.data = {
        "outcome": "replay",
        "status": "completed",
        "result": {"success": True, "action": "hubspot.contacts.update", "data": {"id": "1"}},
    }
    out = claim_write_invoke(
        client,
        org_id="org-1",
        idempotency_key="invoke:abc",
        invoke_action="hubspot.contacts.update",
        logical_action_id_value=None,
    )
    assert isinstance(out, WriteClaimResult)
    assert out.outcome == "replay" and out.replay is not None and out.replay.success


def test_finalize_uses_fenced_rpc():
    client = MagicMock()
    client.rpc.return_value.execute.return_value.data = {"outcome": "finalized"}
    out = finalize_write_invoke(
        client,
        org_id="org-1",
        idempotency_key="invoke:abc",
        claim_token="11111111-1111-4111-8111-111111111111",
        status="completed",
        result=NormalizedResult(success=True, action="hubspot.contacts.update", data={"id": "1"}),
    )
    assert out.outcome == "finalized"
    client.rpc.assert_called_once()
    assert client.rpc.call_args[0][0] == "finalize_write_invoke_idempotency"


def test_finalize_rejects_missing_token():
    client = MagicMock()
    out = finalize_write_invoke(
        client,
        org_id="org-1",
        idempotency_key="invoke:abc",
        claim_token=None,
        status="failed",
    )
    assert out.outcome == "rejected"
    client.rpc.assert_not_called()


def test_claim_fails_closed_without_fencing_token():
    client = MagicMock()
    client.rpc.return_value.execute.return_value.data = {
        "outcome": "claimed", "status": "in_progress", "claim_generation": 1,
    }
    out = claim_write_invoke(
        client,
        org_id="org-1",
        idempotency_key="invoke:abc",
        invoke_action="hubspot.contacts.update",
        logical_action_id_value=None,
    )
    assert out.outcome == "error"
    assert out.reason == "missing_claim_token"
    assert out.claim_token is None
    client.rpc.assert_called_once()


def test_queue_approval_id_is_stable_ledger_identity_and_separates_distinct_approvals():
    """Two intentional identical writes cannot share an approval's ledger key."""
    ctx = dict(
        settings=SimpleNamespace(),
        client=MagicMock(),
        org_id="org-1",
        actor_id="requester-1",
        conversation_id="conv-1",
        write_idempotency_required=True,
    )
    params = {"email": "qa@example.invalid", "subject": "Approved", "body": "Fixture"}
    first = ToolContext(**ctx, turn_id="approval-1")
    second = ToolContext(**ctx, turn_id="approval-2")
    k1, logical1 = build_write_idempotency_key(first, "gmail.messages.send", params)
    replay, logical_replay = build_write_idempotency_key(first, "gmail.messages.send", dict(params))
    k2, logical2 = build_write_idempotency_key(second, "gmail.messages.send", params)
    assert k1.startswith("chat:") and k1 == replay
    assert logical1 == logical_replay
    assert k1 != k2 and logical1 != logical2


def test_queue_approved_unknown_write_classification_fails_closed():
    import pytest
    from app.services.tool_service import assert_queue_write_ledger_classified
    from app.services.tool_types import ToolValidationError

    ctx = ToolContext(
        settings=SimpleNamespace(),
        client=MagicMock(),
        org_id="org-1",
        actor_id="reviewer-1",
        write_idempotency_required=True,
    )
    with pytest.raises(ToolValidationError) as exc:
        assert_queue_write_ledger_classified(ctx, "qa.nonexistent_action")
    assert exc.value.code == "WRITE_LEDGER_CLASSIFICATION_REQUIRED"

    permissive_ctx = ToolContext(
        settings=SimpleNamespace(),
        client=MagicMock(),
        org_id="org-1",
        actor_id="reviewer-1",
    )
    assert_queue_write_ledger_classified(permissive_ctx, "qa.nonexistent_action") is None


def test_queued_approval_ledger_identity_is_tenant_and_arguments_bound():
    """Queued approvals must not alias across tenants or changed provider payloads."""
    base = {
        "settings": SimpleNamespace(),
        "client": MagicMock(),
        "actor_id": "requester-1",
        "conversation_id": "conv-1",
        "turn_id": "approval-1",
        "write_idempotency_required": True,
    }
    first = ToolContext(**base, org_id="org-one")
    foreign = ToolContext(**base, org_id="org-two")
    action = "hubspot.contacts.create"
    args = {"email": "pr611-qa@example.invalid", "firstname": "Original"}
    initial_key, initial_logical = build_write_idempotency_key(first, action, args)
    foreign_key, foreign_logical = build_write_idempotency_key(foreign, action, args)
    changed_key, changed_logical = build_write_idempotency_key(
        first, action, {**args, "firstname": "Tampered"}
    )
    assert initial_key != foreign_key
    assert initial_logical != foreign_logical
    assert initial_key != changed_key
    assert initial_logical != changed_logical


def test_canonical_ledger_claim_error_fails_closed():
    """A missing or unavailable ledger must not be silently treated as a claim."""
    client = MagicMock()
    client.rpc.side_effect = RuntimeError("write_invoke_idempotency unavailable")
    claim = claim_write_invoke(
        client,
        org_id="org-one",
        idempotency_key="chat:approval-1",
        invoke_action="hubspot.contacts.create",
        logical_action_id_value="logical-1",
    )
    assert claim.outcome == "error"
    assert claim.claim_token is None
    client.rpc.assert_called_once()


def test_queued_write_provider_success_with_uncommitted_ledger_is_uncertain():
    """A provider success is not certified if the canonical ledger cannot finalize."""
    from contextlib import ExitStack
    from unittest.mock import patch

    from app.services import tool_service
    from app.services.write_authority import write_authority
    from app.services.write_invoke_idempotency import WriteFinalizeResult

    action = "hubspot.contacts.update"
    provider_calls = []

    def fake_provider(ctx, params):
        provider_calls.append((ctx.turn_id, params.get("id")))
        return NormalizedResult(
            success=True, action=action, data={"id": "isolated-contact"},
        )

    ctx = ToolContext(
        settings=SimpleNamespace(
            write_authority_mode="enforce",
            write_invoke_idempotency_enabled=False,
            private_connector_runtime_enabled=False,
        ),
        client=MagicMock(),
        org_id="org-qa",
        actor_id="member-qa",
        conversation_id="conv-qa",
        turn_id="approved-queue-id",
        write_idempotency_required=True,
    )
    with ExitStack() as stack:
        stack.enter_context(patch("app.services.capability_availability.is_capability_action", return_value=False))
        stack.enter_context(patch("app.capability_ontology.resolver.resolve_capability_invoke_action", return_value=None))
        stack.enter_context(patch("app.services.conversation_write_guard.assert_org_write_allowed"))
        stack.enter_context(patch("app.services.write_preflight.enforce_invoke_write_preflight", side_effect=lambda c, a, p: p))
        stack.enter_context(patch.object(tool_service, "_resolve_tool_executor", return_value=fake_provider))
        stack.enter_context(patch("app.services.hipaa_service.enforce_hipaa_for_tool_invoke"))
        stack.enter_context(patch("app.services.agent_guardrail_limits.enforce_agent_guardrail_limits"))
        stack.enter_context(patch.object(tool_service, "assert_agent_tool_permission"))
        stack.enter_context(patch.object(tool_service, "_write_tool_audit"))
        stack.enter_context(patch("app.workers.workflow_queue.assert_current_workflow_claim_live"))
        claim = stack.enter_context(patch(
            "app.services.write_invoke_idempotency.claim_write_invoke",
            return_value=WriteClaimResult(outcome="claimed", claim_token="qa-claim"),
        ))
        finalize = stack.enter_context(patch(
            "app.services.write_invoke_idempotency.finalize_write_invoke",
            return_value=WriteFinalizeResult(outcome="error", reason="finalize_failed"),
        ))
        with write_authority("human", "approval:approved-queue-id"):
            result = tool_service.invoke_tool(ctx, action, {"id": "isolated-contact"})
    assert provider_calls == [("approved-queue-id", "isolated-contact")]
    claim.assert_called_once()
    assert claim.call_args.kwargs["org_id"] == "org-qa"
    assert claim.call_args.kwargs["invoke_action"] == action
    finalize.assert_called_once()
    assert finalize.call_args.kwargs["status"] == "completed"
    assert result.success is False
    assert result.error_code == "outcome_uncertain"
    assert "reconcile" in result.error_message.lower()


def test_eco001_pre_provider_ownership_rejection_finalizes_claim_and_blocks_dispatch():
    """Focused regression; independent PostgreSQL/provider acceptance remains separate."""
    import pytest
    from contextlib import ExitStack
    from unittest.mock import patch
    from app.services import tool_service
    from app.services.write_authority import write_authority
    from app.services.write_invoke_idempotency import WriteFinalizeResult

    action = "hubspot.contacts.update"
    provider = MagicMock(return_value=NormalizedResult(success=True, action=action, data={"id": "1"}))
    ctx = ToolContext(
        settings=SimpleNamespace(
            write_authority_mode="enforce",
            write_invoke_idempotency_enabled=False,
            private_connector_runtime_enabled=False,
        ),
        client=MagicMock(), org_id="org-qa", actor_id="member-qa",
        conversation_id="conv-qa", turn_id="approved-queue-id",
        write_idempotency_required=True,
    )
    with ExitStack() as stack:
        stack.enter_context(patch("app.services.capability_availability.is_capability_action", return_value=False))
        stack.enter_context(patch("app.capability_ontology.resolver.resolve_capability_invoke_action", return_value=None))
        stack.enter_context(patch("app.services.conversation_write_guard.assert_org_write_allowed"))
        stack.enter_context(patch("app.services.write_preflight.enforce_invoke_write_preflight", side_effect=lambda c, a, p: p))
        stack.enter_context(patch.object(tool_service, "_resolve_tool_executor", return_value=provider))
        stack.enter_context(patch("app.services.hipaa_service.enforce_hipaa_for_tool_invoke"))
        stack.enter_context(patch("app.services.agent_guardrail_limits.enforce_agent_guardrail_limits"))
        stack.enter_context(patch.object(tool_service, "assert_agent_tool_permission"))
        stack.enter_context(patch.object(tool_service, "_write_tool_audit"))
        stack.enter_context(patch(
            "app.workers.workflow_queue.assert_current_workflow_claim_live",
            side_effect=RuntimeError("workflow lease revoked"),
        ))
        claim = stack.enter_context(patch(
            "app.services.write_invoke_idempotency.claim_write_invoke",
            return_value=WriteClaimResult(outcome="claimed", claim_token="qa-claim"),
        ))
        finalize = stack.enter_context(patch(
            "app.services.write_invoke_idempotency.finalize_write_invoke",
            return_value=WriteFinalizeResult(outcome="finalized"),
        ))
        with write_authority("human", "approval:approved-queue-id"):
            result = tool_service.invoke_tool(ctx, action, {"id": "isolated-contact"})
    claim.assert_called_once()
    provider.assert_not_called()
    finalize.assert_called_once()
    assert finalize.call_args.kwargs["status"] == "failed"
    assert result.success is False


def test_eco001_pre_provider_ownership_rejection_with_unconfirmed_finalization_fails_closed():
    """Focused regression; independent PostgreSQL/provider acceptance remains separate."""
    import pytest
    from contextlib import ExitStack
    from unittest.mock import patch
    from app.services import tool_service
    from app.services.write_authority import write_authority
    from app.services.write_invoke_idempotency import WriteFinalizeResult, WriteIdempotencyUnavailable

    action = "hubspot.contacts.update"
    provider = MagicMock(return_value=NormalizedResult(success=True, action=action, data={"id": "1"}))
    ctx = ToolContext(
        settings=SimpleNamespace(
            write_authority_mode="enforce",
            write_invoke_idempotency_enabled=False,
            private_connector_runtime_enabled=False,
        ),
        client=MagicMock(), org_id="org-qa", actor_id="member-qa",
        conversation_id="conv-qa", turn_id="approved-queue-id",
        write_idempotency_required=True,
    )
    with ExitStack() as stack:
        stack.enter_context(patch("app.services.capability_availability.is_capability_action", return_value=False))
        stack.enter_context(patch("app.capability_ontology.resolver.resolve_capability_invoke_action", return_value=None))
        stack.enter_context(patch("app.services.conversation_write_guard.assert_org_write_allowed"))
        stack.enter_context(patch("app.services.write_preflight.enforce_invoke_write_preflight", side_effect=lambda c, a, p: p))
        stack.enter_context(patch.object(tool_service, "_resolve_tool_executor", return_value=provider))
        stack.enter_context(patch("app.services.hipaa_service.enforce_hipaa_for_tool_invoke"))
        stack.enter_context(patch("app.services.agent_guardrail_limits.enforce_agent_guardrail_limits"))
        stack.enter_context(patch.object(tool_service, "assert_agent_tool_permission"))
        stack.enter_context(patch.object(tool_service, "_write_tool_audit"))
        stack.enter_context(patch(
            "app.workers.workflow_queue.assert_current_workflow_claim_live",
            side_effect=RuntimeError("workflow lease revoked"),
        ))
        claim = stack.enter_context(patch(
            "app.services.write_invoke_idempotency.claim_write_invoke",
            return_value=WriteClaimResult(outcome="claimed", claim_token="qa-claim"),
        ))
        finalize = stack.enter_context(patch(
            "app.services.write_invoke_idempotency.finalize_write_invoke",
            return_value=WriteFinalizeResult(outcome="error", reason="ledger_unavailable"),
        ))
        with write_authority("human", "approval:approved-queue-id"):
            with pytest.raises(WriteIdempotencyUnavailable) as raised:
                tool_service.invoke_tool(ctx, action, {"id": "isolated-contact"})
    claim.assert_called_once()
    provider.assert_not_called()
    finalize.assert_called_once()
    assert finalize.call_args.kwargs["status"] == "failed"
    assert "reconciliation" in str(raised.value).lower()


def test_eco001_pre_provider_approval_revocation_finalizes_claim_without_dispatch():
    """Focused regression; independent PostgreSQL/provider acceptance remains separate."""
    import pytest
    from contextlib import ExitStack
    from unittest.mock import patch
    from app.services import tool_service
    from app.services.write_authority import write_authority
    from app.services.write_invoke_idempotency import WriteFinalizeResult

    action = "hubspot.contacts.update"
    provider = MagicMock(return_value=NormalizedResult(success=True, action=action, data={"id": "1"}))
    ctx = ToolContext(
        settings=SimpleNamespace(
            write_authority_mode="enforce",
            write_invoke_idempotency_enabled=False,
            private_connector_runtime_enabled=False,
        ),
        client=MagicMock(), org_id="org-qa", actor_id="member-qa",
        conversation_id="conv-qa", turn_id="approved-queue-id",
        write_idempotency_required=True,
    )
    with ExitStack() as stack:
        stack.enter_context(patch("app.services.capability_availability.is_capability_action", return_value=False))
        stack.enter_context(patch("app.capability_ontology.resolver.resolve_capability_invoke_action", return_value=None))
        stack.enter_context(patch("app.services.conversation_write_guard.assert_org_write_allowed"))
        stack.enter_context(patch("app.services.write_preflight.enforce_invoke_write_preflight", side_effect=lambda c, a, p: p))
        stack.enter_context(patch.object(tool_service, "_resolve_tool_executor", return_value=provider))
        stack.enter_context(patch("app.services.hipaa_service.enforce_hipaa_for_tool_invoke"))
        stack.enter_context(patch("app.services.agent_guardrail_limits.enforce_agent_guardrail_limits"))
        stack.enter_context(patch.object(tool_service, "assert_agent_tool_permission"))
        stack.enter_context(patch.object(tool_service, "_write_tool_audit"))
        stack.enter_context(patch("app.workers.workflow_queue.assert_current_workflow_claim_live"))
        ctx.autonomous_write_guarded = True
        ctx.run_id = "run-qa"
        approval_check = stack.enter_context(patch(
            "app.services.canvas_write_gate.require_approved_authority_run",
            side_effect=[{"approved": True}, {"approved": True}, RuntimeError("approval revoked")],
        ))
        claim = stack.enter_context(patch(
            "app.services.write_invoke_idempotency.claim_approved_autonomous_write",
            return_value=WriteClaimResult(outcome="claimed", claim_token="qa-claim"),
        ))
        finalize = stack.enter_context(patch(
            "app.services.write_invoke_idempotency.finalize_write_invoke",
            return_value=WriteFinalizeResult(outcome="finalized"),
        ))
        with write_authority("run", "run-qa"):
            result = tool_service.invoke_tool(ctx, action, {"id": "isolated-contact"})
    assert approval_check.call_count >= 2
    claim.assert_called_once()
    provider.assert_not_called()
    finalize.assert_called_once()
    assert finalize.call_args.kwargs["status"] == "failed"
    assert result.success is False




def test_eco001_provider_returned_failure_is_uncertain_and_claim_fenced():
    """Focused regression; independent PostgreSQL/provider acceptance remains separate."""
    import pytest
    from contextlib import ExitStack
    from unittest.mock import patch
    from app.services import tool_service
    from app.services.write_authority import write_authority
    from app.services.write_invoke_idempotency import WriteFinalizeResult

    action = "hubspot.contacts.update"
    provider = MagicMock(return_value=NormalizedResult(success=False, action=action, error_code="provider_rejected", error_message="failed"))
    ctx = ToolContext(
        settings=SimpleNamespace(
            write_authority_mode="enforce",
            write_invoke_idempotency_enabled=False,
            private_connector_runtime_enabled=False,
        ),
        client=MagicMock(), org_id="org-qa", actor_id="member-qa",
        conversation_id="conv-qa", turn_id="approved-queue-id",
        write_idempotency_required=True,
    )
    with ExitStack() as stack:
        stack.enter_context(patch("app.services.capability_availability.is_capability_action", return_value=False))
        stack.enter_context(patch("app.capability_ontology.resolver.resolve_capability_invoke_action", return_value=None))
        stack.enter_context(patch("app.services.conversation_write_guard.assert_org_write_allowed"))
        stack.enter_context(patch("app.services.write_preflight.enforce_invoke_write_preflight", side_effect=lambda c, a, p: p))
        stack.enter_context(patch.object(tool_service, "_resolve_tool_executor", return_value=provider))
        stack.enter_context(patch("app.services.hipaa_service.enforce_hipaa_for_tool_invoke"))
        stack.enter_context(patch("app.services.agent_guardrail_limits.enforce_agent_guardrail_limits"))
        stack.enter_context(patch.object(tool_service, "assert_agent_tool_permission"))
        stack.enter_context(patch.object(tool_service, "_write_tool_audit"))
        stack.enter_context(patch("app.workers.workflow_queue.assert_current_workflow_claim_live"))
        claim = stack.enter_context(patch(
            "app.services.write_invoke_idempotency.claim_write_invoke",
            return_value=WriteClaimResult(outcome="claimed", claim_token="qa-claim"),
        ))
        finalize = stack.enter_context(patch(
            "app.services.write_invoke_idempotency.finalize_write_invoke",
            return_value=WriteFinalizeResult(outcome="finalized"),
        ))
        with write_authority("human", "approval:approved-queue-id"):
            result = tool_service.invoke_tool(ctx, action, {"id": "isolated-contact"})
    claim.assert_called_once()
    provider.assert_called_once()
    finalize.assert_called_once()
    assert finalize.call_args.kwargs["status"] == "uncertain"
    assert result.success is False
    assert result.error_code == "outcome_uncertain"
    assert "reconcile" in result.error_message.lower()




def test_eco001_cancellation_before_provider_dispatch_fences_claim():
    """Focused regression; independent PostgreSQL/provider acceptance remains separate."""
    import pytest
    from contextlib import ExitStack
    from unittest.mock import patch
    from app.services import tool_service
    from app.services.write_authority import write_authority
    from app.services.write_invoke_idempotency import WriteFinalizeResult

    action = "hubspot.contacts.update"
    provider = MagicMock(return_value=NormalizedResult(success=True, action=action, data={"id": "1"}))
    ctx = ToolContext(
        settings=SimpleNamespace(
            write_authority_mode="enforce",
            write_invoke_idempotency_enabled=False,
            private_connector_runtime_enabled=False,
        ),
        client=MagicMock(), org_id="org-qa", actor_id="member-qa",
        conversation_id="conv-qa", turn_id="approved-queue-id",
        write_idempotency_required=True,
    )
    with ExitStack() as stack:
        stack.enter_context(patch("app.services.capability_availability.is_capability_action", return_value=False))
        stack.enter_context(patch("app.capability_ontology.resolver.resolve_capability_invoke_action", return_value=None))
        stack.enter_context(patch("app.services.conversation_write_guard.assert_org_write_allowed"))
        stack.enter_context(patch("app.services.write_preflight.enforce_invoke_write_preflight", side_effect=lambda c, a, p: p))
        stack.enter_context(patch.object(tool_service, "_resolve_tool_executor", return_value=provider))
        stack.enter_context(patch("app.services.hipaa_service.enforce_hipaa_for_tool_invoke"))
        stack.enter_context(patch("app.services.agent_guardrail_limits.enforce_agent_guardrail_limits"))
        stack.enter_context(patch.object(tool_service, "assert_agent_tool_permission"))
        stack.enter_context(patch.object(tool_service, "_write_tool_audit"))
        stack.enter_context(patch("app.workers.workflow_queue.assert_current_workflow_claim_live", side_effect=RuntimeError("workflow cancelled")))
        claim = stack.enter_context(patch(
            "app.services.write_invoke_idempotency.claim_write_invoke",
            return_value=WriteClaimResult(outcome="claimed", claim_token="qa-claim"),
        ))
        finalize = stack.enter_context(patch(
            "app.services.write_invoke_idempotency.finalize_write_invoke",
            return_value=WriteFinalizeResult(outcome="finalized"),
        ))
        with write_authority("human", "approval:approved-queue-id"):
            result = tool_service.invoke_tool(ctx, action, {"id": "isolated-contact"})
    claim.assert_called_once()
    provider.assert_not_called()
    finalize.assert_called_once()
    assert finalize.call_args.kwargs["status"] == "failed"
    assert result.success is False
    assert result.error_code == "workflow_claim_lost"
    assert "ownership" in result.error_message.lower()




def test_eco001_concurrent_in_progress_claim_blocks_second_provider_dispatch():
    """Focused regression; independent PostgreSQL/provider acceptance remains separate."""
    import pytest
    from contextlib import ExitStack
    from unittest.mock import patch
    from app.services import tool_service
    from app.services.write_authority import write_authority
    from app.services.write_invoke_idempotency import WriteFinalizeResult

    action = "hubspot.contacts.update"
    provider = MagicMock(return_value=NormalizedResult(success=True, action=action, data={"id": "1"}))
    ctx = ToolContext(
        settings=SimpleNamespace(
            write_authority_mode="enforce",
            write_invoke_idempotency_enabled=False,
            private_connector_runtime_enabled=False,
        ),
        client=MagicMock(), org_id="org-qa", actor_id="member-qa",
        conversation_id="conv-qa", turn_id="approved-queue-id",
        write_idempotency_required=True,
    )
    with ExitStack() as stack:
        stack.enter_context(patch("app.services.capability_availability.is_capability_action", return_value=False))
        stack.enter_context(patch("app.capability_ontology.resolver.resolve_capability_invoke_action", return_value=None))
        stack.enter_context(patch("app.services.conversation_write_guard.assert_org_write_allowed"))
        stack.enter_context(patch("app.services.write_preflight.enforce_invoke_write_preflight", side_effect=lambda c, a, p: p))
        stack.enter_context(patch.object(tool_service, "_resolve_tool_executor", return_value=provider))
        stack.enter_context(patch("app.services.hipaa_service.enforce_hipaa_for_tool_invoke"))
        stack.enter_context(patch("app.services.agent_guardrail_limits.enforce_agent_guardrail_limits"))
        stack.enter_context(patch.object(tool_service, "assert_agent_tool_permission"))
        stack.enter_context(patch.object(tool_service, "_write_tool_audit"))
        stack.enter_context(patch("app.workers.workflow_queue.assert_current_workflow_claim_live"))
        claim = stack.enter_context(patch(
            "app.services.write_invoke_idempotency.claim_write_invoke",
            return_value=WriteClaimResult(outcome="blocked", status="in_progress", reason="already_claimed"),
        ))
        finalize = stack.enter_context(patch(
            "app.services.write_invoke_idempotency.finalize_write_invoke",
            return_value=WriteFinalizeResult(outcome="finalized"),
        ))
        with write_authority("human", "approval:approved-queue-id"):
            with pytest.raises(Exception) as raised:
                tool_service.invoke_tool(ctx, action, {"id": "isolated-contact"})
    claim.assert_called_once()
    provider.assert_not_called()
    finalize.assert_not_called()

    assert "progress" in str(raised.value).lower() or "reconciliation" in str(raised.value).lower()




def test_eco001_completed_claim_replays_without_second_provider_dispatch():
    """Focused regression; independent PostgreSQL/provider acceptance remains separate."""
    import pytest
    from contextlib import ExitStack
    from unittest.mock import patch
    from app.services import tool_service
    from app.services.write_authority import write_authority
    from app.services.write_invoke_idempotency import WriteFinalizeResult

    action = "hubspot.contacts.update"
    provider = MagicMock(return_value=NormalizedResult(success=True, action=action, data={"id": "unexpected"}))
    ctx = ToolContext(
        settings=SimpleNamespace(
            write_authority_mode="enforce",
            write_invoke_idempotency_enabled=False,
            private_connector_runtime_enabled=False,
        ),
        client=MagicMock(), org_id="org-qa", actor_id="member-qa",
        conversation_id="conv-qa", turn_id="approved-queue-id",
        write_idempotency_required=True,
    )
    with ExitStack() as stack:
        stack.enter_context(patch("app.services.capability_availability.is_capability_action", return_value=False))
        stack.enter_context(patch("app.capability_ontology.resolver.resolve_capability_invoke_action", return_value=None))
        stack.enter_context(patch("app.services.conversation_write_guard.assert_org_write_allowed"))
        stack.enter_context(patch("app.services.write_preflight.enforce_invoke_write_preflight", side_effect=lambda c, a, p: p))
        stack.enter_context(patch.object(tool_service, "_resolve_tool_executor", return_value=provider))
        stack.enter_context(patch("app.services.hipaa_service.enforce_hipaa_for_tool_invoke"))
        stack.enter_context(patch("app.services.agent_guardrail_limits.enforce_agent_guardrail_limits"))
        stack.enter_context(patch.object(tool_service, "assert_agent_tool_permission"))
        stack.enter_context(patch.object(tool_service, "_write_tool_audit"))
        stack.enter_context(patch("app.workers.workflow_queue.assert_current_workflow_claim_live"))
        claim = stack.enter_context(patch(
            "app.services.write_invoke_idempotency.claim_write_invoke",
            return_value=WriteClaimResult(outcome="replay", status="completed", replay=NormalizedResult(success=True, action=action, data={"id": "original"})),
        ))
        finalize = stack.enter_context(patch(
            "app.services.write_invoke_idempotency.finalize_write_invoke",
            return_value=WriteFinalizeResult(outcome="finalized"),
        ))
        with write_authority("human", "approval:approved-queue-id"):
            result = tool_service.invoke_tool(ctx, action, {"id": "isolated-contact"})
    claim.assert_called_once()
    provider.assert_not_called()
    finalize.assert_not_called()

    assert result.success is True
    assert result.data["id"] == "original"




