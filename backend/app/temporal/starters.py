"""Start Temporal workflows from API/cron paths."""
from __future__ import annotations

import os
from typing import Any

from app.core.logging import get_logger
from app.temporal.worker import TASK_QUEUE, get_temporal_client, temporal_configured
from app.temporal.workflows import (
    CompanyIntelligenceWorkflow,
    MarketplaceInstallWorkflow,
    MemoryPromotionWorkflow,
    MLModelTrainingWorkflow,
    OutcomeMeasurementWorkflow,
)

logger = get_logger(__name__)


async def start_company_intelligence_workflow(org_id: str) -> dict[str, Any]:
    client = await get_temporal_client()
    handle = await client.start_workflow(
        CompanyIntelligenceWorkflow.run,
        org_id,
        id=f"company-intelligence-{org_id}",
        task_queue=TASK_QUEUE,
    )
    return {"workflow_id": handle.id, "run_id": handle.result_run_id}


async def start_memory_promotion_workflow(org_id: str) -> dict[str, Any]:
    client = await get_temporal_client()
    handle = await client.start_workflow(
        MemoryPromotionWorkflow.run,
        org_id,
        id=f"memory-promotion-{org_id}",
        task_queue=TASK_QUEUE,
    )
    return {"workflow_id": handle.id, "run_id": handle.result_run_id}


async def start_outcome_measurement_workflow(outcome_id: str) -> dict[str, Any]:
    client = await get_temporal_client()
    handle = await client.start_workflow(
        OutcomeMeasurementWorkflow.run,
        outcome_id,
        id=f"outcome-measurement-{outcome_id}",
        task_queue=TASK_QUEUE,
    )
    return {"workflow_id": handle.id, "run_id": handle.result_run_id}


async def start_marketplace_install_workflow(
    asset_ids: list[str],
    org_id: str,
    install_variables: dict[str, Any] | None = None,
    *,
    actor_id: str = "system",
) -> dict[str, Any]:
    client = await get_temporal_client()
    handle = await client.start_workflow(
        MarketplaceInstallWorkflow.run,
        args=[asset_ids, org_id, install_variables or {}, actor_id],
        id=f"marketplace-install-{org_id}-{asset_ids[0]}",
        task_queue=TASK_QUEUE,
    )
    return {"workflow_id": handle.id, "run_id": handle.result_run_id}


async def start_ml_model_training_workflow(org_id: str, model_name: str) -> dict[str, Any]:
    if not temporal_enabled():
        return {"temporal": False}
    client = await get_temporal_client()
    handle = await client.start_workflow(
        MLModelTrainingWorkflow.run,
        args=[org_id, model_name],
        id=f"ml-training-{org_id}-{model_name}",
        task_queue=TASK_QUEUE,
    )
    return {
        "temporal": True,
        "workflow_id": handle.id,
        "run_id": handle.result_run_id,
        "model_name": model_name,
    }


def temporal_enabled() -> bool:
    return temporal_configured() and bool((os.environ.get("TEMPORAL_API_KEY") or "").strip())
