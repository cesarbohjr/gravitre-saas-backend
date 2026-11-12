"""Summarize ECO-003 real context assembly timing logs.

Use only logs collected from an explicitly authorized nonproduction deployment.
No fixture data is generated. Stage times may overlap and must not be summed
to infer request wall time. Inputs must contain no tenant or request payloads.
"""
from __future__ import annotations
import argparse
import json
import math
import re
from collections import defaultdict
from pathlib import Path

PATTERN = re.compile(
    r"eco003_context_stage_timing retrieval_ms=(?P<retrieval>[0-9.]+) "
    r"company_ms=(?P<company>[0-9.]+) research_ms=(?P<research>[0-9.]+) "
    r"total_ms=(?P<total>[0-9.]+) retrieval_ok=(?P<ok>True|False) "
    r"research_requested=(?P<requested>True|False)"
)


def percentile(values, p):
    ordered = sorted(values)
    index = (len(ordered) - 1) * p
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    return round(ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower), 3)


def summarize(lines, *, provenance, min_samples=1):
    if not isinstance(min_samples, int) or isinstance(min_samples, bool) or min_samples < 1:
        raise ValueError("min_samples must be a positive integer")
    if provenance != "verified_nonproduction":
        raise ValueError("verified_nonproduction provenance required")
    groups = defaultdict(lambda: defaultdict(list))
    for line in lines:
        match = PATTERN.search(line)
        if not match:
            continue
        vals = {k: float(match[k]) for k in ("retrieval", "company", "research", "total")}
        if any(not math.isfinite(v) or v < 0 for v in vals.values()):
            raise ValueError("invalid duration")
        scenario = "research" if match["requested"] == "True" else "no_research"
        groups[scenario]["total"].append(vals["total"])
        groups[scenario]["retrieval"].append(vals["retrieval"])
        groups[scenario]["company"].append(vals["company"])
        if scenario == "research":
            groups[scenario]["research"].append(vals["research"])
        groups[scenario]["retrieval_failures"].append(match["ok"] == "False")
    if not groups:
        raise ValueError("no emitted ECO-003 timing observations")
    for scenario, rows in groups.items():
        if len(rows["total"]) < min_samples:
            raise ValueError(f"insufficient observations for {scenario}: {len(rows['total'])} < {min_samples}")
    return {
        "provenance": provenance,
        "caveat": "Timing telemetry is not independent proof of provider identity, tenant isolation, or real external I/O. Stages may overlap; do not sum stage times as wall-clock.",
        "scenarios": {
            name: {
                "samples": len(rows["total"]),
                "retrieval_failures": sum(rows["retrieval_failures"]),
                "stages": {
                    stage: {"count": len(values), "p50_ms": percentile(values, .5),
                            "p95_ms": percentile(values, .95)}
                    for stage, values in rows.items() if stage != "retrieval_failures"
                },
            }
            for name, rows in sorted(groups.items())
        },
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("log", type=Path)
    parser.add_argument("--provenance", choices=["verified_nonproduction"], required=True)
    parser.add_argument("--min-samples", type=int, default=30,
                        help="Minimum observations per present scenario (default: 30)")
    args = parser.parse_args()
    print(json.dumps(summarize(args.log.read_text().splitlines(), provenance=args.provenance, min_samples=args.min_samples), indent=2))


if __name__ == "__main__":
    main()
