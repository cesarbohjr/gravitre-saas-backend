"""Regressions reproduced in ACC-20261019-2344 on production."""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.services.action_intent import action_intent_text
from app.services.chat_orchestration_service import ChatOrchestrationService
from app.services.conversational_execution_service import CONFIRM_PATTERN
from app.services.sentiment_friction_service import SentimentFrictionService
from app.services.spoken_write_approval import classify_spoken_write_approval


def test_constraints_and_trace_requests_are_not_connector_steps():
    request = (
        "Create one HubSpot contact, email acc@example.invalid. "
        "Do not send email, enroll it in automation, or change billing. "
        "First show the proposed action for approval. "
        "Preserve ACC-20261019-2344 as the trace marker and report workflow run IDs when available."
    )
    assert not ChatOrchestrationService.is_orchestration_intent(request, {}, ["hubspot"])
    assert ChatOrchestrationService._mentioned_integrations(request, ["hubspot"]) == ["hubspot"]
    assert "send email" not in action_intent_text(request)
    assert "acc@example.invalid" in action_intent_text(request)


def test_positive_multi_connector_work_is_preserved():
    request = "Find HubSpot deals. Do not send Gmail. Then post a summary to Slack"
    assert ChatOrchestrationService.is_orchestration_intent(request, {}, ["hubspot", "slack"])
    assert set(ChatOrchestrationService._mentioned_integrations(request, [])) == {"hubspot", "slack"}
    assert action_intent_text("Do not create a HubSpot contact") == ""
    assert "Slack" in action_intent_text("Do not send Gmail, but post to Slack")


def test_literal_payload_constraints_are_not_commands_or_removed_from_steps():
    from app.services.action_intent import actionable_clauses

    message = 'Post to Slack: "Do not send Gmail. Never update HubSpot."'
    assert actionable_clauses(message) == [message]
    assert ChatOrchestrationService._mentioned_integrations(message, []) == ["slack"]


@pytest.mark.parametrize("message", ["Approve", "approved", "Yes, create it."])
def test_approval_uses_the_existing_bound_pending_action(message):
    pending = {"pending_task": {
        "id": "action-1", "type": "connector_action", "status": "awaiting_confirm",
        "org_id": "org-1", "actor_id": "user-1", "conversation_id": "conv-1",
        "integration": "hubspot", "invoke_action": "hubspot.contacts.create",
        "params": {"invoke_action": "hubspot.contacts.create", "args": {"email": "acc@example.invalid"}},
    }}
    result = classify_spoken_write_approval(message, task_state=pending,
        expected_org_id="org-1", expected_actor_id="user-1", expected_conversation_id="conv-1")
    assert result.invoke_allowed
    for field, value in [("expected_org_id", "other-org"), ("expected_actor_id", "other-user"),
                         ("expected_conversation_id", "other-conv")]:
        assert not classify_spoken_write_approval(message, task_state=pending, **{field: value}).invoke_allowed
    pending["pending_task"]["status"] = "completed"
    assert not classify_spoken_write_approval(message, task_state=pending).invoke_allowed


def test_approve_is_a_canonical_confirmation_but_modifications_are_not():
    assert CONFIRM_PATTERN.fullmatch("Approve")
    assert not CONFIRM_PATTERN.fullmatch("Approve but change the email")


def test_failed_orchestration_does_not_suppress_a_new_connector_request():
    from app.services.chat_connector_execution_service import ChatConnectorExecutionService

    state = {"pending_task": {"type": "connector_orchestration", "status": "blocked"},
             "execution_plan": {"plan_id": "old-plan", "execution_strategy": "ANSWER_ONLY"}}
    assert ChatConnectorExecutionService.is_connector_intent("Create a HubSpot contact", state)
    assert not ChatConnectorExecutionService.is_connector_intent("Approve", state)
    state["pending_task"]["status"] = "awaiting_plan_confirm"
    assert not ChatConnectorExecutionService.is_connector_intent("Create a HubSpot contact", state)


@pytest.mark.asyncio
async def test_complete_alias_arguments_do_not_call_a_model():
    from app.services.schema_param_extractor import extract_action_args

    with patch("app.services.model_router.get_model_router") as router:
        args = await extract_action_args("slack.post_message", 'Post "Hello" to #sales in Slack',
                                        existing_args={"channel": "sales", "message": "Hello"})
    assert args["message"] == "Hello"
    router.assert_not_called()


@pytest.mark.asyncio
async def test_optional_extraction_times_out_to_clarification(monkeypatch):
    import asyncio
    import app.services.schema_param_extractor as extractor

    async def slow_model(**kwargs):
        await asyncio.sleep(10)

    monkeypatch.setattr(extractor, "EXTRACTION_TIMEOUT_SECONDS", 0.01)
    router = MagicMock()
    router.complete = slow_model
    with patch("app.services.model_router.get_model_router", return_value=router):
        args = await extractor.extract_action_args("slack.post_message", "Post to Slack", existing_args={})
    assert not args.get("text")


def test_sentiment_adapts_uncertainty_without_inventing_urgency_or_frustration():
    service = SentimentFrictionService()
    assert service.analyze("Maybe use the other report")['recommended_adaptation'] == 'offer_options'
    assert service.analyze("Show today's report again")['recommended_adaptation'] == 'none'
    assert service.analyze("ASAP please, this is urgent")['recommended_adaptation'] == 'reduce_verbosity'
    assert service.analyze("THIS IS STILL NOT WORKING")['recommended_adaptation'] == 'acknowledge_briefly'


def test_learning_delivery_reports_disabled_handler_and_filters_tenant():
    from app.services.outcome_learning_handler import learning_delivery_status

    client = MagicMock()
    query = client.table.return_value
    query.select.return_value = query
    query.eq.return_value = query
    query.in_.return_value = query
    query.order.return_value = query
    query.limit.return_value = query
    query.execute.return_value = SimpleNamespace(data=[{"event_id": "evt-1", "status": "pending"}], count=5)
    settings = SimpleNamespace(domain_event_relay_enabled=True, outcome_learning_handler_enabled=False)
    result = learning_delivery_status(client, settings, org_id="org-1")
    assert result["status"] == "blocked"
    assert result["blockers"] == ["outcome_handler_disabled"]
    assert result["undelivered_count"] == 5
    assert result["delivery_is_not_verified_learning"] is True
    query.eq.assert_any_call("org_id", "org-1")
    with pytest.raises(ValueError):
        learning_delivery_status(client, settings, org_id="")
    settings.outcome_learning_handler_enabled = True
    with patch("app.services.outcome_learning_handler.handlers_for", return_value=[]):
        result = learning_delivery_status(client, settings, org_id="org-1")
    assert result["blockers"] == ["outcome_handler_not_registered"]
