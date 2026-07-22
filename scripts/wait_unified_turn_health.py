#!/usr/bin/env python3
"""Poll /health until tip prefix matches and LIVE flag is as expected."""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--health-url", default="https://api.gravitre.app/health")
    p.add_argument("--expect-sha-prefix", required=True)
    p.add_argument("--expect-live", default="true")
    p.add_argument("--timeout-s", type=int, default=900)
    p.add_argument(
        "--allow-missing-flag-keys",
        action="store_true",
        help="Pass when tip matches even if unified_turn_* health keys are absent",
    )
    args = p.parse_args()
    want_live = str(args.expect_live).lower() in {"1", "true", "yes"}
    prefix = args.expect_sha_prefix.strip()
    deadline = time.time() + args.timeout_s
    attempt = 0
    while time.time() < deadline:
        attempt += 1
        try:
            with urllib.request.urlopen(args.health_url, timeout=30) as resp:
                body = resp.read().decode("utf-8", errors="replace")
            health = json.loads(body)
        except Exception as exc:  # noqa: BLE001
            print(f"attempt={attempt} error={exc}")
            time.sleep(10)
            continue
        sha = str(health.get("git_sha") or "")
        live = health.get("unified_turn_live_enabled")
        shadow = health.get("unified_turn_shadow_enabled")
        print(
            f"attempt={attempt} sha={sha[:12]} live={live} shadow={shadow} ts={health.get('timestamp')}"
        )
        tip_ok = bool(prefix) and sha.startswith(prefix)
        if not tip_ok:
            time.sleep(10)
            continue
        if live is None:
            if args.allow_missing_flag_keys:
                print("health gate PASS (tip matched; flag keys not in schema yet)")
                return 0
            print("tip matched but flag keys absent; keep waiting for health schema tip")
            time.sleep(10)
            continue
        if want_live and live is True:
            print("health gate PASS (LIVE=true)")
            return 0
        if not want_live and live is False:
            print("health gate PASS (LIVE=false)")
            return 0
        # Tip advanced but LIVE still false — keep waiting for process with new env.
        time.sleep(10)
    print("health gate TIMEOUT", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
