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
    modes=parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--template", action="store_true")
    modes.add_argument("--product-template", action="store_true",help="Unscored ChatGPT text/voice/execution protocol")
    modes.add_argument("--product-score",type=Path,help="Private observed-session rating manifest")
    parser.add_argument("--identity-file",type=Path,help="Separate A/B identity file withheld from raters")
    parser.add_argument("--evidence-root",type=Path,help="Private capture directory; recordings never enter the report")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()
    default_name="chatgpt-product-benchmark-report.json" if args.product_score else "chatgpt-product-benchmark-template.json" if args.product_template else "conversation-parity-benchmark-template.json"
    out = ROOT / (args.out or "docs/delivery/"+default_name)
    out.parent.mkdir(parents=True, exist_ok=True)
    if args.product_template:
        from app.services.conversation_benchmark_evidence import template as product_template
        payload=product_template()
    elif args.product_score:
        if not args.identity_file or not args.evidence_root:parser.error("--product-score requires --identity-file and --evidence-root")
        from app.services.conversation_benchmark_evidence import evaluate
        try:
            if args.product_score.stat().st_size>4194304 or args.identity_file.stat().st_size>4096:raise ValueError('manifest_bounds_invalid')
            payload=evaluate(json.loads(args.product_score.read_text()),identity=json.loads(args.identity_file.read_text()),evidence_root=args.evidence_root)
        except (ValueError,OSError,TypeError,KeyError):
            payload={'schema_version':1,'status':'NOT_CERTIFIED','reason':'evidence_contract_incomplete_or_invalid','whole_product_equivalence_claim':False}
    else:
        payload=template()
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"wrote {out}; status={payload.get('status','UNSCORED_TEMPLATE')}")
    return 1 if args.product_score and payload.get('status')!='PASS_MEASURED_SCOPE' else 0


if __name__ == "__main__":
    raise SystemExit(main())
