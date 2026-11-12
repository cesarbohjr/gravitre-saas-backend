"""ECO-002 CI-only real PostgreSQL/Redis I/O latency probe.

Measures actual local service-container round trips, never mocked sleeps.
Not an end-to-end IntelligenceRouter or live LLM/provider benchmark.
Uses disposable data and reports only aggregate timings.
"""
from __future__ import annotations

import asyncio
import json
import os
import statistics
from time import perf_counter


def percentile(values, q):
    values = sorted(values)
    if not values:
        raise ValueError("no samples")
    index = (len(values) - 1) * q
    lower = int(index)
    upper = min(lower + 1, len(values) - 1)
    return round(values[lower] + (values[upper] - values[lower]) * (index - lower), 3)


async def measure(name, operation, count):
    values = []
    for _ in range(count):
        start = perf_counter()
        await operation()
        values.append((perf_counter() - start) * 1000)
    return {"dependency": name, "samples": count,
            "p50_ms": percentile(values, 0.5), "p95_ms": percentile(values, 0.95)}


async def main():
    import asyncpg
    import redis.asyncio as redis
    count = int(os.getenv("ECO002_SAMPLES", "100"))
    if not 20 <= count <= 1000:
        raise ValueError("sample count must be between 20 and 1000")
    pg = await asyncpg.connect(os.environ["ECO002_POSTGRES_DSN"])
    client = redis.from_url(os.environ["ECO002_REDIS_URL"], decode_responses=True)
    try:
        async def postgres_roundtrip():
            assert await pg.fetchval("SELECT 1") == 1
        async def redis_roundtrip():
            assert await client.ping()
        await postgres_roundtrip()
        await redis_roundtrip()
        results = [
            await measure("postgresql_select_1", postgres_roundtrip, count),
            await measure("redis_ping", redis_roundtrip, count),
        ]
        print(json.dumps({
            "classification": "real CI service-container I/O, not deployed router or LLM/provider latency",
            "samples_per_dependency": count, "results": results,
            "missing_measurements": ["router_end_to_end", "model", "external_provider"],
        }, sort_keys=True))
    finally:
        await client.aclose()
        await pg.close()


if __name__ == "__main__":
    asyncio.run(main())
