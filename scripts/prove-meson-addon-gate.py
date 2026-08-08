"""C1 live proof: /api/voice blocked without voice_interface addon, allowed with it."""
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
from app.middleware.entitlements import resolve_entitlements  # noqa: E402

ORG = "cbbf993b-b22f-41ce-964b-1fc25e0dd9ea"
UID = "f7e32f06-49df-4e73-8962-f41c21850762"
API = "https://api.gravitre.app"


def _call(token: str) -> tuple[int, str]:
    req = urllib.request.Request(
        f"{API}/api/voice/status",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Org-Id": ORG,
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")[:240]
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")[:240]


def main() -> int:
    settings = get_settings()
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    before = list(
        (
            client.table("subscriptions")
            .select("meson_addons")
            .eq("org_id", ORG)
            .limit(1)
            .execute()
            .data
            or [{}]
        )[0].get("meson_addons")
        or []
    )
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

    # Ensure clean start without addon
    client.table("subscriptions").update({"meson_addons": []}).eq("org_id", ORG).execute()
    ent0 = resolve_entitlements(settings, ORG)
    code0, body0 = _call(token)

    client.table("subscriptions").update({"meson_addons": ["voice_interface"]}).eq("org_id", ORG).execute()
    ent1 = resolve_entitlements(settings, ORG)
    code1, body1 = _call(token)

    client.table("subscriptions").update({"meson_addons": before}).eq("org_id", ORG).execute()
    code2, _ = _call(token)

    ok = code0 == 403 and code1 == 200 and code2 == 403 and "voice_interface" in (ent1.get("addons") or [])
    print(
        json.dumps(
            {
                "without_addon": {"http": code0, "addons": ent0.get("addons"), "body": body0},
                "with_addon": {"http": code1, "addons": ent1.get("addons"), "body": body1},
                "restored_block": {"http": code2, "restored_addons": before},
                "pass": ok,
            },
            indent=2,
        )
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
