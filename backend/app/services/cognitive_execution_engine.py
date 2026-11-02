"""Phase C — parallel READ execution and normalized observations."""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from app.core.logging import get_logger
from app.core.safe_dict import safe_normalize_stored_dict
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
    """Run pending READ/evidence steps concurrently. WRITEs are never included."""
    from app.services.reasoning_evidence_pipeline import parallel_safe_steps

    if plan.terminal_status == "cancelled":
        return []
    read_steps = [s for s in parallel_safe_steps(plan) if s.status == "pending"]
    if not read_steps:
        return []

    sem = asyncio.Semaphore(max(1, max_parallel))

    async def _run(step: ExecutionStep) -> ExecutionObservation:
        async with sem:
            try:
                obs = await handler(step, context)
                if (obs.step_id != step.step_id
                        or (obs.plan_id and obs.plan_id != plan.plan_id)
                        or (step.connector_id and obs.connector_id != step.connector_id)):
                    return ExecutionObservation(
                        step_id=step.step_id, connector_id=str(step.connector_id or "unknown"),
                        success=False, summary="Read returned mismatched execution identity",
                        error="observation_identity_mismatch", plan_id=plan.plan_id,
                    )
                obs.plan_id = obs.plan_id or plan.plan_id
                return obs
            except Exception as exc:  # noqa: BLE001
                logger.warning("execution_read_step_failed error_type=%s", type(exc).__name__)
                return ExecutionObservation(
                    step_id=step.step_id, connector_id=str(step.connector_id or "unknown"),
                    success=False, summary="Read step could not be completed",
                    error="read_execution_failed", plan_id=plan.plan_id,
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
                structured=safe_normalize_stored_dict(item.get("structured")),
                error=item.get("error"),
            )
        )
    return out


def apply_observations_to_plan(
    plan: ExecutionPlan,
    observations: list[ExecutionObservation],
) -> ExecutionPlan:
    """Reuse the canonical verifier, cancellation and whole-plan terminal policy."""
    from app.services.execution_plan_service import apply_observations_to_plan as reconcile

    return reconcile(plan, observations)
