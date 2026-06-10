"""Debug assistant chat flow locally with prod env."""
from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path

import jwt
from dotenv import dotenv_values
from httpx import ASGITransport, AsyncClient
from supabase import create_client

import sys

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))
merged: dict[str, str] = {}
for path in (REPO / "backend" / ".env", REPO / "backend" / ".env.operator.local"):
    if path.is_file():
        merged.update({k: v for k, v in dotenv_values(path).items() if v})

for k, v in merged.items():
    os.environ.setdefault(k, v)

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

from app.main import app  # noqa: E402


async def main() -> None:
    body = {
        "messages": [{"role": "user", "parts": [{"type": "text", "text": "Say ok in one word."}]}],
        "org_id": org_id,
        "tools": ["knowledge_base", "agent_status", "connector_status"],
        "mode": "reasoning",
    }
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post(
            "/api/assistant/chat",
            json=body,
            headers={
                "Authorization": f"Bearer {token}",
                "X-Org-Id": org_id,
                "X-Environment": "production",
            },
        )
        print("status:", r.status_code)
        print("body:", r.text[:1200])


if __name__ == "__main__":
    asyncio.run(main())
