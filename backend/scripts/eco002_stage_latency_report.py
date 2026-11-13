"""Summarize real router_stage_timing log samples without inventing missing data.

Usage: python backend/scripts/eco002_stage_latency_report.py logs.txt
Input must contain actual instrumented router log records. This tool does not
claim that synthetic or fixture requests represent production traffic.
"""
from __future__ import annotations

import argparse
import json
import math
import re
from collections import defaultdict, Counter
from pathlib import Path

SAMPLE_PATTERN = re.compile(r"(?:^|\s)sample=(?P<sample>[A-Za-z0-9_-]{1,48})(?:\s|$)")
PATTERN = re.compile(
    r"router_stage_timing stage=(?P<stage>[a-z_]+) "
    r"surface=(?P<surface>[a-z_]+) outcome=(?P<outcome>ok|error) "
    r"duration_ms=(?P<ms>[0-9]+(?:\.[0-9]+)?)"
)


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = (len(ordered) - 1) * fraction
    lo = math.floor(index)
    hi = math.ceil(index)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (index - lo)


def summarize(lines):
    samples = defaultdict(list)
    failures = defaultdict(int)
    traces = defaultdict(list)
    trace_surfaces = {}
    for line in lines:
        match = PATTERN.search(line)
        if not match:
            continue
        key = (match["surface"], match["stage"])
        duration = float(match["ms"])
        if not math.isfinite(duration):
            continue
        if match["outcome"] == "ok":
            samples[key].append(duration)
            sample_match = SAMPLE_PATTERN.search(line)
            if sample_match:
                sample_id = sample_match["sample"]
                traces[sample_id].append((match["stage"], duration))
                trace_surfaces.setdefault(sample_id, match["surface"])
        else:
            failures[key] += 1
    result = []
    for key, values in samples.items():
        result.append({
            "surface": key[0], "stage": key[1], "count": len(values),
            "p50_ms": round(percentile(values, .5), 3),
            "p95_ms": round(percentile(values, .95), 3),
            "total_observed_ms": round(sum(values), 3),
            "errors": failures[key],
        })
    result.sort(key=lambda x: (-x["p95_ms"], -x["total_observed_ms"]))
    trace_rows = []
    contributions = defaultdict(list)
    for sample_id, stages in sorted(traces.items()):
        total = sum(duration for _, duration in stages)
        if total <= 0:
            continue
        trace_rows.append({"sample": sample_id, "surface": trace_surfaces[sample_id],
                           "observed_stage_sum_ms": round(total, 3),
                           "stage_count": len(stages)})
        for stage, duration in stages:
            contributions[(trace_surfaces[sample_id], stage)].append(duration / total * 100)
    ranked_contributions = sorted(({
        "surface": surface, "stage": stage, "sample_count": len(pcts),
        "mean_observed_stage_share_pct": round(sum(pcts) / len(pcts), 2)
    } for (surface, stage), pcts in contributions.items()),
        key=lambda x: -x["mean_observed_stage_share_pct"])
    return {"measurement": "actual emitted stage timing log samples",
            "critical_path_caveat": "Correlated sequential stage sums exclude uninstrumented work and cannot prove end-to-end critical path or concurrency benefit. Overlapping stages must not be summed as wall-clock time.",
            "correlated_trace_count": len(trace_rows),
            "correlated_traces": trace_rows,
            "ranked_observed_stage_share": ranked_contributions,
            "sample_count": sum(len(v) for v in samples.values()),
            "ranked_by_stage_p95": result}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("log_file", type=Path)
    args = parser.parse_args()
    result = summarize(args.log_file.read_text().splitlines())
    print(json.dumps(result, indent=2))
    if result["sample_count"] == 0:
        raise SystemExit("No real stage timing samples found; no latency ranking available")


if __name__ == "__main__":
    main()
