"""Read-only ECO-001 HTTP ingress acceptance against an actually deployed nonproduction FastAPI backend.

Does NOT execute providers, mutate application data, or assert approvals succeeded.
Rejects a frontend-only preview, mismatched SHA, production environment, or unguarded
authenticated endpoint. Owner-approved write/readback acceptance remains separate.
"""
from __future__ import annotations

import argparse
import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


def get(url: str, headers: dict[str, str] | None = None) -> tuple[int, bytes]:
    req = Request(url, headers=headers or {}, method="GET")
    try:
        with urlopen(req, timeout=12) as response:
            return response.status, response.read(65536)
    except HTTPError as error:
        return error.code, error.read(65536)


def run(base: str, expected_sha: str, headers: dict[str, str]) -> dict:
    parsed = urlsplit(base)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("A valid HTTPS nonproduction backend URL is mandatory")
    base = base.rstrip("/")
    code, raw = get(base + "/health", headers)
    if code != 200:
        raise ValueError(f"FastAPI /health returned HTTP {code}")
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("FastAPI /health did not return JSON") from exc
    if not isinstance(payload, dict) or "checks" not in payload or "unified_turn_live_enabled" not in payload:
        raise ValueError("Backend-specific /health fields absent (possibly frontend preview)")
    env = str(payload.get("environment") or "").lower()
    if env in {"", "production", "prod", "live"}:
        raise ValueError("Refusing a production or unidentified runtime")
    runtime_sha = str(payload.get("git_sha") or "")
    if runtime_sha != expected_sha:
        raise ValueError(f"Runtime git SHA mismatch or absent ({runtime_sha[:12]})")
    if payload.get("checks", {}).get("database") != "healthy":
        raise ValueError("Nonproduction backend has no verified database connectivity")
    # GET of a nonexistent conversation: authentication must be required
    # before tenant-owned state can be retrieved. This never dispatches work.
    checks = {}
    for route in (
        "/api/assistant/conversation/eco001-nonexistent/state",
    ):
        status, _ = get(base + route, headers)
        if status not in {401, 403}:
            raise ValueError(f"Protected GET unexpectedly returned HTTP {status}")
        checks[route] = status
    return {
        "scope": "deployed_nonproduction_backend_read_only",
        "classification": "runtime_identity_and_auth_preflight_not_write_acceptance",
        "expected_sha": expected_sha,
        "runtime_sha": runtime_sha,
        "environment": env,
        "database_check": "healthy",
        "protected_route_statuses": checks,
        "pass": True,
        "provider_write_performed": False,
        "owner_approval_inferred": False,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--sha", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    # Do not add auth headers: the check is that an anonymous caller is denied.
    report = run(args.url, args.sha, {})
    with open(args.output, "w", encoding="utf8") as out:
        json.dump(report, out, sort_keys=True, indent=2)
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
