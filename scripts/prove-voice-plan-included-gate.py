"""Live proof: voice is plan-included (org ON/OFF), not Meson voice_interface purchase.

Checks:
1) /api/voice/status allowed with voice_enabled=true even if voice_interface absent from meson_addons
2) /api/voice/status 403 with reason voice_org_disabled when voice_enabled=false
3) meson-addons response does not list voice_interface as a priced Enable card
"""
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


def _token() -> str:
    settings = get_settings()
    secret = settings.supabase_jwt_secret
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
        secret,
        algorithm="HS256",
    )
    if isinstance(token, bytes):
        token = token.decode()
    return token


def _call(path: str, token: str, method: str = "GET", body: dict | None = None) -> tuple[int, dict]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        f"{API}{path}",
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "x-org-id": ORG,
            "content-type": "application/json",
            "accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            payload = {"raw": raw}
        return exc.code, payload


def main() -> int:
    settings = get_settings()
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    token = _token()

    # Snapshot prior voice flags
    prior = (
        client.table("subscriptions")
        .select("voice_enabled, meson_addons")
        .eq("org_id", ORG)
        .limit(1)
        .execute()
        .data
        or [{}]
    )[0]
    prior_enabled = prior.get("voice_enabled")
    prior_addons = list(prior.get("meson_addons") or [])

    try:
        # Ensure no fake purchase gate leftover.
        cleaned = [a for a in prior_addons if str(a) != "voice_interface"]
        client.table("subscriptions").update(
            {"voice_enabled": True, "meson_addons": cleaned}
        ).eq("org_id", ORG).execute()

        code_on, body_on = _call("/api/voice/status", token)
        code_addons, body_addons = _call("/api/settings/meson-addons", token)

        client.table("subscriptions").update({"voice_enabled": False}).eq("org_id", ORG).execute()
        code_off, body_off = _call("/api/voice/status", token)

        addon_codes = [str(a.get("code")) for a in (body_addons.get("addons") or [])]
        voice_card = body_addons.get("voice") or {}
        detail = body_off.get("detail") if isinstance(body_off.get("detail"), dict) else {}
        reason = str(detail.get("reason") or "")

        ok = (
            code_on == 200
            and code_off == 403
            and reason == "voice_org_disabled"
            and "voice_interface" not in addon_codes
            and voice_card.get("plan_included") is True
        )

        print(
            json.dumps(
                {
                    "ok": ok,
                    "voice_status_on": {"http": code_on, "keys": sorted(list(body_on.keys()))[:8]},
                    "voice_status_off": {"http": code_off, "reason": reason},
                    "meson_addon_codes": addon_codes,
                    "voice_card": {
                        "plan_included": voice_card.get("plan_included"),
                        "enabled": voice_card.get("enabled"),
                        "note": (voice_card.get("note") or "")[:120],
                    },
                    "api": API,
                },
                indent=2,
            )
        )
        return 0 if ok else 1
    finally:
        restore = {"voice_enabled": True if prior_enabled is None else bool(prior_enabled)}
        if prior_addons is not None:
            restore["meson_addons"] = prior_addons
        client.table("subscriptions").update(restore).eq("org_id", ORG).execute()


if __name__ == "__main__":
    raise SystemExit(main())
