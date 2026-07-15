"""Regression: canvas write authority (P1-class — no approval-node bypass)."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.config import Settings
from app.policy.engine import PolicyContext, evaluate_policy
from app.services.canvas_write_gate import (
    CANVAS_WRITE_AUTHORITY_BLOCKED,
    block_canvas_write_step,
    definition_has_catalog_write_steps,
    run_allows_catalog_write_execution,
)
from app.workflows.handlers import InvokeToolHandler
from app.workflows.registry import StepContext


APOLLO_WRITE_DEF = {
    "schema_version": "2025.1",
    "steps": [
        {
            "id": "apollo_list_create",
            "name": "Apollo create list",
            "type": "invoke_tool",
            "config": {"action": "apollo.lists.create", "name": "x"},
        }
    ],
}

NOOP_DEF = {
    "schema_version": "2025.1",
    "steps": [{"id": "n", "name": "N", "type": "noop", "config": {}}],
}


def test_definition_detects_apollo_lists_create_as_write():
    assert definition_has_catalog_write_steps(APOLLO_WRITE_DEF) is True
    assert definition_has_catalog_write_steps(NOOP_DEF) is False


def test_policy_floor_forces_approval_for_invoke_tool_write_even_when_policy_zero():
    settings = Settings()
    decision = evaluate_policy(
        PolicyContext(
            settings=settings,
            org_id="org",
            workflow_id="wf",
            definition=APOLLO_WRITE_DEF,
            required_approvals=0,
            approver_roles=[],
        )
    )
    assert decision.allowed is True
    assert decision.required_approvals >= 1
    assert decision.approval_floor_applied is True
    assert decision.has_external_steps is True


def test_policy_noop_does_not_force_floor_when_zero():
    settings = Settings()
    decision = evaluate_policy(
        PolicyContext(
            settings=settings,
            org_id="org",
            workflow_id="wf",
            definition=NOOP_DEF,
            required_approvals=0,
            approver_roles=[],
        )
    )
    assert decision.required_approvals == 0
    assert decision.approval_floor_applied is False


def test_run_allows_write_only_when_required_approvals_and_approved():
    assert run_allows_catalog_write_execution({"required_approvals": 0, "approval_status": "approved"}) is False
    assert run_allows_catalog_write_execution({"required_approvals": 1, "approval_status": "pending_approval"}) is False
    assert run_allows_catalog_write_execution({"required_approvals": 1, "approval_status": "approved"}) is True


def test_block_canvas_write_step_for_unapproved_run():
    blocked = block_canvas_write_step(
        step_type="invoke_tool",
        config={"action": "apollo.lists.create"},
        run_row={"required_approvals": 0, "approval_status": "approved"},
    )
    assert blocked is not None
    assert blocked["error_code"] == CANVAS_WRITE_AUTHORITY_BLOCKED


def test_invoke_tool_handler_blocks_write_without_approval(monkeypatch):
    handler = InvokeToolHandler()
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[{"id": "run1", "status": "running", "approval_status": "approved", "required_approvals": 0}]
    )
    invoked = {"called": False}

    def _fake_invoke(*_a, **_k):
        invoked["called"] = True
        raise AssertionError("invoke_tool must not run when write authority blocks")

    monkeypatch.setattr("app.workflows.handlers.invoke_tool", _fake_invoke)
    ctx = StepContext(
        settings=Settings(),
        org_id="org",
        user_id="user",
        run_id="run1",
        environment_name="production",
        step_id="apollo_list_create",
        step_type="invoke_tool",
        step_index=0,
        config={"action": "apollo.lists.create", "name": "x"},
        parameters={},
        step_outputs={},
        client=client,
        is_dry_run=False,
    )
    with pytest.raises(PermissionError) as exc:
        handler.execute(ctx)
    assert CANVAS_WRITE_AUTHORITY_BLOCKED in str(exc.value)
    assert invoked["called"] is False
