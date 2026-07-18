#!/usr/bin/env python3
"""Production smoke — adaptive research cascade Phases 1–6 (SSE researchCascade).

Usage:
  python scripts/smoke-research-cascade-prod.py
  python scripts/smoke-research-cascade-prod.py --json docs/delivery/smoke-research-cascade-prod-latest.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import jwt
from dotenv import dotenv_values

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(REPO))

PROD_DEFAULT = os.environ.get(
    "BACKEND_URL",
    "https://gravitre-saas-backend-production.up.railway.app",
).rstrip("/")
ORG_DEFAULT = "cbbf993b-b22f-41ce-964b-1fc25e0dd9ea"
MIN_SHA_PREFIX = "716864e6"


def _load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for path in (BACKEND / ".env", BACKEND / ".env.operator.local", REPO / ".env"):
        if not path.is_file():
            continue
        try:
            merged.update({k: v for k, v in dotenv_values(path).items() if v})
        except UnicodeDecodeError:
            pass
    merged.update({k: v for k, v in os.environ.items() if v})
    return merged


def _mint_token(env: dict[str, str], user_id: str, email: str) -> str:
    url = env["SUPABASE_URL"].rstrip("/")
    secret = env["SUPABASE_JWT_SECRET"]
    now = int(time.time())
    return jwt.encode(
        {
            "sub": user_id,
            "email": email,
            "aud": "authenticated",
            "iss": f"{url}/auth/v1",
            "iat": now,
            "exp": now + 3600,
            "role": "authenticated",
        },
        secret,
        algorithm="HS256",
    )


def _parse_sse(raw: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for block in re.split(r"\n\n+", raw):
        data_lines = [ln[5:].lstrip() for ln in block.splitlines() if ln.startswith("data:")]
        if not data_lines:
            continue
        payload = "\n".join(data_lines).strip()
        if payload in ("", "[DONE]"):
            continue
        try:
            events.append(json.loads(payload))
        except json.JSONDecodeError:
            events.append({"_raw": payload[:300]})
    return events


def _latest_cascade_from_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Match retrieval-ab fingerprint: last researchCascade blob in SSE stream."""
    for ev in reversed(events):
        for container in (ev, ev.get("data") if isinstance(ev.get("data"), dict) else {}):
            if not isinstance(container, dict):
                continue
            cascade = container.get("researchCascade") or container.get("research_cascade")
            if isinstance(cascade, dict) and cascade:
                return cascade
    return {}


def _cascade_from_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    latest = _latest_cascade_from_events(events)
    return [latest] if latest else []


def _request_sse(
    *,
    base_url: str,
    org_id: str,
    token: str,
    body: dict[str, Any],
    timeout: int = 180,
) -> tuple[int, str]:
    url = f"{base_url.rstrip('/')}/api/assistant/chat"
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("X-Org-Id", org_id)
    req.add_header("X-Environment", "production")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "text/event-stream")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return int(resp.status), resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")


def _chat(
    *,
    base_url: str,
    org_id: str,
    token: str,
    text: str,
    conversation_id: str,
    research_scope: str | None = None,
) -> tuple[int, list[dict[str, Any]], list[dict[str, Any]]]:
    body: dict[str, Any] = {
        "messages": [{"role": "user", "content": text}],
        "org_id": org_id,
        "tools": ["knowledge_base", "agent_status", "connector_status"],
        "mode": "fast",
        "conversation_id": conversation_id,
    }
    if research_scope:
        body["research_scope"] = research_scope
    status, raw = _request_sse(base_url=base_url, org_id=org_id, token=token, body=body)
    events = _parse_sse(raw)
    return status, events, _cascade_from_events(events)


def _sha_at_least(deployed: str, minimum: str) -> bool:
    deployed = (deployed or "").strip().lower()
    minimum = minimum.strip().lower()
    if not deployed or not minimum:
        return False
    if deployed.startswith(minimum):
        return True
    try:
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", minimum, deployed],
            check=True,
            capture_output=True,
            cwd=REPO,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return deployed >= minimum


def _fetch_health(base_url: str) -> dict[str, Any]:
    req = urllib.request.Request(f"{base_url.rstrip('/')}/health", method="GET")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return {"http": exc.code}


def run_smoke(args: argparse.Namespace) -> dict[str, Any]:
    env = _load_env()
    for key in ("SUPABASE_URL", "SUPABASE_JWT_SECRET", "SUPABASE_SERVICE_ROLE_KEY"):
        if not env.get(key):
            raise SystemExit(f"Missing {key} — set in env or repo Actions secrets")

    from supabase import create_client

    from scripts.smoke_auth import resolve_smoke_actor_and_email

    client = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
    org_id = (args.org_id or env.get("OAUTH_SMOKE_ORG_ID") or ORG_DEFAULT).strip()
    actor, email = resolve_smoke_actor_and_email(client, org_id=org_id, env=env)
    token = _mint_token(env, actor, email)
    base_url = (args.base_url or PROD_DEFAULT).rstrip("/")
    conv = str(uuid.uuid4())

    report: dict[str, Any] = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "base_url": base_url,
        "org_id": org_id,
        "conversation_id": conv,
        "min_sha_prefix": MIN_SHA_PREFIX,
        "checks": {},
        "pass": False,
    }

    health = _fetch_health(base_url)
    report["health"] = health
    git_sha = str(health.get("git_sha") or "")
    report["checks"]["deploy_sha"] = {
        "pass": _sha_at_least(git_sha, MIN_SHA_PREFIX),
        "git_sha": git_sha,
        "required_prefix": MIN_SHA_PREFIX,
    }

    status1, events1, cascades1 = _chat(
        base_url=base_url,
        org_id=org_id,
        token=token,
        conversation_id=conv,
        text=(
            "What is the exact Q3 2027 revenue forecast for our fictional subsidiary "
            "Zephyr Dynamics in Antarctica? Use only internal org knowledge."
        ),
    )
    thin_cascade = _latest_cascade_from_events(events1)
    report["trace_thin"] = {
        "http_status": status1,
        "cascade_count": 1 if thin_cascade else 0,
        "cascade": thin_cascade,
        "event_count": len(events1),
    }
    report["checks"]["thin_suggest_broaden"] = {
        "pass": bool(thin_cascade.get("suggest_broaden") or thin_cascade.get("internal_thin")),
        "detail": "suggest_broaden or internal_thin in researchCascade SSE",
    }

    status2, events2, cascades2 = _chat(
        base_url=base_url,
        org_id=org_id,
        token=token,
        conversation_id=conv,
        research_scope="everything",
        text=(
            "Summarize what you can find about our refund policy. "
            "Include research confidence and sources used."
        ),
    )
    scoped_cascade = cascades2[-1] if cascades2 else {}
    report["trace_scoped"] = {
        "http_status": status2,
        "cascade_count": len(cascades2),
        "cascade": scoped_cascade,
        "event_count": len(events2),
    }
    has_enrichment = any(
        scoped_cascade.get(key) is not None
        for key in (
            "confidence_band",
            "source_breakdown",
            "stage_progress",
            "progress_steps",
            "active_stages",
        )
    )
    report["checks"]["scoped_enrichment"] = {
        "pass": has_enrichment,
        "detail": "confidence_band/source_breakdown/stage_progress in final researchCascade",
    }
    progress_in_sse = any(
        isinstance(ev.get("data"), dict) and (ev.get("data") or {}).get("progressSteps")
        for ev in events2
        if ev.get("type") == "data-intelligence"
    )
    report["checks"]["progress_steps_sse"] = {
        "pass": progress_in_sse or bool(scoped_cascade.get("progress_steps")),
        "detail": "progressSteps in mid/final SSE",
    }

    deploy_ok = report["checks"]["deploy_sha"]["pass"]
    thin_ok = report["checks"]["thin_suggest_broaden"]["pass"]
    enrich_ok = report["checks"]["scoped_enrichment"]["pass"]
    report["pass"] = deploy_ok and status1 == 200 and status2 == 200 and thin_ok and enrich_ok
    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Prod smoke — research cascade SSE")
    parser.add_argument("--base-url", default=PROD_DEFAULT)
    parser.add_argument("--org-id", default=None)
    parser.add_argument("--json", dest="json_path", default=None)
    args = parser.parse_args()
    report = run_smoke(args)
    text = json.dumps(report, indent=2, default=str)
    print(text)
    if args.json_path:
        out = Path(args.json_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
    return 0 if report.get("pass") else 1


if __name__ == "__main__":
    raise SystemExit(main())
