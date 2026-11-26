"""Read-only ECO-001 HTTP ingress acceptance against an actually deployed nonproduction FastAPI backend.

Does NOT execute providers, mutate application data, or assert approvals succeeded.
Rejects a frontend-only preview, mismatched SHA, production environment, or unguarded
authenticated endpoint. Owner-approved write/readback acceptance remains separate.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

QA_ORIGIN = "https://eco001-fastapi-qa.up.railway.app"


class _RejectRedirects(HTTPRedirectHandler):
    """Never follow a preflight redirect to an unverified host or environment."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def get(url: str, headers: dict[str, str] | None = None) -> tuple[int, bytes]:
    req = Request(url, headers=headers or {}, method="GET")
    try:
        with build_opener(_RejectRedirects()).open(req, timeout=12) as response:
            return response.status, response.read(65536)
    except HTTPError as error:
        return error.code, error.read(65536)


def run(
    base: str,
    expected_sha: str,
    headers: dict[str, str],
    *,
    qa_bearer: str | None = None,
    qa_conversation: str | None = None,
) -> dict:
    parsed = urlsplit(base)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("A valid HTTPS nonproduction backend URL is mandatory")
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment or parsed.port == 0:
        raise ValueError("Backend URL must be an HTTPS origin without path, query, or fragment")
    if not re.fullmatch(r"[0-9a-fA-F]{40}", expected_sha):
        raise ValueError("Expected deployment SHA must be a full 40-character Git commit")
    base = base.rstrip("/")
    signed = qa_bearer is not None or qa_conversation is not None
    if signed:
        if base != QA_ORIGIN:
            raise ValueError("Signed preflight requires the isolated Railway QA origin")
        if not re.fullmatch(r"[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", qa_bearer or ""):
            raise ValueError("Signed preflight requires a QA actor access token")
        if (
            not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", qa_conversation or "")
            or qa_conversation == "eco001-nonexistent"
        ):
            raise ValueError("Signed preflight requires an owned QA conversation fixture")
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
    if env not in {"development", "dev", "test", "testing", "qa", "staging", "preview"}:
        raise ValueError("Refusing a production or unidentified runtime")
    runtime_sha = str(payload.get("git_sha") or "")
    if runtime_sha != expected_sha:
        raise ValueError(f"Runtime git SHA mismatch or absent ({runtime_sha[:12]})")
    if not isinstance(payload.get("checks"), dict) or payload["checks"].get("database") != "healthy":
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
    report = {
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
    if signed:
        if env != "qa":
            raise ValueError("Signed preflight requires the running environment to report qa")
        route = f"/api/assistant/conversation/{qa_conversation}/state"
        status, _ = get(base + route)
        if status not in {401, 403}:
            raise ValueError(f"Anonymous fixture GET unexpectedly returned HTTP {status}")
        signed_status, raw = get(base + route, {"Authorization": f"Bearer {qa_bearer}"})
        if signed_status != 200:
            raise ValueError(f"Signed fixture GET returned HTTP {signed_status}")
        try:
            state = json.loads(raw)
        except (TypeError, ValueError):
            raise ValueError("Signed fixture GET did not return JSON") from None
        if not isinstance(state, dict) or not {"task_state", "execution_result"} <= state.keys():
            raise ValueError("Signed fixture GET did not return conversation state")
        report["signed_fixture_statuses"] = {"anonymous": status, "authenticated": signed_status}
    return report


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--sha", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--signed-qa", action="store_true", help="Check an owned fixture using credentials from the environment")
    args = ap.parse_args()
    signed_args = {
        "qa_bearer": os.environ.get("ECO001_QA_BEARER", ""),
        "qa_conversation": os.environ.get("ECO001_QA_CONVERSATION", ""),
    } if args.signed_qa else {}
    report = run(args.url, args.sha, {}, **signed_args)
    with open(args.output, "w", encoding="utf8") as out:
        json.dump(report, out, sort_keys=True, indent=2)
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
