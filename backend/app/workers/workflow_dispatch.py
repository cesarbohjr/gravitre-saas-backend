"""Workflow run queue dispatch helpers (STA-94)."""
from __future__ import annotations

import asyncio
from typing import Any

from app.config import Settings
from app.services.data_residency_service import resolve_execution_region
from app.workers.queue import is_queue_available
from app.workers.workflow_queue import WorkflowRunJob, enqueue_workflow_run


def _queue_enabled(settings: Settings) -> bool:
    return bool(getattr(settings, "workflow_queue_enabled", True)) and is_queue_available()


def load_org_settings_and_region(client: Any, org_id: str) -> tuple[dict[str, Any], str]:
    row = (
        client.table("organizations")
        .select("settings,data_region")
        .eq("id", org_id)
        .limit(1)
        .execute()
    )
    if not row.data:
        return {}, "us"
    org_row = row.data[0]
    settings = org_row.get("settings") or {}
    org_settings = settings if isinstance(settings, dict) else {}
    column_region = org_row.get("data_region")
    region = resolve_execution_region(org_settings, data_region=column_region)
    return org_settings, region


async def try_enqueue_workflow_run(
    settings: Settings,
    client: Any,
    *,
    org_id: str,
    workflow_id: str,
    run_id: str,
) -> bool:
    """Enqueue a workflow run when the durable queue is available."""
    if not _queue_enabled(settings):
        return False
    _org_settings, region = load_org_settings_and_region(client, org_id)
    await enqueue_workflow_run(
        WorkflowRunJob(
            run_id=run_id,
            org_id=org_id,
            workflow_id=workflow_id,
            region=region,
            idempotency_key=run_id,
        )
    )
    return True


def try_enqueue_workflow_run_sync(
    settings: Settings,
    client: Any,
    *,
    org_id: str,
    workflow_id: str,
    run_id: str,
) -> bool:
    """Enqueue from sync contexts (schedule dispatcher thread pool)."""
    if not _queue_enabled(settings):
        return False

    async def _enqueue() -> bool:
        return await try_enqueue_workflow_run(
            settings,
            client,
            org_id=org_id,
            workflow_id=workflow_id,
            run_id=run_id,
        )

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(_enqueue())
    # Nested loop: run in a fresh loop on this thread.
    return asyncio.run(_enqueue())
