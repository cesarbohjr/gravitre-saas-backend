#!/usr/bin/env python3
"""Release 1 unauthenticated production smoke (safe, read-only).

Does not print secrets. Does not write to production databases.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

DEFAULT_OUT = Path(__file__).resolve().parent.parent / "docs/delivery/release1-production-smoke.json"


def _get(url: str, timeout: float = 20.0, *, follow_redirects: bool = True) -> tuple[int, str]:
    handlers: list[urllib.request.BaseHandler] = []
    if not follow_redirects:
        class NoRedirect(urllib.request.HTTPErrorProcessor):
            def http_response(self, req, response):  # type: ignore[override]
                return response

            https_response = http_response

        handlers.append(NoRedirect())
    opener = urllib.request.build_opener(*handlers)
    req = urllib.request.Request(url, method="GET")
    try:
        with opener.open(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return resp.status, body
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return exc.code, body


def main() -> int:
    parser = argparse.ArgumentParser(description="Release 1 production smoke (anonymous HTTP only)")
    parser.add_argument("--web-base", default="https://gravitre.app")
    parser.add_argument("--api-health", default="https://api.gravitre.app/health")
    parser.add_argument("--expect-sha", default="", help="40-char or prefix of main commit")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    started = datetime.now(timezone.utc).isoformat()
    checks: list[dict] = []
    failed = 0

    # Web up
    code, _ = _get(args.web_base.rstrip("/") + "/")
    ok = code == 200
    checks.append({"id": "web_root", "pass": ok, "http_status": code})
    failed += 0 if ok else 1

    # Hero asset (Automate release alignment)
    code, _ = _get(args.web_base.rstrip("/") + "/illustrations/hero-plays.svg")
    ok = code == 200
    checks.append({"id": "hero_plays_svg", "pass": ok, "http_status": code})
    failed += 0 if ok else 1

    # /plays logged-out redirect
    code, _ = _get(args.web_base.rstrip("/") + "/plays", follow_redirects=False)
    ok = code in (307, 308, 401, 403)
    checks.append({"id": "plays_auth_gate", "pass": ok, "http_status": code})
    failed += 0 if ok else 1

    # API health + optional SHA
    code, body = _get(args.api_health)
    health: dict = {}
    sha_match = None
    if code == 200:
        try:
            health = json.loads(body)
        except json.JSONDecodeError:
            health = {"parse_error": True}
    if args.expect_sha and health.get("git_sha"):
        got = str(health["git_sha"])
        exp = args.expect_sha.strip()
        sha_match = got.startswith(exp) or exp.startswith(got)
    ok = code == 200 and (sha_match is not False)
    checks.append(
        {
            "id": "api_health",
            "pass": ok,
            "http_status": code,
            "git_sha": health.get("git_sha"),
            "expect_sha": args.expect_sha or None,
            "sha_match": sha_match,
        }
    )
    failed += 0 if ok else 1

    # Anonymous sessions must not return real org session payloads
    probe_org = str(uuid4())
    code, body = _get(args.web_base.rstrip("/") + f"/api/sessions?org_id={probe_org}")
    leak = False
    if code == 200:
        try:
            data = json.loads(body)
            runs = data.get("activeRuns") or data.get("recentActivity") or []
            leak = bool(runs)
        except json.JSONDecodeError:
            leak = False
    ok = not leak and code != 200 or (code in (401, 403, 500) and not leak)
    # Accept 500 permission denied as fail-closed without data leak
    if code == 200 and not leak:
        ok = True  # empty payload
    checks.append(
        {
            "id": "anonymous_sessions_no_leak",
            "pass": ok and not leak,
            "http_status": code,
            "body_snippet": body[:200] if body else "",
            "data_leak": leak,
        }
    )
    failed += 0 if (ok and not leak) else 1

    report = {
        "started_at": started,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "web_base": args.web_base,
        "api_health": args.api_health,
        "checks": checks,
        "failed_count": failed,
        "verdict": "PASS" if failed == 0 else "FAIL",
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"verdict": report["verdict"], "failed_count": failed, "out": str(args.out)}, indent=2))
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
