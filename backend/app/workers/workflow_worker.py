"""Background consumer for durable workflow run queue (STA-94)."""
from __future__ import annotations

import asyncio
from typing import Any

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.workflows.execute import execute_workflow_steps
from app.workflows.repository import get_run_with_steps, get_supabase_client
from app.workers.workflow_queue import dequeue_workflow_run, parse_workflow_run_job

logger = get_logger(__name__)


def process_workflow_run_job(settings: Settings, job_raw: str) -> bool:
    """Execute one queued workflow run. Returns True when a job was processed."""
    job = parse_workflow_run_job(job_raw)
    if job is None:
        logger.warning("workflow_worker_invalid_job payload=%s", job_raw[:200])
        return True

    client = get_supabase_client(settings)
    run = get_run_with_steps(client, job.org_id, job.run_id)
    if not run:
        logger.warning(
            "workflow_worker_run_missing org_id=%s run_id=%s",
            job.org_id,
            job.run_id,
        )
        return True

    definition = run.get("definition_snapshot") or {}
    parameters = run.get("parameters") or {}
    actor_id = str(run.get("triggered_by") or "system")
    environment_name = str(run.get("environment") or "default")

    try:
        final_status, step_rows, errors, rate_limited = execute_workflow_steps(
            settings=settings,
            org_id=job.org_id,
            user_id=actor_id,
            run_id=job.run_id,
            definition=definition,
            parameters=parameters,
            client=client,
            environment_name=environment_name,
        )
        logger.info(
            "workflow_worker_completed org_id=%s run_id=%s status=%s steps=%s rate_limited=%s errors=%s",
            job.org_id,
            job.run_id,
            final_status,
            len(step_rows),
            rate_limited,
            len(errors),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "workflow_worker_failed org_id=%s run_id=%s error=%s",
            job.org_id,
            job.run_id,
            str(exc),
        )
    return True


async def _worker_loop(poll_seconds: int, settings: Settings) -> None:
    while True:
        try:
            raw = await dequeue_workflow_run(timeout_seconds=poll_seconds)
            if raw:
                await asyncio.to_thread(process_workflow_run_job, settings, raw)
                continue
        except Exception as exc:  # noqa: BLE001
            logger.warning("workflow_worker_tick error=%s", str(exc))
        await asyncio.sleep(max(1, poll_seconds))


def start_workflow_run_worker() -> asyncio.Task | None:
    try:
        settings = get_settings()
        if not bool(getattr(settings, "workflow_queue_enabled", True)):
            logger.info("workflow run worker disabled")
            return None
        poll = int(getattr(settings, "workflow_queue_poll_seconds", 5) or 5)
    except Exception as exc:  # noqa: BLE001
        logger.warning("workflow run worker not started: %s", str(exc))
        return None
    logger.info("workflow run worker started poll=%ss", poll)
    return asyncio.create_task(_worker_loop(poll, settings))


async def stop_workflow_run_worker(task: asyncio.Task | None) -> None:
    if task is None:
        return
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    except Exception as exc:  # noqa: BLE001
        logger.warning("workflow run worker stop error: %s", str(exc))
