"""Fail-closed autonomous task admission contract.

Pure validation only: never executes, schedules or grants connector actions.
Actual authorization must be re-evaluated at every runtime dispatch.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ActionType = Literal["read", "write"]


@dataclass(frozen=True)
class AutonomousStep:
    step_id: str
    capability: str
    action_type: ActionType
    depends_on: tuple[str, ...] = ()
    approval_required: bool = True
    idempotency_key: str | None = None


@dataclass(frozen=True)
class AutonomousTask:
    task_id: str
    tenant_id: str
    actor_id: str
    goal: str
    steps: tuple[AutonomousStep, ...]
    max_steps: int = 12
    max_replans: int = 2


class InvalidAutonomousTask(ValueError):
    pass


def validate_task(task: AutonomousTask) -> AutonomousTask:
    """Reject ambiguous or unbounded plans before they enter the executor."""
    if not all((task.task_id.strip(), task.tenant_id.strip(), task.actor_id.strip(), task.goal.strip())):
        raise InvalidAutonomousTask("missing_task_identity")
    if not 1 <= task.max_steps <= 64 or not 0 <= task.max_replans <= 8:
        raise InvalidAutonomousTask("invalid_budgets")
    if not task.steps or len(task.steps) > task.max_steps:
        raise InvalidAutonomousTask("invalid_step_count")
    seen: set[str] = set()
    keys: set[str] = set()
    for step in task.steps:
        if not step.step_id.strip() or not step.capability.strip() or step.step_id in seen:
            raise InvalidAutonomousTask("invalid_step_identity")
        if step.action_type not in {"read", "write"}:
            raise InvalidAutonomousTask("unknown_action_type")
        if any(dependency not in seen for dependency in step.depends_on):
            raise InvalidAutonomousTask("missing_or_forward_dependency")
        if len(set(step.depends_on)) != len(step.depends_on):
            raise InvalidAutonomousTask("duplicate_dependency")
        if step.action_type == "write":
            if not step.approval_required:
                raise InvalidAutonomousTask("write_must_require_approval")
            if not step.idempotency_key or not step.idempotency_key.strip():
                raise InvalidAutonomousTask("write_requires_idempotency_key")
            if step.idempotency_key in keys:
                raise InvalidAutonomousTask("duplicate_write_idempotency_key")
            keys.add(step.idempotency_key)
        seen.add(step.step_id)
    return task
