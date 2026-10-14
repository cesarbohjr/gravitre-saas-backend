#!/usr/bin/env python3
"""Compare production backend SHA to an expected main commit (read-only)."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_OUT = Path(__file__).resolve().parent.parent / "docs/delivery/production-deploy-alignment.json"


def fetch_health(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=20) as resp:
        return json.loads(resp.read().decode())


def sha_match(got: str, expected: str) -> bool:
    if not got or not expected:
        return False
    return got.startswith(expected) or expected.startswith(got)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--api-health", default="https://api.gravitre.app/health")
    p.add_argument("--expect-sha", default="", help="Expected git SHA (e.g. from Vercel or main)")
    p.add_argument("--note-web-sha", default="", help="Operator-reported Vercel production SHA")
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = p.parse_args()

    health = fetch_health(args.api_health)
    got = str(health.get("git_sha") or "")
    exp = args.expect_sha.strip()
    web = args.note_web_sha.strip()

    row = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "api_health_url": args.api_health,
        "backend_git_sha": got,
        "expect_sha": exp or None,
        "backend_matches_expect": sha_match(got, exp) if exp else None,
        "operator_web_sha": web or None,
        "web_backend_aligned": sha_match(got, web) if web else None,
        "health_timestamp": health.get("timestamp"),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(row, indent=2) + "\n")
    print(json.dumps(row, indent=2))
    if exp and not sha_match(got, exp):
        return 1
    if web and not sha_match(got, web):
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
