from app.services.workflow_approval_scope import (
    seal_approval_scope,
    step_allowed_by_scope,
)


def test_seal_captures_invoke_tool_write():
    definition = {
        "steps": [
            {"id": "1", "type": "invoke_tool", "config": {"action": "hubspot.contacts.create"}},
            {"id": "2", "type": "slack_post_message", "config": {}},
        ]
    }
    scope = seal_approval_scope(definition)
    assert "hubspot.contacts.create" in scope["allowed_invoke_actions"]
    assert "slack_post_message" in scope["allowed_external_step_types"]


def test_runtime_step_outside_scope_blocked():
    scope = seal_approval_scope(
        {"steps": [{"id": "1", "type": "invoke_tool", "config": {"action": "hubspot.contacts.create"}}]}
    )
    ok = step_allowed_by_scope(
        step_type="invoke_tool",
        config={"action": "hubspot.deals.create"},
        scope=scope,
    )
    assert ok is False


def test_runtime_step_in_scope_allowed():
    scope = seal_approval_scope(
        {"steps": [{"id": "1", "type": "invoke_tool", "config": {"action": "hubspot.contacts.create"}}]}
    )
    assert step_allowed_by_scope(
        step_type="invoke_tool",
        config={"action": "hubspot.contacts.create"},
        scope=scope,
    )
