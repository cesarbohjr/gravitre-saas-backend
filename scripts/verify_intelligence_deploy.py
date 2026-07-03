#!/usr/bin/env python3
"""Smoke-check intelligence endpoints after deploy."""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

BASE = os.environ.get("GRAVITRE_API_BASE", "https://api.gravitre.app").rstrip("/")
CHECKS = (
    "/health",
)


def fetch(path: str) -> tuple[int, str]:
    req = urllib.request.Request(f"{BASE}{path}", headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.status, resp.read(500).decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(200).decode("utf-8", errors="replace")


def main() -> int:
    print(f"Verifying intelligence deploy against {BASE}")
    failed = 0
    for path in CHECKS:
        status, body = fetch(path)
        ok = 200 <= status < 300
        print(f"{'OK' if ok else 'FAIL'} {path} -> {status}")
        if not ok:
            failed += 1
            print(body[:200])
    health_ok, health_body = fetch("/health")
    if health_ok == 200:
        try:
            payload = json.loads(health_body)
            print(f"health.ai_disabled={payload.get('ai_disabled')}")
        except json.JSONDecodeError:
            pass
    print("Admin intelligence routes require auth — verify in app after deploy:")
    print("  GET /api/admin/intelligence/learning/live-dashboard")
    print("  GET /api/admin/intelligence/learning/bandit-status")
    print("  GET /api/admin/intelligence/predictive-ops/domain/support")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
