#!/usr/bin/env python3
"""Create/score provider-neutral conversation parity runs.

The runner intentionally separates scenario definition from provider adapters.
Use --template to emit a blind scoring sheet. Provider transcripts can then be
scored without revealing which system produced them.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.conversation_parity_benchmark import SCENARIOS, validate_registry
from app.services.conversation_parity_scoring import DIMENSIONS


def template() -> dict:
    validate_registry()
    return {
        "schema_version": 1,
        "blind": True,
        "dimensions": list(DIMENSIONS),
        "scale": "1-5; invariant pass/fail scored separately",
        "scenarios": [
            {
                "id": s.id,
                "lane": s.lane,
                "turns": list(s.turns),
                "invariants": list(s.invariants),
                "providers": {
                    "A": {"transcript": [], "scores": {}, "invariants": {}},
                    "B": {"transcript": [], "scores": {}, "invariants": {}},
                    "C": {"transcript": [], "scores": {}, "invariants": {}},
                },
            }
            for s in SCENARIOS
        ],
        "rules": [
            "Run the same scenario and starting state for every provider.",
            "Do not expose provider identity to the human/judge while scoring.",
            "Do not use exact-answer matching for open-ended conversational quality.",
            "Record tool calls, approvals, failures and latency as evidence, not prose claims.",
            "Voice latency must use speech-end to first audible meaningful audio on the same device/network.",
            "Unknown or unmeasured evidence is UNPROVEN, never PASS.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--template", action="store_true")
    parser.add_argument("--out", default="docs/delivery/conversation-parity-benchmark-template.json")
    args = parser.parse_args()
    if not args.template:
        parser.error("currently supported mode: --template")
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = template()
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"wrote {out} ({len(payload['scenarios'])} scenarios)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
