from app.services.execution_context import build_execution_context


def test_execution_context_projects_durable_state_without_inventing_completion():
    state = {
        "resolved_entities": {"contact": "sarah"},
        "execution_plan": {"id": "plan-1", "steps": [{"id": "send"}]},
        "execution_observations": [{"step": "lookup", "status": "completed"}],
        "work_artifacts": [{"id": "proposal-2", "kind": "document"}],
        "pending_action": {"status": "awaiting_approval", "step": "send"},
        "recent_connector_invocations": [
            {"vendor": "gmail", "action": "messages.send", "status": "accepted_async"},
            {"vendor": "hubspot", "action": "contacts.update", "verification_status": "verified"},
        ],
        "recent_user_messages": ["Use the latest proposal"],
        "pending_steps": [{"id": "send", "status": "pending"}],
    }

    context = build_execution_context(
        task_state=state,
        conversation_history=[
            {"role": "user", "content": "Send it to Sarah"},
            {"role": "assistant", "content": "I found Sarah."},
        ],
        surface="ai_chat",
        entry_point="composer",
        originating_modality="text",
    )

    assert context["version"] == 1
    assert context["originating_modality"] == "text"
    assert context["resolved_entities"] == {"contact": "sarah"}
    assert context["current_plan"]["id"] == "plan-1"
    assert context["pending_action"]["status"] == "awaiting_approval"
    assert context["referenced_artifacts"][0]["id"] == "proposal-2"
    assert context["conversation_tail"][-1]["content"] == "I found Sarah."
    assert len(context["prior_verified_actions"]) == 1
    assert context["prior_verified_actions"][0]["vendor"] == "hubspot"


def test_execution_context_keeps_intentional_repeat_as_context_not_dedupe_instruction():
    context = build_execution_context(
        task_state={
            "recent_connector_invocations": [
                {"vendor": "gmail", "action": "messages.send", "status": "completed"}
            ],
            "recent_user_messages": ["Send another one to John"],
        },
        originating_modality="voice",
    )

    assert context["originating_modality"] == "voice"
    assert context["recent_user_messages"] == ["Send another one to John"]
    assert "dedupe" not in context
    assert "block_repeat" not in context
