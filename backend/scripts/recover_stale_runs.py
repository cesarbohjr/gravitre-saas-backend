#!/usr/bin/env python3
"""List (default) or recover workflow runs left in flight by a dead worker.

Dry run by default: prints what would change. --apply writes the transitions
(failed / flagged_for_review / verification_inconclusive). Never re-runs work.
Needs SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.stale_run_recovery import recover_stale_runs
from supabase import create_client


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--threshold-minutes", type=int, default=60)
    parser.add_argument("--verifying-threshold-minutes", type=int, default=1440)
    args = parser.parse_args()
    url, key = os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        print("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required", file=sys.stderr)
        return 1
    out = recover_stale_runs(
        create_client(url, key),
        threshold_minutes=args.threshold_minutes,
        verifying_threshold_minutes=args.verifying_threshold_minutes,
        dry_run=not args.apply,
    )
    print(json.dumps(out, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
