"""Handler protocol for partner connector actions (STA-70)."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

from app.services.tool_types import NormalizedResult, ToolContext, ToolValidationError

ToolExecutor = Callable[[ToolContext, dict[str, Any]], NormalizedResult]


class ConnectorActionHandler(Protocol):
    """Partner-implemented action handler."""

    def execute(self, ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
        """Run the action against the connected vendor API."""


class BaseConnectorHandler:
    """Optional base class for partner handlers with shared helpers."""

    vendor: str

    def __init__(self, vendor: str) -> None:
        self.vendor = vendor

    def ok(self, action: str, data: dict[str, Any], *, connector_id: str | None = None) -> NormalizedResult:
        """Return a successful normalized result."""
        return NormalizedResult(success=True, action=action, data=data, connector_id=connector_id)

    def fail(
        self,
        action: str,
        message: str,
        *,
        code: str = "tool_error",
        connector_id: str | None = None,
    ) -> NormalizedResult:
        """Return a failed normalized result without raising."""
        return NormalizedResult(
            success=False,
            action=action,
            error_code=code,
            error_message=message,
            connector_id=connector_id,
        )

    def require_params(self, params: dict[str, Any], *keys: str) -> None:
        """Raise ToolValidationError when required params are missing."""
        missing = [key for key in keys if not params.get(key)]
        if missing:
            raise ToolValidationError(f"Missing required params: {', '.join(missing)}")
