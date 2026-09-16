"""Phase C — parallel READ execution and normalized observations."""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from app.core.logging import get_logger
from app.services.execution_plan_service import ExecutionObservation, ExecutionPlan, ExecutionStep

logger = get_logger(__name__)

ReadStepHandler = Callable[[ExecutionStep, dict[str, Any]], Awaitable[ExecutionObservation]]


async def execute_read_steps_parallel(
    plan: ExecutionPlan,
    *,
    context: dict[str, Any],
    handler: ReadStepHandler,
    max_parallel: int = 4,
) -> list[ExecutionObservation]:
    """Run pending READ steps concurrently; normalize to ExecutionObservation[]."""
    read_steps = [s for s in plan.steps if s.kind == "read" and s.status == "pending"]
    if not read_steps:
        return []

    sem = asyncio.Semaphore(max(1, max_parallel))

    async def _run(step: ExecutionStep) -> ExecutionObservation:
        async with sem:
            try:
                obs = await handler(step, context)
                obs.plan_id = obs.plan_id or plan.plan_id
                return obs
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "execution_step_failed step_id=%s connector=%s error=%s",
                    step.step_id,
                    step.connector_id,
                    exc,
                )
        return ExecutionObservation(
                    step_id=step.step_id,
                    connector_id=str(step.connector_id or "unknown"),
                    success=False,
                    summary=f"Step failed: {exc}",
                    error=str(exc)[:300],
                    plan_id=plan.plan_id,
                )

    results = await asyncio.gather(*(_run(step) for step in read_steps))
    return list(results)


def normalize_observations(raw: list[Any]) -> list[ExecutionObservation]:
    """Coerce mixed result rows into ExecutionObservation records."""
    out: list[ExecutionObservation] = []
    for item in raw:
        if isinstance(item, ExecutionObservation):
            out.append(item)
            continue
        if not isinstance(item, dict):
            continue
        out.append(
            ExecutionObservation(
                step_id=str(item.get("step_id") or ""),
                connector_id=str(item.get("connector_id") or ""),
                success=bool(item.get("success")),
                summary=str(item.get("summary") or ""),
                structured=dict(item.get("structured") or {}),
                error=item.get("error"),
            )
        )
    return out


def apply_observations_to_plan(
    plan: ExecutionPlan,
    observations: list[ExecutionObservation],
) -> ExecutionPlan:
    """Mark steps completed/failed from observation results."""
    by_step = {o.step_id: o for o in observations}
    updated_steps: list[ExecutionStep] = []
    for step in plan.steps:
        obs = by_step.get(step.step_id)
        if obs is None:
            updated_steps.append(step)
            continue
        status = "completed" if obs.success else "failed"
        updated_steps.append(
            ExecutionStep(
                step_id=step.step_id,
                title=step.title,
                kind=step.kind,
                connector_id=step.connector_id,
                capability_id=step.capability_id,
                action_key=step.action_key,
                status=status,
                meta={**step.meta, "observation_summary": obs.summary[:200]},
            )
        )
    plan.steps = updated_steps
    if observations and all(o.success for o in observations):
        plan.terminal_status = "completed"
    elif observations and any(not o.success for o in observations):
        plan.terminal_status = "partial" if any(o.success for o in observations) else "failed"
    return plan
