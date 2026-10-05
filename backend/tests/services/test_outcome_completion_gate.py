from __future__ import annotations

import pytest

from app.services.action_lifecycle import persist_uncertain_outcome_patch, persist_write_outcome_patch
from app.services.chat_connector_models import ConnectorActionPlan
from app.services.execution_plan_service import ExecutionPlan, ExecutionStep
from app.services.outcome_completion_gate import (
    completion_language_allowed,
    outcome_claim_from_state,
    require_verified_completion,
)


def _plan() -> ConnectorActionPlan:
    return ConnectorActionPlan(
        tool_name="hubspot_contacts_create",
        invoke_action="hubspot.contacts.create",
        integration="hubspot",
        kind="write",
        label="Create contact",
        args={"email": "ownership@example.invalid"},
        requires_approval=True,
    )


def _state() -> dict:
    return {
        "execution_plan": ExecutionPlan(
            plan_id="ownership",
            summary="Create and verify contact",
            source="test",
            terminal_status="running",
            steps=[
                ExecutionStep(
                    step_id="connector_primary",
                    title="Create contact",
                    kind="write",
                    action_key="hubspot.contacts.create",
                )
            ],
        ).as_dict(),
        "pending_task": {
            "type": "connector_action",
            "status": "awaiting_confirm",
            "params": {
                "invoke_action": "hubspot.contacts.create",
                "integration": "hubspot",
                "kind": "write",
                "args": {"email": "ownership@example.invalid"},
            },
        },
    }


def test_provider_success_is_not_completion_without_verification() -> None:
    state = persist_write_outcome_patch(
        task_state=_state(),
        connector_plan=_plan(),
        success=True,
        summary="provider accepted create",
        structured={"id": "123"},
        pending_task=_state()["pending_task"],
        verification=None,
    )
    claim = outcome_claim_from_state(state)
    assert claim.may_claim_executed is True
    assert claim.may_claim_complete is False
    assert claim.needs_verification is True
    assert completion_language_allowed(state) is False
    with pytest.raises(ValueError):
        require_verified_completion(state)


def test_verified_readback_allows_completion_claim() -> None:
    state = persist_write_outcome_patch(
        task_state=_state(),
        connector_plan=_plan(),
        success=True,
        summary="provider accepted create",
        structured={"id": "123"},
        pending_task=_state()["pending_task"],
        verification={"verified": True, "provider_record_id": "123"},
    )
    claim = outcome_claim_from_state(state)
    assert claim.may_claim_complete is True
    assert claim.needs_verification is False
    require_verified_completion(state)


def test_approval_is_not_completion() -> None:
    claim = outcome_claim_from_state(_state())
    assert claim.state == "AWAITING_APPROVAL"
    assert claim.may_claim_complete is False
    assert claim.may_claim_executed is False


def test_uncertain_write_requires_reconciliation_not_done_language() -> None:
    state = persist_uncertain_outcome_patch(
        task_state=_state(),
        connector_plan=_plan(),
        summary="provider timed out",
        error="timeout",
    )
    claim = outcome_claim_from_state(state)
    assert claim.state == "OUTCOME_UNCERTAIN"
    assert claim.may_claim_complete is False
    assert claim.needs_verification is True
