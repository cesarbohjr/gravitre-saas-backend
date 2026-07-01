"""Temporal workflows replacing fire-and-forget asyncio jobs for correctness-critical work."""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from app.temporal.activities import (
        install_marketplace_asset_step,
        load_outcome_baseline,
        measure_outcome_after_window,
        run_company_intelligence_for_org,
        run_memory_promotion_evaluation,
    )


@workflow.defn
class CompanyIntelligenceWorkflow:
    """Durable company intelligence snapshot per org (replaces asyncio scheduler tick)."""

    @workflow.run
    async def run(self, org_id: str) -> dict[str, Any]:
        return await workflow.execute_activity(
            run_company_intelligence_for_org,
            org_id,
            start_to_close_timeout=timedelta(minutes=30),
            retry_policy=RetryPolicy(
                maximum_attempts=3,
                initial_interval=timedelta(seconds=30),
            ),
        )


@workflow.defn
class MemoryPromotionWorkflow:
    """Memory promotion evaluation per org (replaces 8h asyncio promotion loop)."""

    @workflow.run
    async def run(self, org_id: str) -> dict[str, Any]:
        return await workflow.execute_activity(
            run_memory_promotion_evaluation,
            org_id,
            start_to_close_timeout=timedelta(minutes=15),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )


@workflow.defn
class OutcomeMeasurementWorkflow:
    """Delayed outcome measurement — sleeps until attribution window elapses."""

    @workflow.run
    async def run(self, outcome_id: str) -> dict[str, Any]:
        baseline = await workflow.execute_activity(
            load_outcome_baseline,
            outcome_id,
            start_to_close_timeout=timedelta(seconds=30),
        )
        await workflow.sleep(timedelta(days=int(baseline["attribution_window_days"])))
        return await workflow.execute_activity(
            measure_outcome_after_window,
            outcome_id,
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )


@workflow.defn
class MarketplaceInstallWorkflow:
    """Checkpointed marketplace install — one activity per asset in a bulk install."""

    @workflow.run
    async def run(
        self,
        asset_ids: list[str],
        org_id: str,
        install_variables: dict[str, Any] | None = None,
        *,
        actor_id: str = "system",
    ) -> dict[str, Any]:
        results: list[dict[str, Any]] = []
        for asset_id in asset_ids:
            step = await workflow.execute_activity(
                install_marketplace_asset_step,
                {
                    "asset_id": asset_id,
                    "org_id": org_id,
                    "install_variables": install_variables or {},
                    "actor_id": actor_id,
                },
                start_to_close_timeout=timedelta(minutes=10),
                retry_policy=RetryPolicy(maximum_attempts=3),
            )
            results.append(step)
        return {"installed": len(results), "steps": results}
