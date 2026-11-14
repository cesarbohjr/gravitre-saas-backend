"""Summarize real ECO-003 stage timings from a verified isolated QA log.

Read-only: does not generate samples, infer request identity or contact providers.
Nested stage times must not be added to derive total end-to-end latency.
"""
from __future__ import annotations

import argparse
import json
import math
import re
from collections import defaultdict
from pathlib import Path

PATTERN = re.compile(
    r"eco003_context_stage stage=(?P<stage>[a-z_]+) "
    r"outcome=(?P<outcome>ok|error) duration_ms=(?P<ms>[0-9.]+)"
)
STAGES = frozenset({
    "unified_retrieval", "org_context", "agent_memory", "rag_retrieval",
    "company_intelligence", "external_research",
})


def percentile(values: list[float], quantile: float) -> float:
    if not values:
        raise ValueError("no measured samples")
    ordered = sorted(values)
    index = (len(ordered) - 1) * quantile
    low = int(index)
    high = min(low + 1, len(ordered) - 1)
    return round(ordered[low] + (ordered[high] - ordered[low]) * (index - low), 3)


def summarize(lines: list[str], *, provenance: str, min_samples: int = 30) -> dict:
    if provenance != "verified_nonproduction":
        raise ValueError("verified_nonproduction provenance required")
    if type(min_samples) is not int or min_samples < 1:
        raise ValueError("min_samples must be a positive integer")
    durations: dict[tuple[str, str], list[float]] = defaultdict(list)
    for line in lines:
        hit = PATTERN.search(line)
        if not hit:
            continue
        stage, outcome = hit["stage"], hit["outcome"]
        if stage not in STAGES:
            raise ValueError("unknown context stage")
        duration = float(hit["ms"])
        if not math.isfinite(duration) or duration < 0:
            raise ValueError("invalid timing observation")
        durations[stage, outcome].append(duration)
    if not durations:
        raise ValueError("no emitted ECO-003 timing observations")
    observed_stages = sorted({stage for stage, _ in durations})
    records = {}
    for stage in observed_stages:
        good = durations.get((stage, "ok"), [])
        errors = durations.get((stage, "error"), [])
        if len(good) < min_samples:
            raise ValueError(f"insufficient successful observations for {stage}: {len(good)} < {min_samples}")
        records[stage] = {
            "samples": len(good), "errors": len(errors),
            "p50_ms": percentile(good, 0.5), "p95_ms": percentile(good, 0.95),
        }
    return {
        "provenance": provenance,
        "stage_summaries": records,
        "caveats": [
            "Only stages present in logs are summarized; missing conditional stages are not zero latency.",
            "Stage observations are not correlated to requests; do not sum nested spans or infer end-to-end latency.",
            "Source logs are not independent proof of user/tenant authorization or external provider origin.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("log", type=Path)
    parser.add_argument("--provenance", choices=["verified_nonproduction"], required=True)
    parser.add_argument("--min-samples", type=int, default=30)
    args = parser.parse_args()
    print(json.dumps(summarize(args.log.read_text().splitlines(),
                               provenance=args.provenance, min_samples=args.min_samples), indent=2))


if __name__ == "__main__":
    main()
