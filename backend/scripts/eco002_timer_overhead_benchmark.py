"""Deterministic CI microbenchmark for ECO-002 timing overhead.

This exercises the real timer implementation, NOT real router dependencies.
Results must never be described as representative end-to-end routing latency.
"""
import asyncio
import json
import logging
import os
import statistics
from time import perf_counter

from app.services.router_stage_timing import timed_router_stage

SAMPLES = 300
STAGES = ("overview_policy", "dialogue_settings", "understanding", "classification",
          "query_cluster", "context", "model_selection", "enrichments")


async def main():
    logging.disable(logging.CRITICAL)
    results = {}
    for enabled in (False, True):
        os.environ["GRAVITRE_ROUTER_STAGE_TIMING_ENABLED"] = "1" if enabled else "0"
        values = []
        for _ in range(SAMPLES):
            async def no_op():
                return None
            start = perf_counter()
            for stage in STAGES:
                await timed_router_stage(stage, "chat", no_op())
            values.append((perf_counter() - start) * 1000)
        sorted_values = sorted(values)
        results["enabled" if enabled else "disabled"] = {
            "count": len(values),
            "p50_ms": round(statistics.median(values), 5),
            "p95_ms": round(sorted_values[int(0.95 * (len(values)-1))], 5),
        }
    print(json.dumps({"measurement_type": "CI timer overhead only; synthetic no-op operations",
                      "environment": "GitHub Actions ubuntu-latest Python 3.11",
                      "stages_per_iteration": len(STAGES),
                      "results": results}, sort_keys=True))


if __name__ == "__main__":
    asyncio.run(main())
