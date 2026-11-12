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
from collections import defaultdict
from pathlib import Path

PATTERN = re.compile(
    r"router_stage_timing stage=(?P<stage>[a-z_]+) "
    r"surface=(?P<surface>[a-z_]+) outcome=(?P<outcome>ok|error) "
    r"duration_ms=(?P<ms>[0-9]+(?:\\.[0-9]+)?)"
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
    return {"measurement": "actual emitted stage timing log samples",
            "critical_path_caveat": "No per-request correlation IDs; stage sums and rankings cannot prove end-to-end critical path or concurrency benefit.",
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
