#!/usr/bin/env python3
"""Live prove: QA-force 402 on /api/voice/tts (agent-chat voice pipeline).

Mints a JWT like other voice proves. Does not charge ElevenLabs — synthetic QA
error only. Writes docs/delivery/agent-chat-voice-402-qa-force.json.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
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

ORG = os.environ.get("GRAVITRE_ORG_ID") or "cbbf993b-b22f-41ce-964b-1fc25e0dd9ea"
UID = os.environ.get("GRAVITRE_USER_ID") or "f7e32f06-49df-4e73-8962-f41c21850762"
API = (os.environ.get("GRAVITRE_API_BASE") or os.environ.get("API_PUBLIC_URL") or "https://api.gravitre.app").rstrip("/")
OUT = ROOT / "docs" / "delivery" / "agent-chat-voice-402-qa-force.json"


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


def _req(method: str, path: str, *, body: dict | None = None, extra_headers: dict | None = None, token: str):
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {
        "authorization": f"Bearer {token}",
        "x-org-id": ORG,
        "accept": "application/json",
        "content-type": "application/json",
    }
    if extra_headers:
        headers.update(extra_headers)
    req = urllib.request.Request(f"{API}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            return resp.getcode(), resp.read().decode("utf-8", errors="replace"), dict(resp.headers)
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace"), dict(exc.headers)


def main() -> int:
    token = _token()
    health_code, health_body, _ = _req("GET", "/health", token=token)
    health = {}
    try:
        health = json.loads(health_body)
    except json.JSONDecodeError:
        pass

    ctrl_code, ctrl_body, _ = _req(
        "POST",
        "/api/voice/tts",
        body={"text": "QA control ping — ignore.", "voice": "rachel"},
        token=token,
    )

    force_code, force_body, _ = _req(
        "POST",
        "/api/voice/tts",
        body={"text": "QA force billing — ignore.", "voice": "rachel"},
        extra_headers={"X-Gravitre-QA-Force-Voice-Error": "billing"},
        token=token,
    )
    force_json: dict = {}
    try:
        force_json = json.loads(force_body)
    except json.JSONDecodeError:
        force_json = {"raw": force_body[:800]}

    # Live envelope (http_exception_handler):
    # { success:false, error, details:{error_class,billing_issue}, detail:{message,…} }
    details = force_json.get("details") if isinstance(force_json, dict) else None
    detail = force_json.get("detail") if isinstance(force_json, dict) else None
    error_class = None
    billing_issue = None
    detail_text = ""
    if isinstance(details, dict):
        error_class = details.get("error_class")
        billing_issue = details.get("billing_issue")
    if isinstance(detail, dict):
        error_class = error_class or detail.get("error_class")
        billing_issue = billing_issue if billing_issue is not None else detail.get("billing_issue")
        detail_text = str(detail.get("message") or detail.get("detail") or "")
    if not detail_text and isinstance(force_json, dict):
        detail_text = str(force_json.get("error") or force_json.get("raw") or "")

    hooks = bool(health.get("unified_turn_qa_hooks_enabled"))
    tip = str(health.get("git_sha") or "")
    expected_tip = (os.environ.get("EXPECTED_GIT_SHA") or "").strip()
    tip_ok = (not expected_tip) or tip.startswith(expected_tip)
    # Require qa_force marker so a natural ElevenLabs 402 alone is not counted as QA-force proof.
    pass_force = (
        force_code == 402
        and error_class == "billing"
        and billing_issue is True
        and "qa_force_voice_error=billing" in detail_text.lower()
    )

    evidence = {
        "at": datetime.now(timezone.utc).isoformat(),
        "api": API,
        "org_id": ORG,
        "health_status": health_code,
        "health_git_sha": tip,
        "expected_git_sha": expected_tip or None,
        "tip_matches_expected": tip_ok,
        "unified_turn_qa_hooks_enabled": hooks,
        "control_status": ctrl_code,
        "control_body_snippet": ctrl_body[:200],
        "force_status": force_code,
        "force_error_class": error_class,
        "force_billing_issue": billing_issue,
        "force_detail_snippet": detail_text[:300],
        "pass": pass_force and tip_ok,
        "ui_amber_path": (
            "Open agent chat with ?qaForceVoiceError=billing, switch to Voice, "
            "send a short message; presence strip should show amber "
            "'Voice paused — credits needed'. Remove query param / toggle Text to clear."
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(json.dumps(evidence, indent=2))
    return 0 if evidence["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
