#!/usr/bin/env python3
"""Prod smoke: assign expert pack → refresh → persists; remove from second agent → KB remains."""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import jwt
from dotenv import dotenv_values

REPO = Path(__file__).resolve().parent.parent

BASE = (
    os.environ.get("GRAVITRE_PROD_WEB_URL")
    or ("http://localhost:3010" if os.environ.get("SMOKE_USE_LOCAL") == "1" else "https://gravitre.app")
).rstrip("/")
TOKEN = (os.environ.get("GRAVITRE_PROD_BEARER") or os.environ.get("SMOKE_BEARER") or "").strip()
AGENT_A = (os.environ.get("SMOKE_AGENT_A_ID") or "").strip()
AGENT_B = (os.environ.get("SMOKE_AGENT_B_ID") or "").strip()
PACK_ID = (os.environ.get("SMOKE_EXPERT_PACK_ID") or "pack.sales-playbook").strip()
SOURCE_ID = (os.environ.get("SMOKE_RAG_SOURCE_ID") or "").strip()


def _load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for path in (REPO / "backend" / ".env", REPO / "backend" / ".env.operator.local"):
        if not path.is_file():
            continue
        merged.update({k: v for k, v in dotenv_values(path).items() if v})
    merged.update({k: v for k, v in os.environ.items() if v})
    return merged


def _mint_token(env: dict[str, str], user_id: str, email: str) -> str:
    secret = env.get("SUPABASE_JWT_SECRET", "")
    supabase_url = env.get("SUPABASE_URL", "").rstrip("/")
    if not secret or not supabase_url:
        raise SystemExit("SUPABASE_JWT_SECRET and SUPABASE_URL required to mint bearer")
    now = int(time.time())
    return jwt.encode(
        {
            "sub": user_id,
            "email": email,
            "aud": "authenticated",
            "iss": f"{supabase_url}/auth/v1",
            "iat": now,
            "exp": now + 3600,
            "role": "authenticated",
        },
        secret,
        algorithm="HS256",
    )


def _bootstrap_from_env() -> None:
    global TOKEN, AGENT_A, AGENT_B, SOURCE_ID
    if TOKEN and AGENT_A:
        return
    env = _load_env()
    sys.path.insert(0, str(REPO / "scripts"))
    from smoke_auth import resolve_smoke_actor_and_email  # noqa: WPS433

    from supabase import create_client

    url = env.get("SUPABASE_URL")
    key = env.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise SystemExit("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY required")
    client = create_client(url, key)

    members = client.table("organization_members").select("org_id, user_id, role").limit(5).execute()
    if not members.data:
        raise SystemExit("No organization_members rows found")
    org_id = str(members.data[0]["org_id"])
    user_id, email = resolve_smoke_actor_and_email(client, org_id=org_id, env=env)
    if not TOKEN:
        TOKEN = _mint_token(env, user_id, email)

    if not AGENT_A or not AGENT_B or not SOURCE_ID:
        agents = (
            client.table("agents")
            .select("id, name")
            .eq("org_id", org_id)
            .limit(3)
            .execute()
            .data
            or []
        )
        if len(agents) >= 1 and not AGENT_A:
            AGENT_A = str(agents[0]["id"])
        if len(agents) >= 2 and not AGENT_B:
            AGENT_B = str(agents[1]["id"])
        if not SOURCE_ID:
            sources = (
                client.table("rag_sources")
                .select("id, name")
                .eq("org_id", org_id)
                .is_("deleted_at", "null")
                .limit(1)
                .execute()
                .data
                or []
            )
            if sources:
                SOURCE_ID = str(sources[0]["id"])


def _request(method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
    url = f"{BASE}{path}"
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        try:
            payload = json.loads(raw) if raw else {"error": exc.reason}
        except json.JSONDecodeError:
            payload = {"error": raw or exc.reason}
        return exc.code, payload


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main() -> int:
    try:
        _bootstrap_from_env()
    except SystemExit as exc:
        print(f"NOT RUN — {exc}", file=sys.stderr)
        return 2

    if not TOKEN or not AGENT_A:
        print(
            "NOT RUN — could not mint bearer or resolve SMOKE_AGENT_A_ID "
            "(set env vars or ensure backend/.env has Supabase credentials)",
            file=sys.stderr,
        )
        return 2

    print(f"[{_stamp()}] Agent knowledge prod verify against {BASE}")
    print(f"  agent_a={AGENT_A} agent_b={AGENT_B or '(skip)'} source={SOURCE_ID or '(skip)'} pack={PACK_ID}")

    status, listed = _request("GET", f"/api/agents/{AGENT_A}/knowledge-assignments")
    if status >= 400:
        print(f"FAIL list assignments HTTP {status}: {listed}", file=sys.stderr)
        return 1

    before_ids = {str(a.get("sourceId")) for a in listed.get("assignments") or []}

    status, created = _request(
        "POST",
        f"/api/agents/{AGENT_A}/knowledge-assignments",
        {
            "sourceType": "knowledge_pack",
            "sourceId": PACK_ID,
            "label": f"Smoke pack {PACK_ID}",
            "enabled": True,
            "metadata": {"fabric_pack": True},
        },
    )
    if status >= 400 and PACK_ID not in before_ids:
        print(f"FAIL assign pack HTTP {status}: {created}", file=sys.stderr)
        return 1

    status, after_assign = _request("GET", f"/api/agents/{AGENT_A}/knowledge-assignments")
    after_ids = {str(a.get("sourceId")) for a in after_assign.get("assignments") or []}
    if PACK_ID not in after_ids:
        print("FAIL pack missing after assign + refresh", file=sys.stderr)
        return 1
    print(f"PASS — pack {PACK_ID} assigned @ {_stamp()}")

    assignment_id = next(
        (str(a.get("id")) for a in after_assign.get("assignments") or [] if str(a.get("sourceId")) == PACK_ID),
        "",
    )

    if AGENT_B and SOURCE_ID:
        status, _ = _request(
            "POST",
            f"/api/agents/{AGENT_B}/knowledge-assignments",
            {
                "sourceType": "rag_source",
                "sourceId": SOURCE_ID,
                "label": "Smoke org KB",
                "enabled": True,
            },
        )
        if status >= 400:
            print(f"FAIL assign org source to agent B HTTP {status}", file=sys.stderr)
            return 1

        _, b_assignments = _request("GET", f"/api/agents/{AGENT_B}/knowledge-assignments")
        b_row = next(
            (a for a in b_assignments.get("assignments") or [] if str(a.get("sourceId")) == SOURCE_ID),
            None,
        )
        if not b_row or not b_row.get("id"):
            print("FAIL agent B assignment missing", file=sys.stderr)
            return 1

        status, _ = _request("DELETE", f"/api/agents/{AGENT_B}/knowledge-assignments/{b_row['id']}")
        if status >= 400:
            print(f"FAIL remove from agent B HTTP {status}", file=sys.stderr)
            return 1

        status, source_check = _request("GET", f"/api/sources/{SOURCE_ID}")
        if status >= 400:
            print(f"FAIL org source deleted after unassign HTTP {status}", file=sys.stderr)
            return 1
        print(f"PASS — rag_source {SOURCE_ID} still present after agent B unassign @ {_stamp()}")

    if assignment_id:
        status, _ = _request("DELETE", f"/api/agents/{AGENT_A}/knowledge-assignments/{assignment_id}")
        if status >= 400:
            print(f"WARN cleanup delete failed HTTP {status}", file=sys.stderr)

    print(f"PASS — agent knowledge assign/remove prod verify @ {_stamp()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
