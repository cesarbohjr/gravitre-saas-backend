"""Alternate parallel fan-out scheduler for swarm subtasks (STA-270)."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Awaitable

logger = logging.getLogger(__name__)


class ParallelFanout:
    """Create all swarm subtask jobs first, then enqueue in parallel."""

    async def fanout(
        self,
        items: list[tuple[str, Callable[[], Awaitable[None]]]],
    ) -> list[str | BaseException]:
        """Run enqueue callbacks concurrently; returns per-item results (exceptions preserved)."""
        if not items:
            return []
        results = await asyncio.gather(
            *(callback() for _, callback in items),
            return_exceptions=True,
        )
        for job_id, result in zip((job_id for job_id, _ in items), results, strict=True):
            if isinstance(result, Exception):
                logger.warning("parallel fanout enqueue failed job_id=%s error=%s", job_id, result)
        return results

    @staticmethod
    def coordination_payload(
        *,
        objective: str,
        swarm_run_id: str,
        shared_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "objective": objective,
            "swarmRunId": swarm_run_id,
            "scheduler": "parallel_fanout",
        }
        if shared_context:
            payload["channel"] = shared_context
        return payload
