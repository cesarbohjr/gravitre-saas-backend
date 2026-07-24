#!/usr/bin/env python3
"""Poll prod /health until git_sha matches or timeout."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import httpx

BASE = os.environ.get("LIVE_API_BASE", "https://api.gravitre.app").rstrip("/")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sha-prefix", default="", help="Wait until git_sha starts with this")
    parser.add_argument("--timeout-sec", type=int, default=900)
    parser.add_argument("--interval-sec", type=float, default=15)
    args = parser.parse_args()

    deadline = time.time() + args.timeout_sec
    last: dict | None = None
    while time.time() < deadline:
        try:
            last = httpx.get(f"{BASE}/health", timeout=30).json()
        except Exception as exc:  # noqa: BLE001
            print(json.dumps({"error": str(exc)}))
            time.sleep(args.interval_sec)
            continue
        sha = str(last.get("git_sha") or "")
        embed_min = last.get("unified_turn_embed_min_catalog_tools")
        print(
            json.dumps(
                {
                    "git_sha": sha,
                    "unified_turn_embed_min_catalog_tools": embed_min,
                    "unified_turn_embedding_tool_retrieval": last.get(
                        "unified_turn_embedding_tool_retrieval"
                    ),
                }
            )
        )
        if args.sha_prefix and sha.startswith(args.sha_prefix):
            return 0
        if not args.sha_prefix:
            return 0
        time.sleep(args.interval_sec)
    print(json.dumps({"timeout": True, "last": last}, indent=2))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
