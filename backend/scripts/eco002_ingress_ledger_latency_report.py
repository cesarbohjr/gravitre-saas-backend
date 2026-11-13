"""ECO-002 actual joined Chat/Agent -> independently queried SQL timing evidence.

Input: captured stdout from existing ECO-001 joined integration tests.
Provenance: isolated receiver, disposable PostgreSQL, controlled external services.
One first-write measurement per surface is diagnostic, NOT a population p95.
"""
from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path

LINE = re.compile(
    r"eco002_ingress_ledger surface=(chat|agent) outcome=(completed|replay) "
    r"provenance=isolated_receiver samples=1 ingress_ms=([0-9]+(?:\.[0-9]+)?)"
    r"(?: verified_ms=([0-9]+(?:\.[0-9]+)?))?"
)


def summarize(lines: list[str]) -> dict:
    observed: dict[tuple[str, str], dict] = {}
    for line in lines:
        match = LINE.search(line)
        if not match:
            continue
        surface, outcome, ingress, verified = match.groups()
        key = (surface, outcome)
        if key in observed:
            raise ValueError(f"duplicate timing for {surface}/{outcome}")
        duration = float(ingress)
        verification = float(verified) if verified is not None else None
        if not math.isfinite(duration) or duration < 0:
            raise ValueError("invalid ingress duration")
        if outcome == "completed" and (verification is None or verification < duration):
            raise ValueError("completed timing lacks independent SQL verification")
        if outcome == "replay" and verification is not None:
            raise ValueError("replay must not claim new terminal verification")
        observed[key] = {"ingress_ms": duration, "verified_ms": verification}
    required = {(surface, outcome) for surface in ("chat", "agent") for outcome in ("completed", "replay")}
    missing = sorted(f"{surface}/{outcome}" for surface, outcome in required - set(observed))
    return {
        "classification": "diagnostic_single_sample_not_p50_p95",
        "provenance": "isolated_receiver_disposable_postgresql",
        "eligible_for_optimization": False,
        "sample_count_per_surface_outcome": 1,
        "observations": {
            f"{surface}/{outcome}": value
            for (surface, outcome), value in sorted(observed.items())
        },
        "missing": missing,
        "complete": not missing,
        "caveat": (
            "Mounted authenticated Chat and actual Agent worker to independently "
            "queried SQL terminal state. Controlled authorization and provider "
            "fixtures, no real LLM, no production traffic, no context-size or TTFA "
            "measurement; one sample cannot establish p50/p95."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("log", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = summarize(args.log.read_text().splitlines())
    result = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        args.output.write_text(result + "\n")
    print(result)
    if not report["complete"]:
        raise SystemExit("Missing Chat/Agent ingress-to-ledger evidence")


if __name__ == "__main__":
    main()
