#!/usr/bin/env python3
"""STA-305 prod probe — Slack draft segment must not map to List channels.

Local mapper check always runs. Live chat when STA305_LIVE=1.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import jwt
from dotenv import dotenv_values
from httpx import AsyncClient

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

OUT = ROOT / "docs" / "delivery" / "sta305-catalog-kind-prod.json"
ORG = "cbbf993b-b22f-41ce-964b-1fc25e0dd9ea"
BASE = "https://gravitre-saas-backend-production.up.railway.app"
SEGMENT = "draft a follow-up in Slack for approval"
CHAT_TIMEOUT = 180.0


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_env() -> None:
    for p in (
        BACKEND / ".env",
        BACKEND / ".env.operator.local",
        ROOT / ".env",
        ROOT / ".env.operator.local",
    ):
        if not p.is_file():
            continue
        for k, v in dotenv_values(p).items():
            if v:
                os.environ.setdefault(k, v)


def local_mapper_probe() -> dict[str, Any]:
    from app.services.chat_action_mapper import get_chat_action_mapper

    match = get_chat_action_mapper().match_segment(
        SEGMENT,
        connected_integrations=["slack"],
    )
    action = match.entry.registry_key if match else None
    return {
        "segment": SEGMENT,
        "matched_action": action,
        "kind": match.entry.kind if match else None,
        "score": match.score if match else None,
        "args": dict(match.args) if match else None,
        "pass": bool(
            match
            and "post_message" in (action or "")
            and "list" not in (match.entry.action_key or "")
        ),
    }


def parse_sse(raw: str) -> dict[str, Any]:
    texts: list[str] = []
    labels: list[str] = []
    for block in re.split(r"\n\n+", raw):
        data_lines = [ln[5:].lstrip() for ln in block.splitlines() if ln.startswith("data:")]
        if not data_lines:
            continue
        payload = "\n".join(data_lines).strip()
        if payload in ("", "[DONE]"):
            continue
        try:
            o = json.loads(payload)
        except json.JSONDecodeError:
            continue
        t = o.get("type")
        if t == "text-delta":
            texts.append(o.get("delta") or "")
        blob = json.dumps(o)
        for m in re.finditer(r'"(?:label|displayName|title|name)"\s*:\s*"([^"]{2,80})"', blob):
            labels.append(m.group(1))
        for m in re.finditer(r"(List channels|Post (?:Slack )?message|Post message)", blob, re.I):
            labels.append(m.group(1))
    text = "".join(texts)
    return {"text": text, "labels": list(dict.fromkeys(labels))[:20]}


async def live_chat_probe() -> dict[str, Any]:
    load_env()
    from app.config import get_settings
    from app.workflows.repository import get_supabase_client

    settings = get_settings()
    client = get_supabase_client(settings)
    actor = os.environ.get("OAUTH_SMOKE_USER_ID") or (
        client.table("organization_members")
        .select("user_id")
        .eq("org_id", ORG)
        .limit(1)
        .execute()
        .data[0]["user_id"]
    )
    email = (client.auth.admin.get_user_by_id(actor).user.email) or f"{actor}@gravitre.local"
    url = os.environ["SUPABASE_URL"].rstrip("/")
    now = int(time.time())
    tok = jwt.encode(
        {
            "sub": actor,
            "email": email,
            "aud": "authenticated",
            "iss": f"{url}/auth/v1",
            "iat": now,
            "exp": now + 3600,
            "role": "authenticated",
        },
        os.environ["SUPABASE_JWT_SECRET"],
        algorithm="HS256",
    )
    hdr = {
        "Authorization": f"Bearer {tok}",
        "X-Org-Id": ORG,
        "X-Environment": "production",
        "Content-Type": "application/json",
    }
    marker = uuid.uuid4().hex[:8]
    conversation_id = str(uuid.uuid4())
    message = f"Search HubSpot for high-intent leads and {SEGMENT} [STA-305 {marker}]"
    async with AsyncClient(base_url=BASE, timeout=CHAT_TIMEOUT, verify=False) as ac:
        health = await ac.get("/health")
        sha = None
        try:
            body = health.json()
            sha = body.get("git_sha") or body.get("sha") or body.get("version")
        except Exception:
            pass
        t0 = time.perf_counter()
        r = await ac.post(
            "/api/assistant/chat",
            headers=hdr,
            json={
                "messages": [{"role": "user", "parts": [{"type": "text", "text": message}]}],
                "org_id": ORG,
                "tools": ["knowledge_base", "connector_status", "slack_post_message"],
                "mode": "standard",
                "conversation_id": conversation_id,
            },
        )
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        parsed = parse_sse(r.text)
        labels = parsed["labels"]
        text_l = (parsed["text"] or "").lower()
        list_channels = any("list channel" in (lab or "").lower() for lab in labels) or (
            "list channels" in text_l
        )
        post_like = any(
            "post" in (lab or "").lower() and "list" not in (lab or "").lower() for lab in labels
        ) or ("post" in text_l and "slack" in text_l)
        return {
            "sha": sha,
            "conversation_id": conversation_id,
            "marker": marker,
            "http": r.status_code,
            "elapsed_ms": elapsed_ms,
            "labels": labels,
            "text_head": (parsed["text"] or "")[:500],
            "list_channels_seen": list_channels,
            "post_like_seen": post_like,
            "pass": (not list_channels) and (post_like or "channel" in text_l or "approval" in text_l),
        }


def main() -> int:
    report: dict[str, Any] = {
        "ticket": "STA-305",
        "probed_at": utcnow(),
        "local_mapper": local_mapper_probe(),
    }
    if os.environ.get("STA305_LIVE", "").strip().lower() in {"1", "true", "yes"}:
        report["live"] = asyncio.run(live_chat_probe())
    else:
        report["live"] = {"skipped": True, "reason": "set STA305_LIVE=1 after deploy"}
    live = report.get("live") or {}
    report["verdict"] = (
        "PASS"
        if report["local_mapper"].get("pass")
        and (live.get("skipped") or live.get("pass"))
        else "FAIL"
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
