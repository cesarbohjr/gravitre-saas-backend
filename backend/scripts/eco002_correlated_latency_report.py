"""ECO-002 correlate request wall-clock and instrumented stage logs.

Does not infer model/provider/database latency from fixture measurements.
A complete live acceptance requires actual model_provider observations and
explicitly identified nonproduction provider provenance.
"""
from __future__ import annotations
import argparse
import json
import math
import re
from collections import defaultdict
from pathlib import Path
from eco002_stage_latency_report import percentile

WALL = re.compile(r"eco002_request_wall scenario=(?P<scenario>[a-z_]+) sample=(?P<sample>[A-Za-z0-9_-]{1,48}) duration_ms=(?P<ms>[0-9.]+)")
STAGE = re.compile(r"router_stage_timing stage=(?P<stage>[a-z_]+) surface=(?P<surface>[a-z_]+) outcome=(?P<outcome>ok|error) duration_ms=(?P<ms>[0-9.]+) sample=(?P<sample>[A-Za-z0-9_-]{1,48})")


def summarize(lines, *, provenance="fixture"):
    walls = {}
    stages = defaultdict(list)
    for line in lines:
        m = WALL.search(line)
        if m:
            key = m["sample"]
            if key in walls:
                raise ValueError("duplicate request sample")
            walls[key] = (m["scenario"], float(m["ms"]))
        m = STAGE.search(line)
        if m:
            stages[m["sample"]].append((m["stage"], m["outcome"], float(m["ms"])))
    by_scenario = defaultdict(list)
    by_boundary = defaultdict(list)
    incomplete = []
    failed_requests = set()
    invalid_durations = []
    for sample, (scenario, wall_ms) in walls.items():
        if not math.isfinite(wall_ms) or wall_ms < 0:
            invalid_durations.append(sample)
        by_scenario[scenario].append(wall_ms)
        observed = stages.get(sample, [])
        if not observed:
            incomplete.append(sample)
        if any(outcome == "error" for _, outcome, _ in observed):
            failed_requests.add(sample)
        for stage, outcome, duration in observed:
            if not math.isfinite(duration) or duration < 0:
                invalid_durations.append(sample)
                continue
            if outcome == "ok":
                by_boundary[(scenario, stage)].append(duration)
    def stats(values):
        return {"count": len(values), "p50_ms": round(percentile(values, .5), 3),
                "p95_ms": round(percentile(values, .95), 3)}
    orphan_samples = sorted(set(stages) - set(walls))
    model_seen = any(stage == "model_provider" for (_, stage) in by_boundary)
    provider_seen = any(stage == "execution" for (_, stage) in by_boundary)
    return {
        "provenance": provenance,
        "request_count": len(walls),
        "scenarios": {k: stats(v) for k, v in sorted(by_scenario.items())},
        "boundaries": {f"{scenario}/{stage}": stats(v) for (scenario, stage), v in sorted(by_boundary.items())},
        "unmatched_request_count": len(incomplete),
        "orphan_stage_sample_count": len(orphan_samples),
        "failed_request_count": len(failed_requests),
        "invalid_duration_count": len(invalid_durations),
        "correlation_complete": bool(walls) and not (incomplete or orphan_samples or invalid_durations),
        "model_provider_observed": model_seen,
        "governed_execution_observed": provider_seen,
        "actual_external_provider_observed": False,
        "eligible_for_optimization": False,  # External provider I/O and authorization evidence not yet established.
        "caveat": "Stage boundaries may overlap; never subtract summed stage times from wall clock. Execution stage does not establish external provider I/O. Fixture traces are not live latency evidence.",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("log", type=Path)
    parser.add_argument("--provenance", choices=("fixture", "verified_nonproduction"), default="fixture")
    parser.add_argument("--require-live", action="store_true")
    args = parser.parse_args()
    result = summarize(args.log.read_text().splitlines(), provenance=args.provenance)
    print(json.dumps(result, indent=2, sort_keys=True))
    if not result["correlation_complete"]:
        raise SystemExit("Missing, orphaned, or invalid router timing traces")
    if args.require_live and not result["eligible_for_optimization"]:
        raise SystemExit("Missing verified nonproduction model/provider traces; no optimization authorized")


if __name__ == "__main__":
    main()
