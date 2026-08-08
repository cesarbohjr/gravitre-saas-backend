"""Live proof: POST /api/billing/top-up/voice-minutes returns a Stripe Checkout URL."""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import jwt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

for candidate in [ROOT / "backend" / ".env.operator.local", ROOT / "backend" / ".env"]:
    if not candidate.exists():
        continue
    for line in candidate.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key and key not in os.environ:
            os.environ[key] = value

from supabase import create_client  # noqa: E402

from app.config import get_settings  # noqa: E402

ORG = "cbbf993b-b22f-41ce-964b-1fc25e0dd9ea"
UID = "f7e32f06-49df-4e73-8962-f41c21850762"
API = os.environ.get("API_PUBLIC_URL", "https://api.gravitre.app").rstrip("/")


def main() -> int:
    settings = get_settings()
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    users = client.auth.admin.get_user_by_id(UID)
    email = (users.user.email if users and users.user else None) or f"{UID}@gravitre.local"
    now = int(time.time())
    token = jwt.encode(
        {
            "sub": UID,
            "email": email,
            "aud": "authenticated",
            "iss": f"{settings.supabase_url.rstrip('/')}/auth/v1",
            "iat": now,
            "exp": now + 3600,
            "role": "authenticated",
        },
        settings.supabase_jwt_secret,
        algorithm="HS256",
    )
    if isinstance(token, bytes):
        token = token.decode()

    # Ensure voice org ON for top-up.
    client.table("subscriptions").update({"voice_enabled": True}).eq("org_id", ORG).execute()

    body = json.dumps({"minutes": 60}).encode("utf-8")
    req = urllib.request.Request(
        f"{API}/api/billing/top-up/voice-minutes",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "x-org-id": ORG,
            "content-type": "application/json",
            "accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
            ok = resp.status == 200 and bool(data.get("checkout_url")) and int(data.get("amount_cents") or 0) > 0
            print(
                json.dumps(
                    {
                        "ok": ok,
                        "http": resp.status,
                        "minutes": data.get("minutes"),
                        "amount_cents": data.get("amount_cents"),
                        "rate_cents_per_minute": data.get("rate_cents_per_minute"),
                        "has_checkout_url": bool(data.get("checkout_url")),
                        "session_id_prefix": str(data.get("session_id") or "")[:20],
                        "note": "Checkout session created — complete payment in Stripe to credit prepaid minutes",
                    },
                    indent=2,
                )
            )
            return 0 if ok else 1
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        print(json.dumps({"ok": False, "http": exc.code, "body": raw[:600]}, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
