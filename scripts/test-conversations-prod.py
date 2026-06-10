"""Probe conversations create on production."""
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
row = (
    client.table("organization_members")
    .select("org_id,user_id,role")
    .eq("role", "owner")
    .limit(1)
    .execute()
    .data[0]
)
org_id = str(row["org_id"])
user_id = str(row["user_id"])
email = client.auth.admin.get_user_by_id(user_id).user.email
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

for label, target in [
    ("railway", "https://gravitre-saas-backend-production.up.railway.app/api/conversations"),
    ("proxy", "https://gravitre.app/api/conversations"),
]:
    body = json.dumps({"title": "hello"}).encode("utf-8")
    req = urllib.request.Request(target, data=body, method="POST")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("X-Org-Id", org_id)
    req.add_header("Content-Type", "application/json")
    print(f"\n=== {label} ===")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            print("status:", resp.status)
            print(resp.read().decode()[:500])
    except urllib.error.HTTPError as exc:
        print("status:", exc.code)
        print(exc.read().decode()[:800])
