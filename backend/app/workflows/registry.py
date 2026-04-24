"""Step handler registry for execute and dry-run."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.config import Settings


@dataclass
class StepContext:
    settings: Settings
    org_id: str
    user_id: str | None
    run_id: str | None
    environment_name: str
    step_id: str
    step_type: str
    step_index: int
    config: dict[str, Any]
    parameters: dict[str, Any]
    step_outputs: dict[str, Any]
    client: Any | None
    is_dry_run: bool


class StepHandler:
    step_type: str = "unknown"
    supports_execute: bool = True

    def validate(self, context: StepContext) -> None:
        return None

    def simulate(self, context: StepContext) -> dict[str, Any]:
        raise NotImplementedError

    def execute(self, context: StepContext) -> dict[str, Any]:
        raise NotImplementedError

    def audit(self, context: StepContext, output: dict[str, Any] | None, error: Exception | None) -> None:
        return None


_HANDLERS: dict[str, StepHandler] = {}


def register_handler(handler: StepHandler) -> None:
    _HANDLERS[handler.step_type] = handler


def get_handler(step_type: str) -> StepHandler:
    handler = _HANDLERS.get(step_type)
    if not handler:
        raise ValueError(f"Unknown step type: {step_type}")
    return handler
