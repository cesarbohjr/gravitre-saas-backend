"""Supervise a dedicated workflow-worker OS process inside the existing API container.

One Railway service/replica, no extra infrastructure. The API never imports
or processes workflow queue jobs in isolation mode. The child inherits the
same existing configuration and executes only the workflow worker loop.
If the child is SIGKILLed, the API stays alive and supervision replaces it.
The existing Redis claim and SQL orphan lease retain durable ownership.
"""
from __future__ import annotations

import asyncio
import sys

from app.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Fixed module command, no shell or untrusted arguments.
WORKER_COMMAND = (sys.executable, "-m", "app.workers.workflow_worker_process")


async def _stop_child(child: asyncio.subprocess.Process) -> None:
    if child.returncode is not None:
        return
    try:
        child.terminate()
    except ProcessLookupError:
        return
    try:
        await asyncio.wait_for(child.wait(), timeout=5)
    except asyncio.TimeoutError:
        logger.warning("isolated_workflow_worker_graceful_stop_timed_out")
        if child.returncode is None:
            try:
                child.kill()
            except ProcessLookupError:
                pass
        await child.wait()


async def supervise_workflow_worker(*, command: tuple[str, ...] = WORKER_COMMAND,
                                    restart_delay: float = 2.0,
                                    on_started=None) -> None:
    """Keep exactly one child per API process; await termination and restart.

    If the backend is ever scaled to multiple replicas, Redis claims and SQL
    leases (not this process-local singleton) remain the cross-replica fences.
    """
    child = None
    try:
        while True:
            try:
                child = await asyncio.create_subprocess_exec(*command)
                logger.info("isolated_workflow_worker_started pid=%s", child.pid)
                if on_started is not None:
                    on_started(child)
                code = await child.wait()
                logger.warning(
                    "isolated_workflow_worker_exited pid=%s code=%s restart=true",
                    child.pid, code)
                child = None
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "isolated_workflow_worker_start_failed reason=%s",
                    type(exc).__name__)
            await asyncio.sleep(max(1.0, restart_delay))
    finally:
        if child is not None:
            await _stop_child(child)


def start_isolated_workflow_worker() -> asyncio.Task | None:
    settings = get_settings()
    if not bool(getattr(settings, "workflow_worker_process_isolation_enabled", False)):
        return None
    if not bool(getattr(settings, "workflow_queue_enabled", True)):
        logger.info("isolated_workflow_worker_disabled queue=false")
        return None
    logger.info("isolated_workflow_worker_supervisor_enabled")
    return asyncio.create_task(supervise_workflow_worker())


async def stop_isolated_workflow_worker(task: asyncio.Task | None) -> None:
    if task is None:
        return
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
