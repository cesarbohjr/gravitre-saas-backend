"""Fail-closed validation of autonomous task admission."""
from dataclasses import replace

import pytest

from app.services.autonomous_task_contract import (
    AutonomousStep, AutonomousTask, InvalidAutonomousTask, validate_task,
)


def task(*steps):
    return AutonomousTask("task-1", "tenant-1", "actor-1", "Research account", steps)


def test_read_then_approved_write_is_valid():
    steps = (
        AutonomousStep("search", "crm.search", "read"),
        AutonomousStep("update", "crm.update", "write", ("search",), True, "task-1:update"),
    )
    assert validate_task(task(*steps)).steps == steps


@pytest.mark.parametrize("invalid", [
    (AutonomousStep("update", "crm.update", "write", approval_required=False, idempotency_key="k"),),
    (AutonomousStep("update", "crm.update", "write"),),
    (AutonomousStep("b", "crm.read", "read", ("missing",)),),
    (AutonomousStep("a", "crm.read", "read"), AutonomousStep("a", "crm.read", "read")),
    (AutonomousStep("a", "crm.read", "read", ("a",)),),
    (AutonomousStep("a", "crm.read", "execute"),),
])
def test_invalid_plans_fail_closed(invalid):
    with pytest.raises(InvalidAutonomousTask):
        validate_task(task(*invalid))


def test_duplicate_write_keys_fail_closed():
    with pytest.raises(InvalidAutonomousTask, match="duplicate_write"):
        validate_task(task(
            AutonomousStep("a", "crm.update", "write", idempotency_key="same"),
            AutonomousStep("b", "crm.update", "write", idempotency_key="same"),
        ))


def test_budget_and_identity_requirements():
    valid = task(AutonomousStep("read", "crm.read", "read"))
    for modified in (replace(valid, tenant_id=" "), replace(valid, max_steps=0),
                     replace(valid, max_replans=9), replace(valid, steps=())):
        with pytest.raises(InvalidAutonomousTask):
            validate_task(modified)
