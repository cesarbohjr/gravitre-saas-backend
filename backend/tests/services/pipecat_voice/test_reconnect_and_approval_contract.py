"""Reconnect ownership, result recovery and the explicit approval contract.

Reconnect: an old connection never clears a newer connection's stop marker,
stops delivering output once superseded, and the new connection recovers the
outcome of work the old one finished (completed / pending / cancelled /
in progress / unknown) from the stored records, without re-running anything.

Approval: a "yes" approves the version that was read back on this connection
(approval_action_id), never whatever happens to be staged; answer expectation
comes from the pending approval, not from how the last sentence ends.
"""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from app.services import chat_turn_cancel_service, voice_barge_in_write
from app.services.approval_expectation import (
    APPROVAL_REVISION_STALE,
    bind_expected_approval,
    expected_approval,
    pending_approval_from_state,
)
from app.services.chat_turn_cancel_service import (
    clear_stop,
    is_stop_requested,
    request_stop,
    stop_owner,
)
from app.services.pipecat_voice import voice_connection_recovery as recovery
from app.services.pipecat_voice.voice_audio_origin import VoicePipelineSession
from app.services.spoken_write_approval import classify_spoken_write_approval
from app.services.turn_cancellation import TurnCancellation
from tests.services.pipecat_voice.test_interrupt_intents import (
    _FakeStateService,
    _Harness,
)

ORG = "00000000-0000-4000-8000-000000000001"
USER = "00000000-0000-4000-8000-000000000002"
CONV = "00000000-0000-4000-8000-000000000003"


@pytest.fixture(autouse=True)
def _isolated(monkeypatch: pytest.MonkeyPatch):
    chat_turn_cancel_service.reset_local_stops_for_tests()
    voice_barge_in_write.reset_write_effects_for_tests()
    recovery.reset_for_tests()
    monkeypatch.setattr(chat_turn_cancel_service, "get_redis_client", lambda _s=None: None)
    monkeypatch.setattr(recovery, "_redis", lambda _s=None: None)
    monkeypatch.setattr("app.services.pipecat_voice.voice_latency_metrics._write", lambda *a, **k: None)
    yield
    chat_turn_cancel_service.reset_local_stops_for_tests()
    recovery.reset_for_tests()


def _email(status: str, approval_id: str = "appr-A", **extra: Any) -> dict[str, Any]:
    return {
        "pending_task": {
            "type": "connector_action",
            "status": status,
            "params": {
                "invoke_action": "gmail.messages.send",
                "tool_name": "gmail_send",
                "integration": "gmail",
                "label": "Send email",
                "args": {"to": "stephanie@example.test", "subject": "Budget", "body": "Attached."},
                "approval_action_id": approval_id,
                "bound_args_digest": f"digest-{approval_id}",
            },
            **extra,
        }
    }


# --- stop marker ownership --------------------------------------------------------------


class _FakeRedis:
    """setex/get/delete plus EVAL of the compare-and-delete script."""

    def __init__(self) -> None:
        self.data: dict[str, str] = {}

    def setex(self, key: str, _ttl: int, value: str) -> None:
        self.data[key] = value

    def get(self, key: str) -> str | None:
        return self.data.get(key)

    def delete(self, key: str) -> None:
        self.data.pop(key, None)

    def eval(self, _script: str, _n: int, key: str, owner: str) -> int:
        if self.data.get(key) == owner:
            del self.data[key]
            return 1
        return 0


@pytest.mark.parametrize("with_redis", [False, True], ids=["in_process", "redis"])
def test_old_connection_cannot_clear_a_newer_connections_stop(monkeypatch, with_redis: bool) -> None:
    redis = _FakeRedis() if with_redis else None
    monkeypatch.setattr(chat_turn_cancel_service, "get_redis_client", lambda _s=None: redis)
    request_stop(ORG, CONV, owner="conn-A")
    # The user reconnected and said "cancel it" on the new connection.
    request_stop(ORG, CONV, owner="conn-B")
    # The old socket closes and releases what it armed.
    clear_stop(ORG, CONV, owner="conn-A")
    assert is_stop_requested(ORG, CONV) is True, "connection B's cancel still holds"
    assert stop_owner(ORG, CONV) == "conn-B"
    clear_stop(ORG, CONV, owner="conn-B")
    assert is_stop_requested(ORG, CONV) is False


def test_unscoped_clear_still_clears_text_chat_stop() -> None:
    request_stop(ORG, CONV)
    clear_stop(ORG, CONV, owner="conn-A")
    assert is_stop_requested(ORG, CONV) is True, "a voice socket never clears text chat's Stop"
    clear_stop(ORG, CONV)
    assert is_stop_requested(ORG, CONV) is False


def test_reporter_release_is_scoped_to_its_connection() -> None:
    from app.services.pipecat_voice.interrupt_reporter import (
        ElevenLabsInterruptReporter,
    )

    old = VoicePipelineSession()
    new = VoicePipelineSession()
    reporter = ElevenLabsInterruptReporter(org_id=ORG, user_id=USER, conversation_id=CONV, voice_session=old)
    request_stop(ORG, CONV, owner=new.connection_token)
    asyncio.run(reporter.release_stop_marker())
    assert stop_owner(ORG, CONV) == new.connection_token


# --- two overlapping connections --------------------------------------------------------


def test_newer_connection_supersedes_the_older_one() -> None:
    a, b = VoicePipelineSession(), VoicePipelineSession()
    notified: list[str] = []
    recovery.claim_conversation(ORG, CONV, a, on_superseded=lambda: notified.append("A"))
    assert recovery.is_current_connection(ORG, CONV, a.connection_token)
    previous = recovery.claim_conversation(ORG, CONV, b)
    assert previous == a.connection_token
    assert a.superseded is True and b.superseded is False
    assert notified == ["A"], "the old client is told its session was replaced"
    assert not recovery.is_current_connection(ORG, CONV, a.connection_token)
    # A superseded connection's audio is never delivered.
    assert a.reply_audio_suppressed(a.reply_id)
    # The old socket closing does not remove the new owner.
    recovery.release_conversation(ORG, CONV, a.connection_token)
    assert recovery.is_current_connection(ORG, CONV, b.connection_token)


def test_cancel_on_the_replacement_cancels_the_old_connections_uncommitted_work() -> None:
    a, b = VoicePipelineSession(), VoicePipelineSession()
    a.turn_cancellation = TurnCancellation()
    recovery.claim_conversation(ORG, CONV, a)
    recovery.claim_conversation(ORG, CONV, b)
    since = recovery.cancel_superseded_work(ORG, CONV, "task_cancel")
    assert since is not None
    assert a.turn_cancellation.cancelled, "its write that has not committed is refused"


def test_superseded_connection_speaks_nothing_more() -> None:
    h = _Harness(True, conversation_id=CONV)

    async def _script() -> None:
        h.session.superseded = True
        await h.service._push_spoken_text("This reply is obsolete.")
        await h.service._speak_narration_now("Let me check.")

    h.run(_script)
    assert h.service._push_llm_text.await_count == 0


# --- recovery classification -----------------------------------------------------------


def _marker() -> dict[str, Any]:
    return {recovery.UNDELIVERED_KEY: recovery.undelivered_marker(status="executed", label="", connection="A")}


def test_provider_completion_after_disconnect_is_recovered_once() -> None:
    state = {
        "pending_task": {"status": "executed", "result": {"title": "Send email", "body": "Sent."}},
        **_marker(),
    }
    outcome = recovery.classify_recovery(state)
    assert outcome.kind == recovery.COMPLETED and outcome.should_announce
    assert "went through" in recovery.recovery_line(outcome)
    # Without the marker the user was already told: nothing to repeat.
    del state[recovery.UNDELIVERED_KEY]
    assert not recovery.classify_recovery(state).should_announce


def test_pending_approval_is_recovered_as_pending_not_announced() -> None:
    outcome = recovery.classify_recovery(_email("awaiting_confirm"))
    assert outcome.kind == recovery.PENDING and not outcome.should_announce


def test_cancelled_before_disconnect_is_recovered() -> None:
    state = {
        "pending_task": None,
        recovery.UNDELIVERED_KEY: recovery.undelivered_marker(status="cancelled", label="Send email", connection="A"),
    }
    outcome = recovery.classify_recovery(state)
    assert outcome.kind == recovery.CANCELLED
    assert "nothing was sent" in recovery.recovery_line(outcome)


def test_worker_restart_mid_write_is_unknown_and_never_resent() -> None:
    old = (datetime.now(UTC) - timedelta(minutes=10)).isoformat()
    state = _email("executing", execution_claim_id="claim-1", claimed_at=old)
    outcome = recovery.classify_recovery(state)
    assert outcome.kind == recovery.UNKNOWN and outcome.should_announce
    line = recovery.recovery_line(outcome)
    assert "can't confirm" in line and "won't send it again" in line


def test_fresh_claim_is_in_progress() -> None:
    fresh = datetime.now(UTC).isoformat()
    outcome = recovery.classify_recovery(_email("executing", execution_claim_id="c", claimed_at=fresh))
    assert outcome.kind == recovery.IN_PROGRESS


def test_uncertain_outcome_is_unknown() -> None:
    assert recovery.classify_recovery(_email("outcome_uncertain")).kind == recovery.UNKNOWN


def test_unreadable_state_recovers_nothing() -> None:
    assert recovery.classify_recovery({"_unavailable": True}).kind == recovery.NOTHING


def test_new_connection_says_the_recovered_result_before_its_next_answer() -> None:
    h = _Harness(True, conversation_id=CONV)
    state = _FakeStateService(
        {"pending_task": {"status": "executed", "result": {"title": "Send email to Stephanie"}}, **_marker()}
    )

    async def _script() -> None:
        with patch(
            "app.services.pipecat_voice.speculative_generation.load_revision_task_state",
            new=AsyncMock(return_value=dict(state.state)),
        ):
            await h.service.prepare_connection_recovery()
        await h.turn("did it go out?")

    with patch("app.services.conversation_state_service.get_conversation_state_service", return_value=state):
        h.run(_script)
    text = h.spoken_client_text()
    assert text.startswith("Before we got cut off, \"Send email to Stephanie\" went through.")
    assert state.state[recovery.UNDELIVERED_KEY] is None, "said once"
    assert "Do not repeat it" in str(h.calls[-1].get("assistant_base_prompt") or "")


def test_first_turn_waits_for_recovery_that_is_still_loading() -> None:
    h = _Harness(True, conversation_id=CONV)
    state = _FakeStateService(
        {"pending_task": {"status": "executed", "result": {"title": "Send email to Stephanie"}}, **_marker()}
    )

    async def _slow_load(*_a: Any, **_k: Any) -> dict[str, Any]:
        await asyncio.sleep(0.2)
        return dict(state.state)

    async def _script() -> None:
        with patch(
            "app.services.pipecat_voice.speculative_generation.load_revision_task_state", new=_slow_load
        ):
            h.service.recovery_task = asyncio.create_task(h.service.prepare_connection_recovery())
            await h.turn("did it go out?")

    with patch("app.services.conversation_state_service.get_conversation_state_service", return_value=state):
        h.run(_script)
    assert h.spoken_client_text().startswith("Before we got cut off, \"Send email to Stephanie\" went through.")


def test_a_turn_on_a_connection_replaced_on_another_worker_is_not_answered(monkeypatch) -> None:
    h = _Harness(True, conversation_id=CONV)
    owner_key = f"voice:conn:{ORG}:{CONV}"
    monkeypatch.setattr(recovery, "_redis", lambda _s=None: SimpleNamespace(get=lambda k: "other-worker" if k == owner_key else None))
    h.service._org_id = ORG

    async def _script() -> None:
        await h.turn("what's on my calendar?")

    h.run(_script)
    assert h.session.superseded, "ownership moved, read from the shared key"
    assert h.calls == [], "the replaced connection does not answer"
    assert h.service._push_llm_text.await_count == 0


def test_turn_that_wrote_after_disconnect_leaves_an_undelivered_marker() -> None:
    h = _Harness(True, conversation_id=CONV)
    state = _FakeStateService({"pending_task": {"status": "executed", "label": "Send email"}})

    def _write_lands_after_the_drop() -> None:
        h.session.client_connected = False
        handle = voice_barge_in_write.begin_write_effect(
            SimpleNamespace(org_id=ORG, conversation_id=CONV, settings=None), "email.send"
        )
        voice_barge_in_write.finish_write_effect(handle, "completed")

    h.during_first_turn = _write_lands_after_the_drop

    async def _script() -> None:
        await h.turn("yes")
        await asyncio.gather(*list(h.service._background_tasks))

    with patch(
        "app.services.voice_barge_in_write.action_is_mutating_write", lambda action: action == "email.send"
    ), patch("app.services.conversation_state_service.get_conversation_state_service", return_value=state), patch(
        "app.services.pipecat_voice.speculative_generation.load_revision_task_state",
        new=AsyncMock(return_value={"_unavailable": True}),
    ), patch("app.services.pipecat_voice.cognitive_llm.load_revision_task_state", new=AsyncMock(return_value={"_unavailable": True})):
        h.run(_script)
    marker = state.state.get(recovery.UNDELIVERED_KEY)
    assert marker and marker["status"] == "executed"
    assert recovery.classify_recovery(state.state).should_announce


# --- the approval contract: classifier and claim ---------------------------------------


def test_yes_bound_to_the_read_back_version_approves_it() -> None:
    with bind_expected_approval("appr-A"):
        verdict = classify_spoken_write_approval("yes", task_state=_email("awaiting_confirm", "appr-A"))
    assert verdict.invoke_allowed is True


def test_recipient_changed_after_approval_is_not_sent_on_the_old_yes() -> None:
    # The user said yes to version A; a correction re-bound the draft as B.
    with bind_expected_approval("appr-A"):
        verdict = classify_spoken_write_approval("yes", task_state=_email("awaiting_confirm", "appr-B"))
    assert verdict.invoke_allowed is False and verdict.reason == "approval_revised"


def test_yes_with_nothing_read_back_approves_nothing() -> None:
    with bind_expected_approval(""):
        verdict = classify_spoken_write_approval("yes", task_state=_email("awaiting_confirm"))
    assert verdict.invoke_allowed is False and verdict.reason == "approval_not_read_back"


def test_unbound_confirmation_keeps_existing_behavior() -> None:
    assert expected_approval() is None
    assert classify_spoken_write_approval("yes", task_state=_email("awaiting_confirm")).invoke_allowed


def test_claim_refuses_a_revised_version_and_sends_nothing() -> None:
    from app.services.chat_connector_execution_service import (
        ChatConnectorExecutionService,
    )
    from app.services.chat_connector_models import ConnectorActionPlan

    service = ChatConnectorExecutionService.__new__(ChatConnectorExecutionService)
    service._state = SimpleNamespace(
        compare_and_set_pending_status=AsyncMock(return_value=True), update_task_state=AsyncMock()
    )
    plan = ConnectorActionPlan(
        tool_name="gmail_send", invoke_action="gmail.messages.send", integration="gmail", kind="write",
        label="Send email", args={},
    )

    async def _claim(bound: str) -> Any:
        with bind_expected_approval(bound):
            return await service._claim_write_before_invoke(
                CONV, ORG, _email("awaiting_confirm", "appr-B"), client=None, plan=plan, actor_id=USER
            )

    refused = asyncio.run(_claim("appr-A"))
    assert refused is not None and refused.error_code == APPROVAL_REVISION_STALE
    service._state.compare_and_set_pending_status.assert_not_awaited()
    assert asyncio.run(_claim("appr-B")) is None, "the read-back version is claimed"


def test_cas_rechecks_the_version_under_the_lock() -> None:
    from app.services.conversation_state_service import ConversationStateService

    svc = ConversationStateService.__new__(ConversationStateService)
    svc._read_task_state_sync = lambda *_a: _email("awaiting_confirm", "appr-B")  # type: ignore[method-assign]
    svc._client = lambda _c: (_ for _ in ()).throw(AssertionError("no write on a mismatch"))  # type: ignore[method-assign]
    with bind_expected_approval("appr-A"):
        assert svc._compare_and_set_pending_status_sync(CONV, ORG, "awaiting_confirm", {}, None, USER) is False


# --- the approval contract in the voice turn -------------------------------------------


def _staging_stream(h: _Harness, states: list[dict[str, Any] | None]):
    """Turn N reports ``states[N-1]`` (turn 1 stages the readback); every turn records the bound expectation."""
    from app.operators.stream_events import (
        AssistantStreamComplete,
        AssistantStreamEvent,
    )

    seen: list[Any] = []

    async def _stream(**kwargs: Any):
        h.calls.append(kwargs)
        seen.append(expected_approval())
        yield AssistantStreamEvent(sse_type="text-delta", payload={"delta": "Here's the email to Stephanie."})
        yield AssistantStreamComplete(
            full_content="Here's the email to Stephanie.",
            tool_results=[],
            react_result=None,
            model="test",
            task_state=states[len(h.calls) - 1] if len(h.calls) <= len(states) else None,
        )

    h._stream = _stream  # type: ignore[method-assign]
    return seen


def test_yes_after_the_readback_is_bound_to_that_version() -> None:
    h = _Harness(True, conversation_id=CONV)
    staged = _email("awaiting_confirm", "appr-A")
    seen = _staging_stream(h, [staged])

    async def _script() -> None:
        await h.turn("email Stephanie the budget")
        assert h.session.approval_read_back_id == "appr-A"
        assert h.session.approval_readback_reply_id == h.service._reply_id
        await h.turn("email Stephanie the budget", "yes")

    with patch(
        "app.services.pipecat_voice.cognitive_llm.load_revision_task_state", new=AsyncMock(return_value=staged)
    ), patch("app.services.pipecat_voice.cognitive_llm.confirmation_hold_seconds", return_value=0.0):
        h.run(_script)
    assert seen[-1] is not None and seen[-1].approval_action_id == "appr-A"


def test_reconnect_during_readback_rereads_before_approving() -> None:
    h = _Harness(True, conversation_id=CONV)  # a fresh connection: nothing read back here
    staged = _email("awaiting_confirm", "appr-A")
    seen = _staging_stream(h, [staged])

    async def _script() -> None:
        await h.turn("yes")
        assert h.calls == [], "the first yes is not an approval: the draft is read back instead"
        assert h.session.approval_read_back_id == "appr-A"
        await h.turn("yes", "yes")

    with patch(
        "app.services.pipecat_voice.cognitive_llm.load_revision_task_state", new=AsyncMock(return_value=staged)
    ), patch("app.services.pipecat_voice.cognitive_llm.confirmation_hold_seconds", return_value=0.0):
        h.run(_script)
    text = h.spoken_client_text()
    assert "Before I send anything, here's what I have." in text and "stephanie@example.test" in text
    assert len(h.calls) == 1 and seen[-1].approval_action_id == "appr-A"


def test_cancel_then_a_later_yes_approves_nothing() -> None:
    h = _Harness(True, conversation_id=CONV)
    state = _FakeStateService(_email("awaiting_confirm", "appr-A"))
    # Turn 2 ("cancel it", no barge-in) is answered by the brain, which drops the draft.
    seen = _staging_stream(h, [dict(state.state), {"pending_task": None}])

    async def _script() -> None:
        await h.turn("email Stephanie the budget")
        await h.turn("email Stephanie the budget", "cancel it")
        state.state["pending_task"] = None
        assert h.session.pending_approval is None
        with patch(
            "app.services.pipecat_voice.cognitive_llm.load_revision_task_state",
            new=AsyncMock(return_value=dict(state.state)),
        ):
            await h.turn("email Stephanie the budget", "cancel it", "yes")

    with patch("app.services.conversation_state_service.get_conversation_state_service", return_value=state), patch(
        "app.services.pipecat_voice.cognitive_llm.confirmation_hold_seconds", return_value=0.0
    ):
        h.run(_script)
    assert state.state["pending_task"] is None
    assert seen[-1] is not None and seen[-1].approval_action_id == "", "the late yes is bound to nothing"
    assert classify_spoken_write_approval("yes", task_state=state.state).invoke_allowed is False


def test_answer_expected_comes_from_the_pending_approval_not_punctuation() -> None:
    from app.services.pipecat_voice.interrupt_reporter import (
        ElevenLabsInterruptReporter,
    )

    session = VoicePipelineSession()
    reporter = ElevenLabsInterruptReporter(org_id=ORG, user_id=USER, conversation_id=CONV, voice_session=session)
    # A readback whose copy ends with no question and no "say yes" invitation.
    reporter._draft_client = "I'll send the budget email to Stephanie at stephanie@example.test as soon as you approve."
    assert reporter.answer_expected() is False, "a statement with no approval behind it expects nothing"
    session.pending_approval = pending_approval_from_state(_email("awaiting_confirm"))
    session.approval_read_back_id = "appr-A"
    session.approval_readback_reply_id = session.reply_id
    assert reporter.answer_expected() is True
    # A later, unrelated reply is not the readback.
    session.reply_id += 1
    assert reporter.answer_expected() is False


def test_answer_expected_waits_until_the_readback_details_were_heard() -> None:
    from app.services.pipecat_voice.interrupt_reporter import (
        ElevenLabsInterruptReporter,
    )

    class _Ledger:
        ever_recorded = True

        def __init__(self) -> None:
            self.heard = ""

        def snapshot(self) -> str:
            return self.heard

    ledger = _Ledger()
    session = VoicePipelineSession()
    reporter = ElevenLabsInterruptReporter(
        org_id=ORG, user_id=USER, conversation_id=CONV, voice_session=session, spoken_ledger=ledger
    )
    draft = "Here's the email to Stephanie about the budget. Should I send it? Say yes, or tell me what to change."
    reporter._draft_client = draft
    session.pending_approval = pending_approval_from_state(_email("awaiting_confirm"))
    session.approval_read_back_id = "appr-A"
    session.approval_readback_reply_id = session.reply_id
    ledger.heard = draft[:20]
    assert reporter.answer_expected() is False, "a 'yes' over the first words is a backchannel"
    ledger.heard = draft
    assert reporter.answer_expected() is True


# --- cancellation on the replacement connection ----------------------------------------


def test_cancel_on_the_replacement_stops_the_old_connections_write() -> None:
    old = VoicePipelineSession()
    old.turn_cancellation = TurnCancellation()
    old.work_active = True
    h = _Harness(True, conversation_id=CONV)
    recovery.claim_conversation(ORG, CONV, old)
    recovery.claim_conversation(ORG, CONV, h.session)
    h.service.replaced_connection = True

    async def _script() -> None:
        await h.turn("cancel it")

    with patch(
        "app.services.pipecat_voice.cognitive_llm.load_revision_task_state",
        new=AsyncMock(return_value={"pending_task": None}),
    ):
        h.run(_script)
    assert old.turn_cancellation.cancelled, "the old connection's uncommitted write is refused"
    assert stop_owner(ORG, CONV) == h.session.connection_token
    assert h.calls == [], "answered from the record, not by the brain"
    # The old socket closing cannot release the new connection's stop.
    clear_stop(ORG, CONV, owner=old.connection_token)
    assert is_stop_requested(ORG, CONV) is True


def test_cancel_on_the_replacement_never_claims_nothing_was_sent_for_a_write_in_flight_elsewhere() -> None:
    h = _Harness(True, conversation_id=CONV)
    h.service.replaced_connection = True
    fresh = datetime.now(UTC).isoformat()
    in_flight = _email("executing", execution_claim_id="c", claimed_at=fresh)

    async def _script() -> None:
        await h.turn("cancel it")

    with patch(
        "app.services.pipecat_voice.cognitive_llm.load_revision_task_state", new=AsyncMock(return_value=in_flight)
    ), patch(
        "app.services.conversation_state_service.get_conversation_state_service",
        return_value=_FakeStateService(dict(in_flight)),
    ):
        h.run(_script)
    report = h.spoken_client_text()
    assert "can't confirm" in report and "Nothing had been sent" not in report


# --- cancel coverage (OC-2, OC-3) ------------------------------------------------------


@pytest.mark.parametrize(
    "status", ["awaiting_plan_confirm", "awaiting_step_confirm", "awaiting_user_confirmation", "awaiting_approval"]
)
def test_cancel_withdraws_plan_and_step_approvals_too(status: str) -> None:
    from app.services.pipecat_voice.cognitive_llm import (
        withdraw_unclaimed_pending_write,
    )

    assert withdraw_unclaimed_pending_write(_email(status)) is not None


def test_a_failed_withdraw_is_said_not_swallowed() -> None:
    h = _Harness(True, conversation_id=CONV)

    class _Broken:
        async def update_task_state_from(self, *_a: Any, **_k: Any) -> None:
            raise RuntimeError("db down")

    async def _script() -> None:
        await h.barge_in_during("email Stephanie the budget")
        await h.turn("email Stephanie the budget", "cancel it")

    with patch("app.services.conversation_state_service.get_conversation_state_service", return_value=_Broken()):
        h.run(_script)
    report = h.spoken_client_text()
    assert "couldn't clear what was waiting for your approval" in report
    assert h.session.approval_read_back_id is None, "a later yes re-reads before approving"
