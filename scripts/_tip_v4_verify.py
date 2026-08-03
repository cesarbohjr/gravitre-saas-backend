#!/usr/bin/env python3
"""Tip verify: POST /api/extension/chat on deployed backend."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import httpx
import jwt
from dotenv import dotenv_values

BACKEND = Path(__file__).resolve().parent.parent / "backend"
merged: dict[str, str] = {}
for p in (BACKEND / ".env", BACKEND / ".env.operator.local"):
    if not p.is_file():
        continue
    for enc in ("utf-8", "utf-8-sig", "cp1252"):
        try:
            d = dotenv_values(p, encoding=enc)
            break
        except UnicodeDecodeError:
            continue
    merged.update({k: v for k, v in d.items() if v})
for k, v in merged.items():
    os.environ.setdefault(k, v)

BASE = "https://gravitre-saas-backend-production.up.railway.app"
ORG = "cbbf993b-b22f-41ce-964b-1fc25e0dd9ea"
ACTOR = "f7e32f06-49df-4e73-8962-f41c21850762"
EXPECTED = os.environ.get("EXPECTED_GIT_SHA_PREFIX", "").strip()

url = os.environ["SUPABASE_URL"].rstrip("/")
now = int(time.time())
token = jwt.encode(
    {
        "sub": ACTOR,
        "email": "smoke@gravitre.app",
        "aud": "authenticated",
        "iss": f"{url}/auth/v1",
        "iat": now,
        "exp": now + 3600,
        "role": "authenticated",
    },
    os.environ["SUPABASE_JWT_SECRET"],
    algorithm="HS256",
)
h = {
    "Authorization": f"Bearer {token}",
    "X-Org-Id": ORG,
    "X-Environment": "production",
    "Content-Type": "application/json",
}
health = httpx.get(f"{BASE}/health", timeout=30).json()
sha = str(health.get("git_sha", ""))
print("health git_sha", sha)
if EXPECTED:
    assert sha.startswith(EXPECTED), health

page_context = {
    "fullName": "Casey Operator",
    "company": "Gravitree Smoke Co",
    "title": "Head of Revenue Ops",
    "source": "linkedin",
}
quick = httpx.post(
    f"{BASE}/api/extension/chat",
    headers=h,
    json={
        "message": (
            "Using only the overlay page context, answer in one sentence: "
            "what is this person's full name, title, and company?"
        ),
        "pageUrl": "https://www.linkedin.com/in/extension-v4-smoke-profile",
        "pageContext": page_context,
    },
    timeout=180,
)
print("quick", quick.status_code)
qj = quick.json()
print(json.dumps(qj, indent=2)[:1500])
assert quick.status_code == 200 and qj.get("answer"), qj
ans = (qj.get("answer") or "").lower()
assert ("casey" in ans) or ("gravitree smoke" in ans) or ("revenue" in ans), qj
assert qj.get("path") in {
    "execute_task_streaming",
    "execute_task_streaming+page_context_answer",
}, qj
assert qj.get("needsHandoff") is False, qj

handoff = httpx.post(
    f"{BASE}/api/extension/chat",
    headers=h,
    json={
        "message": "Create a HubSpot list for Casey Operator from this page.",
        "pageUrl": "https://www.linkedin.com/in/extension-v4-smoke-profile",
        "pageContext": page_context,
        "conversationId": qj.get("conversationId"),
    },
    timeout=180,
)
print("handoff", handoff.status_code)
hj = handoff.json()
print(json.dumps(hj, indent=2)[:1500])
assert handoff.status_code == 200, hj
assert hj.get("needsHandoff") is True, hj
assert "/ai?c=" in str(hj.get("openInGravitreeUrl") or ""), hj

out = {
    "overall": "PASS",
    "git_sha": sha,
    "quickConversationId": qj.get("conversationId"),
    "handoffConversationId": hj.get("conversationId"),
    "handoffReason": hj.get("handoffReason"),
    "openInGravitreeUrl": hj.get("openInGravitreeUrl"),
    "quickAnswerPreview": (qj.get("answer") or "")[:300],
}
Path("docs/delivery/browser-extension-v4-tip-verify.json").write_text(
    json.dumps(out, indent=2), encoding="utf-8"
)
print(json.dumps(out, indent=2))
