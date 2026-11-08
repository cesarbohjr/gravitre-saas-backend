"""P27-08 dedicated queue/orphan worker OS process, no HTTP server.

The parent FastAPI process supervises this command; it does not supervise
itself or spawn any additional Railway service. A process crash cannot
terminate the API and the parent starts a replacement.
"""
from __future__ import annotations

import asyncio

from app.config import get_settings
from app.core.logging import get_logger, setup_logging
from app.workers.workflow_worker import _worker_loop

logger = get_logger(__name__)


def main() -> None:
    setup_logging(None)
    settings = get_settings()
    if not bool(getattr(settings, "workflow_worker_process_isolation_enabled", False)):
        raise SystemExit("P27 isolated worker entrypoint requires opt-in flag")
    if not bool(getattr(settings, "workflow_queue_enabled", True)):
        raise SystemExit("P27 isolated worker requires enabled workflow queue")
    logger.info("isolated_workflow_worker_child_ready")
    poll = max(1, int(getattr(settings, "workflow_queue_poll_seconds", 5) or 5))
    asyncio.run(_worker_loop(poll, settings))


if __name__ == "__main__":
    main()
