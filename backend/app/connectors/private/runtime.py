"""Subprocess sandbox runtime for org-scoped private connector bundles (STA-98)."""
from __future__ import annotations

import json
import logging
import subprocess
import sys
from typing import Any

from app.config import Settings
from app.services.tool_types import NormalizedResult, ToolContext, ToolValidationError

logger = logging.getLogger(__name__)


def action_to_handler_name(action_id: str) -> str:
    """Map manifest action id to Python function name (tickets.list -> tickets_list)."""
    return action_id.replace(".", "_").replace("-", "_")


def run_private_handler(
    settings: Settings,
    *,
    handler_source: str,
    action: str,
    ctx: ToolContext,
    params: dict[str, Any],
) -> NormalizedResult:
    """Execute a private connector handler in an isolated subprocess."""
    if not settings.private_connector_runtime_enabled:
        raise ToolValidationError("Private connector runtime is disabled on this deployment")

    action_id = action.split(".", 1)[1] if "." in action else action
    function_name = action_to_handler_name(action_id)
    payload = {
        "handlerSource": handler_source,
        "functionName": function_name,
        "action": action,
        "params": params,
        "context": {
            "orgId": ctx.org_id,
            "userId": ctx.actor_id,
            "connectorId": ctx.connector_id,
            "runId": ctx.run_id,
        },
    }
    timeout = max(1, int(settings.private_connector_sandbox_timeout_sec))
    proc = subprocess.run(
        [sys.executable, "-m", "app.connectors.private.sandbox_runner"],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if proc.returncode != 0 and not proc.stdout.strip():
        logger.warning("private sandbox failed stderr=%s", proc.stderr[:500])
        raise ToolValidationError(proc.stderr.strip() or "Private connector sandbox failed")

    try:
        envelope = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise ToolValidationError("Private connector sandbox returned invalid JSON") from exc

    if not envelope.get("ok"):
        raise ToolValidationError(str(envelope.get("error") or "Private connector handler failed"))

    result = envelope.get("result") or {}
    return NormalizedResult(
        success=bool(result.get("success", True)),
        action=str(result.get("action") or action),
        data=result.get("data") if isinstance(result.get("data"), dict) else {},
        error_code=result.get("errorCode") or result.get("error_code"),
        error_message=result.get("errorMessage") or result.get("error_message"),
        connector_id=result.get("connectorId") or result.get("connector_id") or ctx.connector_id,
    )


def make_private_executor(handler_source: str, action: str, settings: Settings):
    """Return an invoke_tool-compatible executor bound to sandbox source."""

    def _executor(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
        return run_private_handler(settings, handler_source=handler_source, action=action, ctx=ctx, params=params)

    return _executor
