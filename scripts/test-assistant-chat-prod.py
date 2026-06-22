"""One-off prod assistant chat probe."""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path

import jwt
from dotenv import dotenv_values
from supabase import create_client

REPO = Path(__file__).resolve().parent.parent
merged: dict[str, str] = {}
for path in (REPO / "backend" / ".env", REPO / "backend" / ".env.operator.local"):
    if path.is_file():
        merged.update({k: v for k, v in dotenv_values(path).items() if v})

url = merged["SUPABASE_URL"]
key = merged["SUPABASE_SERVICE_ROLE_KEY"]
secret = merged["SUPABASE_JWT_SECRET"]
client = create_client(url, key)

members = (
    client.table("organization_members")
    .select("org_id,user_id,role")
    .eq("role", "owner")
    .limit(1)
    .execute()
)
if not members.data:
    members = client.table("organization_members").select("org_id,user_id,role").limit(1).execute()
row = members.data[0]
org_id = str(row["org_id"])
user_id = str(row["user_id"])
users = client.auth.admin.get_user_by_id(user_id)
email = users.user.email or f"{user_id}@gravitre.local"

now = int(time.time())
token = jwt.encode(
    {
        "sub": user_id,
        "email": email,
        "aud": "authenticated",
        "iss": f"{url.rstrip('/')}/auth/v1",
        "iat": now,
        "exp": now + 3600,
        "role": "authenticated",
    },
    secret,
    algorithm="HS256",
)

payload = {
    "messages": [{"role": "user", "parts": [{"type": "text", "text": "Say ok in one word."}]}],
    "org_id": org_id,
    "tools": ["knowledge_base", "agent_status", "connector_status"],
    "mode": "reasoning",
}

api_base = "https://api.gravitre.app"
for label, target in [
    ("railway_direct", f"{api_base}/api/assistant/chat?environment=production"),
    ("gravitre_proxy", "https://gravitre.app/api/chat?org_id=" + org_id),
]:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(target, data=body, method="POST")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("X-Org-Id", org_id)
    req.add_header("X-Environment", "production")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "text/event-stream")
    print(f"\n=== {label} ===")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            text = resp.read(800).decode("utf-8", errors="replace")
            print("status:", resp.status)
            print("body_prefix:", text[:400])
    except urllib.error.HTTPError as exc:
        print("status:", exc.code)
        print("body:", exc.read().decode("utf-8", errors="replace")[:800])
