"""Tests for unified-turn live → classical ReAct fallthrough."""
from __future__ import annotations

from app.services.unified_turn_classical_fallback import (
    message_requires_classical_tool_sse,
    should_defer_unified_turn_live_to_classical,
)


def test_message_requires_classical_tool_sse_connectors():
    assert message_requires_classical_tool_sse("What connectors are connected right now?")


def test_agent_mode_pure_chat_not_deferred():
    """Connectors upgrade standard→agent; LIVE must still own greetings."""
    assert not should_defer_unified_turn_live_to_classical(
        mode_key="agent",
        outcome_kind="conversational_reply",
        message="Hey",
    )


def test_reasoning_mode_pure_chat_not_deferred():
    assert not should_defer_unified_turn_live_to_classical(
        mode_key="reasoning",
        outcome_kind="conversational_reply",
        message="hello",
    )


def test_standard_mode_pure_chat_not_deferred():
    assert not should_defer_unified_turn_live_to_classical(
        mode_key="standard",
        outcome_kind="conversational_reply",
        message="hello",
    )


def test_standard_greeting_not_deferred_when_requires_action_flag_set():
    assert not should_defer_unified_turn_live_to_classical(
        mode_key="standard",
        outcome_kind="conversational_reply",
        message="Hey",
        classification={"requires_action": True},
    )


def test_defer_connector_tool_proposal_all_modes():
    assert not should_defer_unified_turn_live_to_classical(
        mode_key="fast",
        outcome_kind="connector_tool_proposal",
        message="create an apollo contact list",
    )


def test_fast_mode_pure_chat_not_deferred():
    assert not should_defer_unified_turn_live_to_classical(
        mode_key="fast",
        outcome_kind="conversational_reply",
        message="hey there",
    )


def test_fast_mode_connector_query_deferred():
    assert should_defer_unified_turn_live_to_classical(
        mode_key="fast",
        outcome_kind="conversational_reply",
        message="What connectors are connected right now?",
    )


def test_standard_mode_connector_query_deferred():
    assert should_defer_unified_turn_live_to_classical(
        mode_key="standard",
        outcome_kind="conversational_reply",
        message="What connectors are connected right now?",
    )


def test_agent_mode_connector_query_deferred():
    assert should_defer_unified_turn_live_to_classical(
        mode_key="agent",
        outcome_kind="conversational_reply",
        message="What connectors are connected right now?",
    )


def test_explicit_live_no_defer_cannot_be_overridden_by_legacy_wording():
    """ECO-011 / DEC-001: one authoritative routing decision per turn."""
    for outcome_kind in ("conversational_reply", "clarifying_question", "knowledge_boundary"):
        assert not should_defer_unified_turn_live_to_classical(
            mode_key="agent",
            outcome_kind=outcome_kind,
            message="What connectors are connected right now?",
            classification={"requires_action": False},
            needs_tool_sse=False,
        )


def test_explicit_structured_defer_honored_without_keyword_matching():
    assert should_defer_unified_turn_live_to_classical(
        mode_key="standard",
        outcome_kind="conversational_reply",
        message="Investigate unusual renewal risk",
        needs_tool_sse=True,
    )


def test_legacy_callers_without_structured_signal_keep_guarded_compatibility():
    assert should_defer_unified_turn_live_to_classical(
        mode_key="standard",
        outcome_kind="conversational_reply",
        message="What connectors are connected right now?",
        needs_tool_sse=None,
    )
    assert not should_defer_unified_turn_live_to_classical(
        mode_key="standard",
        outcome_kind="conversational_reply",
        message="Hey, how are you?",
        needs_tool_sse=None,
    )


def test_connector_proposal_stays_live_even_when_sse_signal_is_true():
    assert not should_defer_unified_turn_live_to_classical(
        mode_key="agent",
        outcome_kind="connector_tool_proposal",
        message="Send the approved email",
        needs_tool_sse=True,
    )


def test_human_venting_remains_live_even_if_structured_signal_is_true():
    assert not should_defer_unified_turn_live_to_classical(
        mode_key="agent",
        outcome_kind="conversational_reply",
        message="This has been such a frustrating day. I'm exhausted.",
        needs_tool_sse=True,
    )


def test_handoff_consumed_once_and_removed_from_persistable_state():
    """ECO-011/DEC-018: a retry cannot re-arm a consumed tool selection."""
    from types import SimpleNamespace
    from app.services.live_classical_handoff import (
        arm_from_task_state, consume_handoff, peek_handoff,
        stash_live_classical_handoff,
    )

    state = {}
    try:
        proposal = SimpleNamespace(
            tool_name="getConnectorStatus", tool_invoke_action="getConnectorStatus",
            tool_arguments={"provider": "slack"},
        )
        stashed = stash_live_classical_handoff(
            state, proposal, reason="read_tool_classical",
        )
        assert stashed is not None
        arm_from_task_state(state)
        assert "live_classical_handoff" not in state
        assert consume_handoff() == stashed
        assert consume_handoff() is None
        arm_from_task_state(state)  # simulated retry with same conversation state
        assert peek_handoff() is None
        assert consume_handoff() is None
    finally:
        arm_from_task_state({})  # contextvars must not leak across tests


def test_evidence_queue_consumes_each_choice_once_without_stale_rearm():
    """DEC-002/018: queued handoff choices have bounded one-shot semantics."""
    from app.services.live_classical_handoff import (
        arm_from_task_state, consume_handoff, stash_handoff_queue,
    )

    state = {}
    try:
        stash_handoff_queue(state, [
            {"tool_name": "first_read", "tool_arguments": {"step": 1}},
            {"tool_name": "second_read", "tool_arguments": {"step": 2}},
        ])
        arm_from_task_state(state)
        assert "live_classical_handoff_queue" not in state
        assert "live_classical_handoff" not in state
        assert "evidence_plan_owns_tools" not in state
        assert consume_handoff()["tool_name"] == "first_read"
        assert consume_handoff()["tool_name"] == "second_read"
        assert consume_handoff() is None
        arm_from_task_state(state)
        assert consume_handoff() is None
    finally:
        arm_from_task_state({})


def test_new_direct_handoff_replaces_unconsumed_prior_queue():
    """DEC-001: a new turn must never inherit the previous turn's queued action."""
    from app.services.live_classical_handoff import (
        arm_from_task_state, arm_handoff, consume_handoff, stash_handoff_queue,
    )

    try:
        state = {}
        stash_handoff_queue(state, [{"tool_name": "stale_read"}])
        arm_from_task_state(state)
        arm_handoff({"tool_name": "current_read", "tool_arguments": {}})
        assert consume_handoff()["tool_name"] == "current_read"
        assert consume_handoff() is None
    finally:
        arm_from_task_state({})


def test_verified_output_persistence_failure_is_not_reported_as_success(monkeypatch):
    """DEC outcome authority: a failed evidence merge must reach the finalizer."""
    import pytest
    from app.services.execution_outcome import (
        ExecutionOutcomeEvent, VerifiedOutputRef, _persist_run,
    )
    from app.workflows import repository

    calls = []

    def update_run(_client, run_id, **kwargs):
        calls.append((run_id, kwargs["status"]))

    def fail_merge(_client, _run_id, _patch):
        raise RuntimeError("simulated metadata store outage")

    monkeypatch.setattr(repository, "update_run", update_run)
    monkeypatch.setattr(repository, "merge_run_parameters", fail_merge)
    event = ExecutionOutcomeEvent(
        org_id="org-test", status="completed", source="assistant_chat",
        run_id="run-test", verified_output=VerifiedOutputRef(summary="Verified read"),
    )
    with pytest.raises(RuntimeError, match="simulated metadata store outage"):
        _persist_run(None, event, "completed", "2026-11-09T00:00:00+00:00")
    assert calls == [("run-test", "completed")]


def test_finalizer_does_not_claim_run_persisted_after_storage_failure(monkeypatch):
    """No-network finalizer regression: failed durable write cannot report success."""
    from app.services import execution_outcome as outcome

    monkeypatch.setattr(outcome, "_resolve_workflow_id", lambda *_: "workflow-test")
    monkeypatch.setattr(outcome, "_run_already_finalized", lambda *_: False)

    def fail_persist(*_args):
        raise RuntimeError("simulated persistence outage")

    monkeypatch.setattr(outcome, "_persist_run", fail_persist)
    monkeypatch.setattr(outcome, "_write_audit", lambda *_: None)
    monkeypatch.setattr(outcome, "_emit_notification", lambda *_: None)
    monkeypatch.setattr(outcome, "_record_learning", lambda *_: None)
    monkeypatch.setattr(outcome, "_record_play_actioned_result", lambda *_: False)
    monkeypatch.setattr(outcome, "_enqueue_failure_alert_correlation", lambda *_: False)

    result = outcome.finalize_execution_outcome(
        None, org_id="org-test", status="cancelled", source="assistant_chat",
        run_id="run-test", workflow_id="workflow-test",
        metadata={"conversation_id": ""},
    )
    assert result.status == "cancelled"
    assert result.fanout["run_persisted"] is False
    assert result.fanout.get("idempotent_skip") is not True


def test_finalized_run_retry_skips_duplicate_terminal_fanout(monkeypatch):
    """A persisted terminal run must not repeat provider-facing fanout on retry."""
    from types import SimpleNamespace
    from app.services import execution_outcome as outcome

    class Query:
        def select(self, *_args): return self
        def eq(self, *_args): return self
        def limit(self, *_args): return self
        def execute(self):
            return SimpleNamespace(data=[{
                "status": "completed",
                "parameters": {"outcome_finalized": True},
            }])

    class Client:
        def table(self, name):
            assert name == "workflow_runs"
            return Query()

    monkeypatch.setattr(outcome, "_resolve_workflow_id", lambda *_: "workflow-test")

    def forbidden(*_args, **_kwargs):
        raise AssertionError("duplicate terminal fanout on retry")

    for name in ("_persist_run", "_write_audit", "_emit_notification", "_record_learning"):
        monkeypatch.setattr(outcome, name, forbidden)

    result = outcome.finalize_execution_outcome(
        Client(), org_id="org-test", status="completed", source="assistant_chat",
        run_id="run-test", workflow_id="workflow-test",
        metadata={"completion_verified": True},
    )
    assert result.fanout["idempotent_skip"] is True
