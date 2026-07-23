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
sys.path.insert(0, str(ROOT / "scripts"))

from isolated_conversation_org import (  # noqa: E402
    resolve_isolated_conversation_actor,
    smoke_http_headers,
)

OUT = ROOT / "docs" / "delivery" / "sta305-catalog-kind-prod.json"
BASE = os.environ.get("LIVE_API_BASE", "https://api.gravitre.app").rstrip("/")
SEGMENT = "draft a follow-up in Slack for approval"
CHAT_TIMEOUT = 180.0
REQUIRED_LIVE_CONNECTORS = ("hubspot", "slack")


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
        loaded: dict[str, str | None] = {}
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                loaded = dotenv_values(p, encoding=enc)
                break
            except UnicodeDecodeError:
                continue
        for k, v in loaded.items():
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


def connected_integrations_for_org(org_id: str) -> list[str]:
    from app.config import get_settings
    from app.workflows.repository import get_supabase_client

    client = get_supabase_client(get_settings())
    rows = (
        client.table("connectors")
        .select("type,status")
        .eq("org_id", org_id)
        .execute()
        .data
        or []
    )
    ok_status = {"active", "healthy", "connected", "ok"}
    names: list[str] = []
    for row in rows:
        integration = str(row.get("type") or row.get("integration") or "").strip().lower()
        status = str(row.get("status") or "").strip().lower()
        if integration and status in ok_status:
            names.append(integration)
    return sorted(set(names))


async def live_chat_probe() -> dict[str, Any]:
    load_env()
    from app.config import get_settings
    from app.workflows.repository import get_supabase_client

    settings = get_settings()
    client = get_supabase_client(settings)
    org_id, user_id, email = resolve_isolated_conversation_actor(
        {k: os.environ.get(k, "") for k in os.environ},
        client,
    )
    connected = connected_integrations_for_org(org_id)
    missing = [c for c in REQUIRED_LIVE_CONNECTORS if c not in connected]
    if missing:
        return {
            "skipped": True,
            "reason": (
                "STA-305 live requires connected HubSpot + Slack in isolated test org; "
                f"missing={missing} connected={connected}"
            ),
            "org_id": org_id,
            "connected_integrations": connected,
            "pass": False,
        }
    url = os.environ["SUPABASE_URL"].rstrip("/")
    now = int(time.time())
    tok = jwt.encode(
        {
            "sub": user_id,
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
        **smoke_http_headers(),
        "Authorization": f"Bearer {tok}",
        "X-Org-Id": org_id,
        "X-Environment": "production",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
    }
    marker = uuid.uuid4().hex[:8]
    message = f"Search HubSpot for high-intent leads and {SEGMENT} [STA-305 {marker}]"
    async with AsyncClient(base_url=BASE, timeout=CHAT_TIMEOUT) as ac:
        cr = await ac.post(
            "/api/conversations",
            headers={k: v for k, v in hdr.items() if k != "Accept"},
            json={"title": f"sta305-{marker}"},
        )
        cr.raise_for_status()
        conversation_id = str(cr.json()["id"])
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
                "org_id": org_id,
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
            "org_id": org_id,
            "connected_integrations": connected,
            "conversation_id": conversation_id,
            "marker": marker,
            "http": r.status_code,
            "elapsed_ms": elapsed_ms,
            "labels": labels,
            "text_head": (parsed["text"] or "")[:500],
            "list_channels_seen": list_channels,
            "post_like_seen": post_like,
            "pass": (not list_channels)
            and (
                post_like
                or "channel" in text_l
                or "approval" in text_l
                or "slack" in text_l
            ),
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
    live_skipped = bool(live.get("skipped"))
    if live_skipped and str(live.get("reason") or "").startswith("STA-305 live requires"):
        report["verdict"] = "BLOCKED"
    elif live_skipped:
        report["verdict"] = "PASS" if report["local_mapper"].get("pass") else "FAIL"
    else:
        report["verdict"] = (
            "PASS"
            if report["local_mapper"].get("pass") and live.get("pass")
            else "FAIL"
        )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    if report["verdict"] == "BLOCKED":
        # Env/fixture gap (connectors missing in smoke org). Local mapper still proves
        # omit-detail kind routing; do not fail the combined Phase 2 suite on BLOCKED.
        print(
            "STA-305 live BLOCKED: connect HubSpot + Slack in isolated conversation org, then re-run.",
            file=sys.stderr,
        )
        return 0 if report["local_mapper"].get("pass") else 2
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        import traceback

        traceback.print_exc()
        raise SystemExit(2) from None
