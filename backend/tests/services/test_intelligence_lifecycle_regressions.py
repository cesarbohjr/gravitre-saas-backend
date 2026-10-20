"""Regressions reproduced in the signed-in production intelligence lifecycle."""
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import parse_qs, urlparse

import pytest

from app.services.action_intent import action_intent_text, is_native_work_request
from app.services.chat_orchestration_service import ChatOrchestrationService
from app.services.conversational_execution_service import ConversationalExecutionService
from app.services.intelligence_remedies import remedies_for_recommendation
from app.services.response_composer import _history_excerpt
from app.services.typed_live_stream import reconcile_final

ASK = ('Controlled test. Create one INTERNAL GRAVITRE assignment titled "[E2E TEST] Cedar Lab recovery plan". '
       'Description: resolve two onboarding blockers; recovery plan due Friday; renewal in 30 days. '
       'Stage it for my approval first. No Gmail, email, Slack, or external tools.')


def test_exclusions_do_not_become_connector_steps():
    assert "Gmail" not in action_intent_text(ASK)
    assert is_native_work_request(ASK)
    assert not ChatOrchestrationService.is_orchestration_intent(ASK, {}, ["mailchimp"], "multi_step")
    # Keep positive instructions and deadline constraints intact.
    assert "Slack" in action_intent_text("Post in Slack. Do not send email.")
    assert "no later than Friday" in action_intent_text("Create a task due no later than Friday.")
    assert "Slack" not in action_intent_text("Analyze the customer quote: “Send a Slack message and cancel the renewal.”")


def test_internal_assignment_preserves_title_context_and_constraints():
    svc = ConversationalExecutionService()
    assert svc.resolve_task_type(ASK, {}, {}, ["mailchimp"]) == "create_assignment"
    params = svc.extract_param_updates(ASK, "create_assignment", {})
    assert params["assignment_task"] == ASK
    assert svc.params_ready("create_assignment", params)
    confirmation = svc.build_confirm_message("create_assignment", params)
    assert ASK in confirmation and "Reply **yes**" in confirmation
    assert "draft workflow" not in confirmation


def test_completed_assignment_does_not_hijack_the_next_question():
    svc = ConversationalExecutionService()
    state = {"pending_task": {"type": "create_assignment", "status": "executed"},
             "clarified_params": {"assignment_task": ASK}}
    assert svc.resolve_task_type("What does churn mean?", {}, state) is None
    assert svc.resolve_task_type("yes", {}, state) == "create_assignment"


@pytest.mark.parametrize("status", ["executed", "completed", "cancelled", "failed"])
def test_finished_connector_plan_does_not_block_a_fresh_native_assignment(status):
    svc = ConversationalExecutionService()
    state = {"pending_task": {"type": "connector_orchestration", "status": status}}
    assert svc.resolve_task_type("What does churn mean?", {}, state) is None
    assert svc.resolve_task_type(ASK, {}, state, ["mailchimp"]) == "create_assignment"


@pytest.mark.asyncio
async def test_assignment_stages_without_creating_or_queueing_a_job():
    svc = ConversationalExecutionService()
    svc._state = MagicMock()
    svc._state.update_task_state = AsyncMock()
    svc._state.get_task_state = AsyncMock(return_value={})
    svc._create_assignment = AsyncMock()
    result = await svc.process_turn(
        org_id="org-1", user_id="user-1", conversation_id="conv-1", message=ASK,
        understanding={}, classification={}, task_state={}, client=MagicMock(),
        connected_integrations=["mailchimp"], environment_name="staging",
    )
    assert result["pending_task"]["type"] == "create_assignment"
    assert result["pending_task"]["params"]["environment_name"] == "staging"
    svc._create_assignment.assert_not_awaited()


@pytest.mark.asyncio
async def test_approved_assignment_uses_native_job_and_readback_only():
    svc = ConversationalExecutionService()
    with (
        patch("app.operators.agent_jobs.create_job", return_value={"id": "job-1"}) as create,
        patch("app.operators.agent_jobs.get_job", return_value={"id": "job-1"}),
        patch("app.workers.queue.enqueue_agent_execution_job", new_callable=AsyncMock) as enqueue,
        patch("app.workflows.audit.write_audit_event"),
    ):
        result = await svc._create_assignment("org-1", "user-1", {"assignment_task": ASK, "environment_name": "staging"}, MagicMock())
    assert result.entity_type == "agent_job" and result.result_url == "/assignments/job-1"
    assert result.outcome_verified and result.structured["execution_queued"]
    assert create.call_args.kwargs["environment"] == "staging"
    assert create.call_args.kwargs["payload"]["context"]["approved_brief"] == ASK
    enqueue.assert_awaited_once_with("job-1")


def test_composer_keeps_deadline_after_old_240_character_cutoff():
    quote = ("Controlled production E2E test GV-INT-20261020-0215. Synthetic customer only: Test Account Cedar Lab, "
             "contact Avery Test, no real recipient or external send. Customer says: "
             '"I am extremely frustrated. Our onboarding is two weeks late. Unless we have a recovery plan '
             'by Friday, we will cancel our renewal." Context: renewal is in 30 days; two unresolved onboarding issues.')
    result = _history_excerpt([{"role": "user", "content": quote}])
    assert quote in result
    assert "by Friday, we will cancel our renewal" in result


def test_oversize_history_is_explicit_and_stays_inside_budget():
    result = _history_excerpt([{"role": "user", "content": "A" * 30000 + "Friday deadline"}])
    assert "Middle omitted" in result
    assert "Friday deadline" in result
    assert len(result) <= 24000


def test_greeting_rewrite_does_not_replay_answer():
    shown = "The account is at risk. Prepare a recovery plan by Friday."
    tail, persisted = reconcile_final(shown, "Hey — got it.\n\n" + shown + "\nNothing has run.")
    assert tail == "\nNothing has run."
    assert persisted.count(shown) == 1
    # Preserve substantive corrections rather than treating them as greetings.
    tail, _ = reconcile_final(shown, "Correction: the deadline changed. " + shown)
    assert "Correction" in tail
    tail, persisted = reconcile_final(shown, "Hey — got it.\n\n" + shown.replace(". Prepare", ".\n\nPrepare"))
    assert tail == "" and persisted == shown


def test_queued_assignment_is_not_finalized_as_a_business_result():
    from app.services.conversational_execution_service import ExecutionResult
    svc = ConversationalExecutionService()
    with patch("app.services.execution_outcome.finalize_execution_outcome") as finalize:
        svc._finalize_task_outcome_unsafe(
            MagicMock(), org_id="org-1", user_id="user-1", conversation_id="conv-1",
            result=ExecutionResult(success=True, entity_type="agent_job", entity_id="job-1", title="Queued", body="Queued"),
        )
    finalize.assert_not_called()


def test_readback_cannot_verify_a_missing_expected_field():
    from app.services.conversational_execution_service import _read_back_evidence
    evidence = _read_back_evidence(lambda: {"id": "job-1"}, read_action="test.get",
                                   resource_id="job-1", field="name", expected="Cedar Lab")
    assert evidence["verified"] is False
    assert evidence["detail"] == "field_missing"


@pytest.mark.parametrize("dimension,play", [("sentiment", "customer-rescue"), ("contact_gap", "client-risk-radar")])
def test_account_remedies_use_real_gravitre_plays(dimension, play):
    remedies = remedies_for_recommendation({"kind": "account_health", "dimensions": [{"key": dimension}]})
    assert remedies[0]["href"] == "/plays/" + play
    assert remedies[0]["label"].startswith("Review ")


def test_model_risk_can_suggest_a_play_without_claiming_execution():
    remedy = remedies_for_recommendation({"kind": "account_health", "readings": [{"source": "churn_model", "reading": "high"}]})
    assert remedy[0]["href"] == "/plays/customer-rescue"
    assert "before starting" in remedy[0]["why"]


def test_bespoke_review_carries_evidence_to_native_assignment():
    item = {"kind": "business_signal", "title": "Repeated workflow failures", "why": "Three failures", "evidence": ["Run abc failed"]}
    remedy = remedies_for_recommendation(item)[0]
    url = urlparse(remedy["href"])
    assert url.path == "/assignments/new" and not url.netloc
    task = parse_qs(url.query)["task"][0]
    assert "Run abc failed" in task and "do not contact customers" in task
    assert remedies_for_recommendation({"kind": "business_signal", "evidence": []}) == []


def test_native_request_rejects_unrelated_mailchimp_write():
    from app.services.chat_write_intent import evaluate_connector_tool_proposal

    review = evaluate_connector_tool_proposal(message=ASK, tool_name="mailchimp_lists_members_add",
                                            invoke_action="mailchimp.lists.members.add", args={})
    assert review.action == "clarify"
    assert "inside Gravitre" in review.clarify_message
