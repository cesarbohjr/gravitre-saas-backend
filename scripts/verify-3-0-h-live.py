#!/usr/bin/env python3
"""Live 3.0-H store join + catalog classification + NL listing F2 on isolated org.

Does not invent a multi-provider OAuth PASS. WRITE is not requested.
"""
from __future__ import annotations

import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx
import jwt
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(ROOT / "scripts"))

from isolated_conversation_org import resolve_isolated_conversation_actor, smoke_http_headers  # noqa: E402

BASE = os.environ.get("LIVE_API_BASE", "https://api.gravitre.app").rstrip("/")
OUT = ROOT / "docs" / "delivery" / "3.0-h-live.json"
REQUIRED_SHA_PREFIX = os.environ.get("REQUIRED_SHA_PREFIX", "")


def load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for p in (BACKEND / ".env", ROOT / ".env", BACKEND / ".env.operator.local"):
        if not p.is_file():
            continue
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                loaded = dotenv_values(p, encoding=enc)
                merged.update({k: v for k, v in loaded.items() if v})
                break
            except UnicodeDecodeError:
                continue
    for k, v in os.environ.items():
        if v and k not in merged:
            merged[k] = v
    for k in (
        "SUPABASE_URL",
        "SUPABASE_SERVICE_ROLE_KEY",
        "SUPABASE_JWT_SECRET",
        "SUPABASE_ANON_KEY",
        "SUPABASE_KEY",
    ):
        if merged.get(k):
            os.environ[k] = merged[k]
    return merged


def mint(env: dict[str, str], user_id: str, email: str) -> str:
    url = env["SUPABASE_URL"].rstrip("/")
    return jwt.encode(
        {
            "sub": user_id,
            "email": email,
            "aud": "authenticated",
            "iss": f"{url}/auth/v1",
            "iat": int(time.time()),
            "exp": int(time.time()) + 7200,
            "role": "authenticated",
        },
        env["SUPABASE_JWT_SECRET"],
        algorithm="HS256",
    )


def wait_health(prefix: str, timeout_s: int = 720) -> dict:
    deadline = time.time() + timeout_s
    last = {}
    while time.time() < deadline:
        try:
            resp = httpx.get(f"{BASE}/health", timeout=30)
            last = resp.json() if resp.status_code == 200 else {"status": resp.status_code}
            sha = str(last.get("git_sha") or "")
            if not prefix or sha.startswith(prefix):
                return last
        except Exception as exc:  # noqa: BLE001
            last = {"error": str(exc)}
        time.sleep(15)
    return last


def stream_turn(http: httpx.Client, headers: dict, conv: str, org_id: str, prompt: str, history: list) -> dict:
    history.append({"role": "user", "parts": [{"type": "text", "text": prompt}]})
    t0 = time.perf_counter()
    first_text_ms = None
    buf: list[str] = []
    with http.stream(
        "POST",
        f"{BASE}/api/assistant/chat",
        headers=headers,
        json={
            "messages": history,
            "org_id": org_id,
            "mode": "fast",
            "conversation_id": conv,
        },
        timeout=180,
    ) as resp:
        status = resp.status_code
        for piece in resp.iter_text():
            if first_text_ms is None and "text-delta" in piece:
                first_text_ms = int((time.perf_counter() - t0) * 1000)
            buf.append(piece)
    raw = "".join(buf)
    texts: list[str] = []
    for block in raw.split("\n\n"):
        data_lines = [ln[5:].lstrip() for ln in block.splitlines() if ln.startswith("data:")]
        if not data_lines:
            continue
        payload = "\n".join(data_lines).strip()
        if not payload or payload == "[DONE]":
            continue
        try:
            obj = json.loads(payload)
        except json.JSONDecodeError:
            continue
        if obj.get("type") in {"text-delta", "text"}:
            texts.append(str(obj.get("delta") or obj.get("text") or ""))
    assistant = "".join(texts).strip()
    if assistant:
        history.append({"role": "assistant", "parts": [{"type": "text", "text": assistant}]})
    return {
        "http_status": status,
        "first_useful_text_ms": first_text_ms,
        "completion_ms": int((time.perf_counter() - t0) * 1000),
        "assistant_excerpt": assistant[:1600],
        "assistant_len": len(assistant),
    }


def audit_rows(env: dict[str, str], *, conversation_id: str, action: str, since_iso: str) -> list[dict]:
    url = env["SUPABASE_URL"].rstrip("/")
    key = env["SUPABASE_SERVICE_ROLE_KEY"]
    with httpx.Client(timeout=30) as client:
        resp = client.get(
            f"{url}/rest/v1/audit_events",
            params={
                "action": f"eq.{action}",
                "resource_id": f"eq.{conversation_id}",
                "created_at": f"gte.{since_iso}",
                "select": "id,created_at,org_id,actor_id,resource_id,action,metadata",
                "order": "created_at.desc",
                "limit": "8",
            },
            headers={"apikey": key, "Authorization": f"Bearer {key}"},
        )
        if resp.status_code != 200:
            return []
        rows = resp.json()
        return rows if isinstance(rows, list) else []


def main() -> int:
    env = load_env()
    from supabase import create_client

    sb = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
    org_id, user_id, email = resolve_isolated_conversation_actor(env, sb)
    health = wait_health(REQUIRED_SHA_PREFIX)
    sha = str(health.get("git_sha") or "")
    token = mint(env, user_id, email)
    headers = {
        **smoke_http_headers(),
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
        "x-org-id": org_id,
    }
    json_headers = {k: v for k, v in headers.items() if k != "Accept"}
    json_headers["Accept"] = "application/json"
    catalog_conv = str(uuid.uuid4())
    listing_conv = str(uuid.uuid4())
    entity_conv = str(uuid.uuid4())
    since = datetime.now(timezone.utc).isoformat()
    catalog: dict = {}
    listing: dict = {}
    entity: dict = {}
    with httpx.Client(timeout=180) as http:
        for conv, title in (
            (catalog_conv, "3.0-h-catalog"),
            (listing_conv, "3.0-h-listing-f2"),
            (entity_conv, "3.0-h-entity"),
        ):
            created = http.post(
                f"{BASE}/api/conversations",
                headers=json_headers,
                json={"title": title, "id": conv},
                timeout=60,
            )
            if created.status_code < 400:
                body = created.json() or {}
                cid = str(body.get("id") or conv)
                if conv == catalog_conv:
                    catalog_conv = cid
                elif conv == listing_conv:
                    listing_conv = cid
                else:
                    entity_conv = cid
        catalog_hist: list = []
        catalog = stream_turn(
            http,
            headers,
            catalog_conv,
            org_id,
            "Which connected tools can I use? Search the tool catalog.",
            catalog_hist,
        )
        listing_hist: list = []
        listing = stream_turn(
            http,
            headers,
            listing_conv,
            org_id,
            "List all HubSpot deals",
            listing_hist,
        )
        entity_hist: list = []
        entity = stream_turn(
            http,
            headers,
            entity_conv,
            org_id,
            "What do we know about Alpha across HubSpot, QuickBooks, and Zendesk?",
            entity_hist,
        )

    repairs = audit_rows(env, conversation_id=listing_conv, action="f2.read.repair", since_iso=since)
    catalog_text = str(catalog.get("assistant_excerpt") or "").lower()
    entity_text = str(entity.get("assistant_excerpt") or "").lower()
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "health_sha": sha,
        "org_id": org_id,
        "catalog": {
            **catalog,
            "conversation_id": catalog_conv,
            "write_labeled": "approval required" in catalog_text and "write" in catalog_text,
            "writes_started_claim": "not executed" in catalog_text or "approval required" in catalog_text,
        },
        "listing": {
            **listing,
            "conversation_id": listing_conv,
            "f2_repair_rows": repairs,
            "nl_f2_proven": bool(repairs),
        },
        "entity": {
            **entity,
            "conversation_id": entity_conv,
            "store_join_language": "accepted company entity" in entity_text or "entity id" in entity_text,
            "live_multi_provider_pass": False,
            "limitation": "QBO/Zendesk live OAuth not required for store answer; do not invent PASS",
        },
    }
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2)[:8000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
