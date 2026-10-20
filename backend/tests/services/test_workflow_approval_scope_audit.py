from app.services.workflow_approval_scope import (
    block_invoke_by_approval_scope,
    definition_digest_matches,
)


def test_digest_mismatch_blocks():
    scope = {"definition_digest": "aaa", "allowed_invoke_actions": ["slack.messages.post"]}
    assert not definition_digest_matches(scope, {"schema_version": "v1", "steps": []})


def test_missing_scope_blocks_approved_run():
    run = {"required_approvals": 1, "parameters": {}}
    blocked = block_invoke_by_approval_scope(
        invoke_action="slack.messages.post",
        run_row=run,
        run_parameters={},
        definition={"schema_version": "v1", "steps": []},
    )
    assert blocked is not None and blocked["reason"] == "approval_scope_missing"
