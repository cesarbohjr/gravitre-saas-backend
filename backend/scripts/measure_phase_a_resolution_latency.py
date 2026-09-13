"""Local Phase A resolution latency probe (no LLM)."""
from __future__ import annotations

import asyncio
import statistics
import time
from types import SimpleNamespace

from app.services.cognitive_resolution_pipeline import run_cognitive_resolution


async def _bench(message: str, *, connected: list[str] | None = None, state: dict | None = None, n: int = 50) -> dict:
    durations: list[float] = []
    for _ in range(n):
        t0 = time.perf_counter()
        await run_cognitive_resolution(
            message=message,
            task_state=state or {},
            tenant_id="org-bench",
            user_id="user-bench",
            client=object(),
            settings=SimpleNamespace(),
            conversation_id="conv-bench",
            connected_integrations=connected,
        )
        durations.append((time.perf_counter() - t0) * 1000.0)
    durations.sort()
    return {
        "message": message,
        "n": n,
        "p50_ms": round(statistics.median(durations), 3),
        "p95_ms": round(durations[int(0.95 * len(durations)) - 1], 3),
        "max_ms": round(max(durations), 3),
    }


async def main() -> None:
    cases = [
        ("hello", None, None),
        ("what is OAuth?", None, None),
        ("2 + 2", None, None),
        ("show me GA4 traffic", ["google_analytics"], None),
        ("how is my website doing?", ["google_analytics", "google_search_console"], None),
        ("yes", None, {"offered_action": {"status": "awaiting_user_confirmation", "tools": ["connector_status"]}}),
    ]
    for message, connected, state in cases:
        row = await _bench(message, connected=connected, state=state, n=100)
        print(row)


if __name__ == "__main__":
    asyncio.run(main())
