from app.services.canvas_write_gate import block_canvas_write_step
from app.services.workflow_approval_scope import seal_approval_scope


def test_block_step_outside_approval_scope():
    definition = {"steps": [{"type": "invoke_tool", "config": {"action": "hubspot.contacts.create"}}]}
    run_row = {"approval_status": "approved", "required_approvals": 1, "definition_snapshot": definition}
    scope = seal_approval_scope(definition)
    blocked = block_canvas_write_step(
        step_type="invoke_tool",
        config={"action": "hubspot.deals.create"},
        run_row=run_row,
        run_parameters={"approval_scope": scope},
    )
    assert blocked is not None
    assert blocked.get("reason") == "approval_scope_mismatch"
