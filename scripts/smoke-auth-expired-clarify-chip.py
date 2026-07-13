#!/usr/bin/env python3
"""Live spotcheck: expired Slack clarify chip must be auth_expired, not tool_not_available."""
from __future__ import annotations

import json
import os
import re
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import jwt
from dotenv import dotenv_values
from httpx import Client

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
OUT = ROOT / "docs" / "delivery" / "auth-expired-clarify-live.json"
ORG = "cbbf993b-b22f-41ce-964b-1fc25e0dd9ea"
BASE = "https://gravitre-saas-backend-production.up.railway.app"
PROMPT = "send a message in slack general channel"


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


def main() -> int:
    load_env()
    sys.path.insert(0, str(BACKEND))
    from app.config import get_settings
    from app.workflows.repository import get_supabase_client

    settings = get_settings()
    client = get_supabase_client(settings)
    actor = os.environ.get("OAUTH_SMOKE_USER_ID") or "f7e32f06-49df-4e73-8962-f41c21850762"
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
    cid = str(uuid.uuid4())
    hdr = {
        "Authorization": f"Bearer {tok}",
        "X-Org-Id": ORG,
        "X-Environment": "production",
        "Accept": "text/event-stream",
        "Content-Type": "application/json",
    }
    body = {
        "messages": [{"role": "user", "parts": [{"type": "text", "text": PROMPT}]}],
        "org_id": ORG,
        "conversation_id": cid,
        "id": cid,
    }
    texts: list[str] = []
    codes: list[str] = []
    chips: list[dict] = []
    with Client(base_url=BASE, timeout=180.0, verify=False) as ac:
        sha = str((ac.get("/health").json() or {}).get("git_sha") or "")
        r = ac.post("/api/assistant/chat", headers=hdr, json=body)
        for block in re.split(r"\n\n+", r.text):
            lines = [ln[5:].lstrip() for ln in block.splitlines() if ln.startswith("data:")]
            if not lines:
                continue
            payload = "\n".join(lines).strip()
            if payload in ("", "[DONE]"):
                continue
            try:
                o = json.loads(payload)
            except json.JSONDecodeError:
                continue
            t = o.get("type")
            if t == "text-delta":
                texts.append(o.get("delta") or "")
            out = o.get("output") if isinstance(o.get("output"), dict) else None
            code = None
            if out and out.get("errorCode"):
                code = str(out.get("errorCode"))
            elif o.get("errorCode"):
                code = str(o.get("errorCode"))
            if code:
                codes.append(code)
                chips.append(
                    {
                        "type": t,
                        "errorCode": code,
                        "error": (out or {}).get("error") or o.get("error") or "",
                        "toolName": o.get("toolName"),
                    }
                )

    text = "".join(texts)
    passed = (
        r.status_code == 200
        and "auth_expired" in codes
        and "tool_not_available" not in codes
        and ("expired" in text.lower() or "reconnect" in text.lower())
    )
    report = {
        "probe": "auth_expired_clarify_chip",
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "prod_sha": sha,
        "conversation_id": cid,
        "http": r.status_code,
        "text": text[:500],
        "error_codes": codes,
        "chips": chips[:8],
        "pass": passed,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print("WROTE", OUT)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
