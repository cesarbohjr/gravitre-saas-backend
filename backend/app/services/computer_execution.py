"""Computer / browser execution on the canonical task — not a second brain.

Reuse ExecutionPlan, HMAC/PendingAction, Observations, Composer.
Does not start paid Browserbase/Steel infrastructure.
API-native WRITEs stay on ActionSpec; browser is only for graphical gaps.
"""
from __future__ import annotations

from typing import Any, Literal
from uuid import uuid4

from app.config import Settings, get_settings
from app.services.browser_agent_service import BrowserAgentError, browser_agent_interact, browser_agent_read
from app.services.execution_plan_service import ExecutionObservation, ExecutionPlan, ExecutionStep

ExecutionStrategy = Literal["api_native", "browser_cdp", "computer_use", "hybrid"]


def classify_execution_strategy(
    *,
    invoke_action: str | None = None,
    requires_graphical_ui: bool = False,
    has_action_spec: bool = False,
) -> ExecutionStrategy:
    """Choose API when a catalog action exists. Browser only for genuine UI work."""
    if requires_graphical_ui and invoke_action:
        return "hybrid"
    if requires_graphical_ui:
        return "browser_cdp"
    if has_action_spec or str(invoke_action or "").strip():
        return "api_native"
    return "browser_cdp"


def observation_from_browser_result(
    *,
    plan: ExecutionPlan,
    result: dict[str, Any],
    approval_id: str | None = None,
) -> ExecutionObservation:
    success = bool(result.get("success", True)) and not result.get("pending_approval")
    return ExecutionObservation(
        observation_id=str(uuid4()),
        step_id="computer_primary",
        connector_id="browser",
        success=success,
        summary=str(result.get("title") or result.get("message") or result.get("url") or "browser result")[:500],
        structured={
            "success": success,
            "url": result.get("url"),
            "action": result.get("mode") or result.get("action") or "browser_cdp",
            "screenshot_digest": result.get("screenshot_digest"),
            "dom_excerpt": str(result.get("text") or "")[:800],
            "cdp_trace_id": result.get("cdp_trace_id"),
            "approval_id": approval_id or result.get("approval_id"),
            "strategy": "browser_cdp",
            "pending_approval": bool(result.get("pending_approval")),
        },
        plan_id=plan.plan_id,
        source="computer_execution",
    )


async def execute_browser_cdp_read(
    url: str,
    *,
    plan: ExecutionPlan | None = None,
    settings: Settings | None = None,
) -> tuple[dict[str, Any], ExecutionObservation]:
    """Public-URL READ via existing browser agent (httpx). Not a live headful vendor."""
    active = settings or get_settings()
    exec_plan = plan or ExecutionPlan(
        plan_id=str(uuid4()),
        summary=f"Read {url}",
        source="computer_execution",
        steps=[ExecutionStep(step_id="computer_primary", title="Browser read", kind="read")],
    )
    try:
        raw = await browser_agent_read(url, settings=active)
        raw["success"] = True
        raw["mode"] = "httpx_read"
    except BrowserAgentError as exc:
        raw = {"success": False, "url": url, "message": str(exc), "mode": "httpx_read"}
    return raw, observation_from_browser_result(plan=exec_plan, result=raw)


async def stage_computer_use_interact(
    url: str,
    *,
    actions: list[dict[str, Any]] | None = None,
    approval_id: str | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """UI automation stays approval-gated. Disabled unless interact flag is on."""
    return await browser_agent_interact(
        url,
        actions=actions,
        settings=settings or get_settings(),
        approval_id=approval_id,
    )
