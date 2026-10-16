from app.services.canvas_write_gate import block_canvas_write_step


def test_block_step_outside_approval_scope():
    run_row = {"approval_status": "approved", "required_approvals": 1}
    scope = {
        "allowed_invoke_actions": ["hubspot.contacts.create"],
        "allowed_external_step_types": [],
    }
    blocked = block_canvas_write_step(
        step_type="invoke_tool",
        config={"action": "hubspot.deals.create"},
        run_row=run_row,
        run_parameters={"approval_scope": scope},
    )
    assert blocked is not None
    assert blocked.get("reason") == "approval_scope_mismatch"
