"""Run the observation extractor over the labelled set and check the release gate.

Calls the real fast-tier model once per case (needs provider keys), so run it
before switching ENTITY_OBSERVATIONS_ENABLED on, and again for every new
EXTRACTOR_VERSION:

    python scripts/eval_observations.py --org <org uuid> --out /tmp/obs-eval.json

Exits 1 when the gate in app/services/observation_eval.py is not met.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.entity_observations import EXTRACTOR_VERSION, extract_observations
from app.services.observation_eval import evaluate, load_cases, passes_gate

DEFAULT_CASES = Path(__file__).resolve().parent.parent / "tests" / "eval" / "fixtures" / "observations_v1.jsonl"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--cases", default=str(DEFAULT_CASES))
    parser.add_argument("--org", required=True, help="org id the model calls are billed to")
    parser.add_argument("--out")
    args = parser.parse_args(argv)

    async def extractor(text: str):
        return await extract_observations(text, org_id=args.org)

    report = asyncio.run(evaluate(load_cases(args.cases), extractor))
    ok, failures = passes_gate(report)
    report.update({"extractor_version": EXTRACTOR_VERSION, "gate_passed": ok, "gate_failures": failures})
    text = json.dumps(report, indent=2)
    if args.out:
        Path(args.out).write_text(text + "\n")
    print(text)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
