"""Types and errors for the unified agent/workflow tool layer (STA-10)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.config import Settings


class ToolError(Exception):
    """Base error for tool invocation."""

    code: str = "tool_error"

    def __init__(self, message: str, *, code: str | None = None, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        if code:
            self.code = code
        self.details = details or {}


class ToolAuthExpiredError(ToolError):
    code = "auth_expired"


class ToolRateLimitedError(ToolError):
    code = "rate_limited"


class ToolValidationError(ToolError):
    code = "validation_error"


class ToolPermissionDeniedError(ToolValidationError):
    code = "permission_denied"


class ToolNotFoundError(ToolError):
    code = "action_not_found"


@dataclass(frozen=True)
class ToolContext:
    """Execution context for invoke_tool — workflows, agents, or operators."""

    settings: Settings
    client: Any
    org_id: str
    actor_id: str
    environment_name: str = "production"
    run_id: str | None = None
    task_id: str | None = None
    agent_id: str | None = None
    operator_id: str | None = None
    transparency_log_id: str | None = None
    connector_id: str | None = None
    step_id: str | None = None
    step_type: str | None = None
    connector_timeout_seconds: int | None = None


@dataclass
class NormalizedResult:
    """Vendor-neutral tool result."""

    success: bool
    action: str
    data: dict[str, Any] = field(default_factory=dict)
    error_code: str | None = None
    error_message: str | None = None
    connector_id: str | None = None
    latency_ms: int | None = None

    def to_step_output(self) -> dict[str, Any]:
        if self.success:
            return dict(self.data)
        raise self.to_exception()

    def to_exception(self) -> ToolError:
        code = self.error_code or "tool_error"
        msg = self.error_message or "Tool invocation failed"
        if code == "auth_expired":
            return ToolAuthExpiredError(msg, details={"action": self.action})
        if code == "rate_limited":
            return ToolRateLimitedError(msg, details={"action": self.action})
        if code == "validation_error":
            return ToolValidationError(msg, details={"action": self.action})
        return ToolError(msg, code=code, details={"action": self.action})


def contact_record(**fields: Any) -> dict[str, Any]:
    return {"type": "contact", **fields}


def deal_record(**fields: Any) -> dict[str, Any]:
    return {"type": "deal", **fields}


def ticket_record(**fields: Any) -> dict[str, Any]:
    return {"type": "ticket", **fields}
