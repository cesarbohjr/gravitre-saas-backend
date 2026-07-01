"""Temporal worker — runs alongside asyncio schedulers when TEMPORAL_HOST is set."""
from __future__ import annotations

import os

from temporalio.client import Client
from temporalio.worker import Worker

from app.core.logging import get_logger
from app.temporal.activities import (
    install_marketplace_asset,
    install_marketplace_asset_step,
    load_outcome_baseline,
    measure_outcome_after_window,
    run_company_intelligence_for_org,
    run_memory_promotion_evaluation,
    train_ml_model_for_org,
)
from app.temporal.workflows import (
    CompanyIntelligenceWorkflow,
    MarketplaceInstallWorkflow,
    MemoryPromotionWorkflow,
    MLModelTrainingWorkflow,
    OutcomeMeasurementWorkflow,
)

logger = get_logger(__name__)

TASK_QUEUE = "gravitre-main"

_WORKFLOWS = [
    CompanyIntelligenceWorkflow,
    MemoryPromotionWorkflow,
    OutcomeMeasurementWorkflow,
    MarketplaceInstallWorkflow,
    MLModelTrainingWorkflow,
]

_ACTIVITIES = [
    run_company_intelligence_for_org,
    run_memory_promotion_evaluation,
    load_outcome_baseline,
    measure_outcome_after_window,
    install_marketplace_asset,
    install_marketplace_asset_step,
    train_ml_model_for_org,
]


def temporal_configured() -> bool:
    return bool((os.environ.get("TEMPORAL_HOST") or "").strip())


async def get_temporal_client() -> Client:
    host = os.environ.get("TEMPORAL_HOST", "localhost:7233")
    namespace = os.environ.get("TEMPORAL_NAMESPACE", "default")
    api_key = (os.environ.get("TEMPORAL_API_KEY") or "").strip()
    connect_kwargs: dict = {"namespace": namespace}
    if api_key:
        connect_kwargs["api_key"] = api_key
        connect_kwargs["tls"] = True
    return await Client.connect(host, **connect_kwargs)


async def start_temporal_worker() -> None:
    if not temporal_configured():
        logger.warning("Temporal worker not started — TEMPORAL_HOST unset")
        return
    client = await get_temporal_client()
    worker = Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=_WORKFLOWS,
        activities=_ACTIVITIES,
    )
    logger.info("Temporal worker started task_queue=%s", TASK_QUEUE)
    await worker.run()


def registered_workflow_names() -> list[str]:
    return [wf.__name__ for wf in _WORKFLOWS]
