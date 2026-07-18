#!/usr/bin/env python3
"""Live A/B fingerprints — representative chat queries after retrieval changes.

Compares tool-call shape, routing tier, approval behavior, and SSE event types
against frozen baselines. Intended to catch orchestration regressions unit tests miss.

Usage:
  python scripts/smoke-retrieval-ab-live.py
  python scripts/smoke-retrieval-ab-live.py --json docs/delivery/retrieval-ab-live-latest.json
"""
from __future__ import annotations

import argparse
import json
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

PROD_DEFAULT = "https://gravitre-saas-backend-production.up.railway.app"
ORG_DEFAULT = "cbbf993b-b22f-41ce-964b-1fc25e0dd9ea"
BASELINE_PATH = REPO / "docs" / "delivery" / "retrieval-ab-baseline.json"

QUERIES: list[dict[str, Any]] = [
    {
        "id": "A_fast_connectors",
        "message": "What connectors are connected? (retrieval-ab A {tag})",
        "mode": "fast",
        "expect": {
            "http": 200,
            "routing_tiers_contains": ["simple"],
            "effective_modes_contains": ["fast"],
            "tool_names_contains": ["getConnectorStatus"],
            "forbidden_error_codes": ["write_approval_required"],
        },
    },
    {
        "id": "B_write_intent_gate",
        "message": (
            "Create an Apollo contact list named exactly 'gravitre-retrieval-ab-{tag}' "
            "with no contacts. Use Apollo only."
        ),
        "mode": "fast",
        "expect": {
            "http": 200,
            "routing_tiers_any_of": ["multi_step", "research"],
            "requires_pending_or_gate": True,
            "allowed_error_codes": ["write_approval_required"],
        },
    },
    {
        "id": "C_org_kb",
        "message": "What is our refund policy? Answer from internal knowledge only. (retrieval-ab C {tag})",
        "mode": "fast",
        "expect": {
            "http": 200,
            "tool_names_any_of": ["searchKnowledgeBase", "search_knowledge_base"],
            "forbidden_error_codes": ["write_approval_required"],
        },
    },
    {
        "id": "D_thin_broaden",
        "message": (
            "What is the exact Q3 2027 revenue forecast for our fictional subsidiary "
            "Zephyr Dynamics in Antarctica? Use only internal org knowledge. (retrieval-ab D {tag})"
        ),
        "mode": "fast",
        "expect": {
            "http": 200,
            "research_cascade_expect": "suggest_broaden_or_internal_thin",
        },
    },
    {
        "id": "E_fast_honesty",
        "message": "Reply with one sentence: what mode are you in? (retrieval-ab E {tag})",
        "mode": "fast",
        "expect": {
            "http": 200,
            "effective_modes_contains": ["fast"],
            "forbidden_error_codes": ["write_approval_required"],
        },
    },
]


def _load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for path in (BACKEND / ".env", BACKEND / ".env.operator.local", REPO / ".env"):
        if not path.is_file():
            continue
        try:
            merged.update({k: v for k, v in dotenv_values(path).items() if v})
        except UnicodeDecodeError:
            pass
    merged.update({k: v for k, v in __import__("os").environ.items() if v})
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


def _fingerprint(events: list[dict[str, Any]]) -> dict[str, Any]:
    tool_names: list[str] = []
    error_codes: list[str] = []
    routing_tiers: list[str] = []
    effective_modes: list[str] = []
    research_cascades: list[dict[str, Any]] = []
    text_parts: list[str] = []
    pending_seen = False

    for ev in events:
        et = str(ev.get("type") or "")
        if et == "text-delta":
            text_parts.append(str(ev.get("delta") or ""))
        if et in {"tool-input-available", "tool-input-start"}:
            name = str(ev.get("toolName") or ev.get("name") or "")
            if name:
                tool_names.append(name)
        output = ev.get("output") if isinstance(ev.get("output"), dict) else {}
        if et == "tool-output-available" and isinstance(output, dict):
            code = str(output.get("errorCode") or "")
            if code:
                error_codes.append(code)
        if et == "data-intelligence":
            data = ev.get("data") if isinstance(ev.get("data"), dict) else {}
            intel = data or ev
            rt = str(intel.get("routingTier") or (intel.get("routing") or {}).get("routingTier") or "")
            em = str(intel.get("effectiveMode") or "")
            if rt:
                routing_tiers.append(rt)
            if em:
                effective_modes.append(em)
            if intel.get("pendingTask") or intel.get("pending_task"):
                pending_seen = True
            cascade = intel.get("researchCascade") or intel.get("research_cascade")
            if isinstance(cascade, dict):
                research_cascades.append(cascade)

    return {
        "tool_names": tool_names,
        "error_codes": error_codes,
        "routing_tiers": routing_tiers,
        "effective_modes": effective_modes,
        "final_routingTier": routing_tiers[-1] if routing_tiers else None,
        "final_effectiveMode": effective_modes[-1] if effective_modes else None,
        "pending_seen": pending_seen,
        "research_cascade_final": research_cascades[-1] if research_cascades else None,
        "text_head": "".join(text_parts)[:400],
        "event_types": sorted({str(ev.get("type") or "") for ev in events}),
    }


def _chat(
    *,
    base_url: str,
    org_id: str,
    token: str,
    message: str,
    mode: str,
) -> tuple[int, list[dict[str, Any]]]:
    body = {
        "messages": [{"role": "user", "content": message}],
        "org_id": org_id,
        "tools": ["knowledge_base", "agent_status", "connector_status"],
        "mode": mode,
        "conversation_id": str(uuid.uuid4()),
    }
    url = f"{base_url.rstrip('/')}/api/assistant/chat"
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("X-Org-Id", org_id)
    req.add_header("X-Environment", "production")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "text/event-stream")
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            return int(resp.status), _parse_sse(resp.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        return exc.code, _parse_sse(exc.read().decode("utf-8", errors="replace"))


def _contains_any(haystack: list[str], needles: list[str]) -> bool:
    lowered = {str(x).lower() for x in haystack}
    return any(str(n).lower() in lowered or any(str(n).lower() in h for h in lowered) for n in needles)


def _evaluate(query: dict[str, Any], fp: dict[str, Any], http: int) -> tuple[bool, list[str]]:
    expect = query.get("expect") or {}
    reasons: list[str] = []
    ok = True

    if expect.get("http") and http != expect["http"]:
        ok = False
        reasons.append(f"http {http} != expected {expect['http']}")

    if expect.get("routing_tiers_contains"):
        for tier in expect["routing_tiers_contains"]:
            if tier not in (fp.get("routing_tiers") or []):
                ok = False
                reasons.append(f"missing routing tier {tier}")

    if expect.get("routing_tiers_any_of"):
        if not _contains_any(fp.get("routing_tiers") or [], expect["routing_tiers_any_of"]):
            ok = False
            reasons.append(f"routing tiers {fp.get('routing_tiers')} not in {expect['routing_tiers_any_of']}")

    if expect.get("effective_modes_contains"):
        for mode in expect["effective_modes_contains"]:
            if mode not in (fp.get("effective_modes") or []):
                ok = False
                reasons.append(f"missing effectiveMode {mode}")

    if expect.get("tool_names_contains"):
        for tool in expect["tool_names_contains"]:
            if tool not in (fp.get("tool_names") or []):
                ok = False
                reasons.append(f"missing tool {tool}")

    if expect.get("tool_names_any_of"):
        if not _contains_any(fp.get("tool_names") or [], expect["tool_names_any_of"]):
            ok = False
            reasons.append(f"tools {fp.get('tool_names')} missing any of {expect['tool_names_any_of']}")

    if expect.get("forbidden_error_codes"):
        for code in expect["forbidden_error_codes"]:
            if code in (fp.get("error_codes") or []):
                ok = False
                reasons.append(f"forbidden error code {code}")

    if expect.get("allowed_error_codes"):
        codes = fp.get("error_codes") or []
        if codes and not all(c in expect["allowed_error_codes"] for c in codes):
            ok = False
            reasons.append(f"unexpected error codes {codes}")

    if expect.get("requires_pending_or_gate"):
        has_gate = "write_approval_required" in (fp.get("error_codes") or [])
        if not (fp.get("pending_seen") or has_gate):
            ok = False
            reasons.append("expected pending task or write_approval_required gate")

    cascade = fp.get("research_cascade_final") or {}
    if expect.get("research_cascade_expect") == "suggest_broaden_or_internal_thin":
        if not (cascade.get("suggest_broaden") or cascade.get("internal_thin")):
            ok = False
            reasons.append("expected suggest_broaden or internal_thin in researchCascade")

    return ok, reasons


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


def run_smoke(args: argparse.Namespace) -> dict[str, Any]:
    env = _load_env()
    for key in ("SUPABASE_URL", "SUPABASE_JWT_SECRET", "SUPABASE_SERVICE_ROLE_KEY"):
        if not env.get(key):
            raise SystemExit(f"Missing {key}")

    from supabase import create_client

    client = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
    org_id = (args.org_id or env.get("OAUTH_SMOKE_ORG_ID") or ORG_DEFAULT).strip()
    actor = (env.get("OAUTH_SMOKE_USER_ID") or "").strip()
    if not actor:
        rows = client.table("organization_members").select("user_id").eq("org_id", org_id).limit(1).execute()
        actor = str((rows.data or [{}])[0].get("user_id") or "")
    users = client.auth.admin.get_user_by_id(actor)
    email = (users.user.email if users and users.user else None) or f"{actor}@gravitre.local"
    token = _mint_token(env, actor, email)
    base_url = (args.base_url or PROD_DEFAULT).rstrip("/")
    tag = datetime.now(timezone.utc).strftime("%Y%m%d%H%M")

    report: dict[str, Any] = {
        "probe": "retrieval_ab_live",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "base_url": base_url,
        "org_id": org_id,
        "actor_id": actor,
        "min_sha_prefix": args.min_sha,
        "queries": {},
        "pass": False,
    }

    req = urllib.request.Request(f"{base_url}/health", method="GET")
    with urllib.request.urlopen(req, timeout=30) as resp:
        health = json.loads(resp.read().decode("utf-8"))
    git_sha = str(health.get("git_sha") or "")
    report["health"] = health
    report["deploy_sha_ok"] = _sha_at_least(git_sha, args.min_sha)

    all_ok = report["deploy_sha_ok"]
    for spec in QUERIES:
        qid = spec["id"]
        message = spec["message"].format(tag=tag)
        http, events = _chat(
            base_url=base_url,
            org_id=org_id,
            token=token,
            message=message,
            mode=str(spec.get("mode") or "fast"),
        )
        fp = _fingerprint(events)
        passed, reasons = _evaluate(spec, fp, http)
        all_ok = all_ok and passed
        report["queries"][qid] = {
            "pass": passed,
            "http": http,
            "conversation_fingerprint": fp,
            "reasons": reasons,
            "message": message,
        }

    report["pass"] = all_ok
    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=PROD_DEFAULT)
    parser.add_argument("--org-id", default=None)
    parser.add_argument("--min-sha", default="4eb6adbe", help="Research Manager commit prefix")
    parser.add_argument("--json", dest="json_path", default=str(REPO / "docs/delivery/retrieval-ab-live-latest.json"))
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
