"""Read-only stage p50/p95 report from verified isolated ECO-002 router telemetry.

Uses the current canonical routing_stage_metrics.py logger, not the parallel
router_stage_timing.py implementation on an unmerged branch. Never infers
request-level latency or approves optimizations from stage-only observations.
"""
from __future__ import annotations

import argparse
import json
import math
import re
from collections import defaultdict
from pathlib import Path

PATTERN = re.compile(
    r"eco002_route_stage stage=(?P<stage>[a-z_]+) "
    r"outcome=(?P<outcome>ok|error) duration_ms=(?P<ms>[0-9.]+)"
)
STAGES = frozenset({
    "overview_policy", "dialogue_settings", "understanding", "classification",
    "query_cluster", "clarification", "context_assembly", "risk_evaluation",
    "model_selection", "enrichments", "response_dispatch", "guidance",
})


def percentile(values: list[float], quantile: float) -> float:
    if not values:
        raise ValueError("no observed samples")
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
    timings: dict[tuple[str, str], list[float]] = defaultdict(list)
    for line in lines:
        match = PATTERN.search(line)
        if not match:
            continue
        stage = match["stage"]
        if stage not in STAGES:
            raise ValueError("unknown router stage")
        value = float(match["ms"])
        if not math.isfinite(value) or value < 0:
            raise ValueError("invalid stage duration")
        timings[stage, match["outcome"]].append(value)
    if not timings:
        raise ValueError("no measured ECO-002 router stage timings")
    stage_records = {}
    for stage in sorted({s for s, _ in timings}):
        ok = timings.get((stage, "ok"), [])
        errors = timings.get((stage, "error"), [])
        if len(ok) < min_samples:
            raise ValueError(f"insufficient stage samples for {stage}: {len(ok)} < {min_samples}")
        stage_records[stage] = {
            "samples": len(ok), "errors": len(errors),
            "p50_ms": percentile(ok, .5), "p95_ms": percentile(ok, .95),
        }
    return {
        "provenance": provenance,
        "stage_summaries": stage_records,
        "eligible_for_optimization": False,
        "caveats": [
            "Histograms and logs are per stage, not correlated complete requests or end-to-end response times.",
            "Never sum overlapping spans as wall-clock latency.",
            "Missing conditional stages are unobserved, not zero duration.",
            "Actual provider outcome, authorization, rollback and release gates are independent.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("log", type=Path)
    parser.add_argument("--provenance", choices=("verified_nonproduction",), required=True)
    parser.add_argument("--min-samples", type=int, default=30)
    args = parser.parse_args()
    print(json.dumps(summarize(args.log.read_text().splitlines(),
                               provenance=args.provenance, min_samples=args.min_samples), indent=2))


if __name__ == "__main__":
    main()
