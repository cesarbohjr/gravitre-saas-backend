"""Read-only ECO-003 percentile report from the canonical context stage logs.

The source is the *existing* context_stage_metrics.measure observer, not a
second context timer. Require real, authorized nonproduction observations:
test fixtures and empty files cannot certify performance improvements.
No request body, tenant identifier or source document is read or emitted.
"""
from __future__ import annotations

import argparse
import json
import math
import re
from collections import defaultdict
from pathlib import Path

# Must match app.services.context_stage_metrics exactly.
STAGES = frozenset({
    "unified_retrieval", "org_context", "agent_memory", "rag_retrieval",
    "company_intelligence", "external_research", "context_assembly_total",
})
LINE = re.compile(
    r"\beco003_context_stage stage=(?P<stage>[a-z_]+)"
    r" outcome=(?P<outcome>ok|error)"
    r" duration_ms=(?P<duration>[0-9]+(?:\.[0-9]+)?)\b"
)


def _quantile(samples: list[float], percentile: float) -> float:
    ordered = sorted(samples)
    index = (len(ordered) - 1) * percentile
    lo = int(index)
    hi = min(lo + 1, len(ordered) - 1)
    return round(ordered[lo] + (ordered[hi] - ordered[lo]) * (index - lo), 3)


def summarize(lines, *, provenance: str, min_samples: int = 30) -> dict:
    if provenance != "verified_nonproduction":
        raise ValueError("verified_nonproduction provenance required")
    if type(min_samples) is not int or min_samples < 30:
        raise ValueError("min_samples must be at least 30 per reported stage")
    observations = defaultdict(lambda: {"ok": [], "error": []})
    for line in lines:
        match = LINE.search(line)
        if not match:
            continue
        stage, outcome = match.group("stage"), match.group("outcome")
        if stage not in STAGES:
            raise ValueError("unknown static context stage")
        ms = float(match.group("duration"))
        if not math.isfinite(ms) or ms < 0:
            raise ValueError("invalid duration")
        observations[stage][outcome].append(ms)
    if not observations:
        raise ValueError("no canonical ECO-003 timing observations")
    result = {}
    for stage, values in sorted(observations.items()):
        ok = values["ok"]
        if len(ok) < min_samples:
            raise ValueError(f"insufficient successful observations for {stage}: {len(ok)} < {min_samples}")
        result[stage] = {
            "successful_samples": len(ok),
            "failed_samples": len(values["error"]),
            "p50_ms": _quantile(ok, 0.50),
            "p95_ms": _quantile(ok, 0.95),
        }
    return {
        "provenance": provenance,
        "status": "measured_nonproduction_only_not_qa_certified",
        "stage_statistics": result,
        "caveat": (
            "The observer is opt-in. A stage can contain nested stages; "
            "do not sum stage latencies. Request, tenant, user and document "
            "data are not exported. These measurements alone do not prove "
            "authorization, provider delivery, or end-to-end latency gains."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("log", type=Path, help="Authorized nonproduction log export")
    parser.add_argument("--provenance", choices=["verified_nonproduction"], required=True)
    parser.add_argument("--min-samples", type=int, default=30)
    args = parser.parse_args()
    print(json.dumps(summarize(
        args.log.read_text(encoding="utf-8").splitlines(),
        provenance=args.provenance,
        min_samples=args.min_samples,
    ), indent=2))


if __name__ == "__main__":
    main()
