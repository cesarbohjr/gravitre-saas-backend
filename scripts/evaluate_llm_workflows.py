#!/usr/bin/env python3
"""Validate or explicitly run bounded synthetic planning evaluations.

Default is manifest-only (no providers/database). --run requires a dedicated
test org and uses the existing guarded ModelRouter and model_calls writer.
No tools execute and no live routing changes. Output omits prompts/responses.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.config import get_settings  # noqa: E402
from app.services.llm_catalog import get_llm_model  # noqa: E402
from app.services.llm_workflow_evaluation import GOLDEN_CASES, evaluate_models  # noqa: E402
from app.services.model_router import ModelRouter  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", nargs="+", required=True)
    parser.add_argument("--org-id", type=UUID, help="Dedicated evaluation/test organization")
    parser.add_argument("--repetitions", type=int, default=1)
    parser.add_argument("--run", action="store_true", help="Make paid model requests and persist model_calls")
    args = parser.parse_args()
    calls = len(args.models) * len(GOLDEN_CASES) * args.repetitions
    if (not 1 <= len(args.models) <= 5 or len(set(args.models)) != len(args.models)
            or not 1 <= args.repetitions <= 10 or calls > 200):
        parser.error("Use 1..5 distinct models, 1..10 repetitions and at most 200 calls")
    if any(get_llm_model(model) is None or get_llm_model(model).deprecated for model in args.models):
        parser.error("Every model must be an active catalog id")
    if not args.run:
        print(json.dumps({"dry_run": True, "planned_calls": calls, "models": args.models,
                          "cases": [case.id for case in GOLDEN_CASES], "max_output_tokens_per_call": 256}))
        return 0
    if args.org_id is None:
        parser.error("--run requires --org-id for a dedicated test organization")
    report = asyncio.run(evaluate_models(
        ModelRouter(get_settings()), org_id=str(args.org_id), models=args.models,
        repetitions=args.repetitions,
    ))
    report["generated_at"] = datetime.now(timezone.utc).isoformat()
    print(json.dumps(report, sort_keys=True, allow_nan=False))
    return 0 if all(row["passed"] for row in report["results"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
