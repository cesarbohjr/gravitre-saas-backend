#!/usr/bin/env python3
"""Live prove: QA-force 402 on /api/voice/tts (agent-chat voice pipeline).

Requires auth token + org. Does not charge ElevenLabs — synthetic QA error only.
Writes evidence JSON under docs/delivery/.
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

API = (os.environ.get("GRAVITRE_API_BASE") or "https://api.gravitre.app").rstrip("/")
TOKEN = (os.environ.get("GRAVITRE_ACCESS_TOKEN") or os.environ.get("SUPABASE_ACCESS_TOKEN") or "").strip()
ORG = (os.environ.get("GRAVITRE_ORG_ID") or "").strip()
OUT = Path(__file__).resolve().parents[1] / "docs" / "delivery" / "agent-chat-voice-402-qa-force.json"


def _req(method: str, path: str, *, body: dict | None = None, extra_headers: dict | None = None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {
        "authorization": f"Bearer {TOKEN}",
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
    if not TOKEN or not ORG:
        print("Set GRAVITRE_ACCESS_TOKEN and GRAVITRE_ORG_ID", file=sys.stderr)
        return 2

    health_code, health_body, _ = _req("GET", "/health")
    health = {}
    try:
        health = json.loads(health_body)
    except json.JSONDecodeError:
        pass

    # Control: without force header, should not be synthetic QA 402 (may still 402 if real).
    ctrl_code, ctrl_body, _ = _req(
        "POST",
        "/api/voice/tts",
        body={"text": "QA control ping — ignore.", "voice": "rachel"},
    )

    force_code, force_body, force_headers = _req(
        "POST",
        "/api/voice/tts",
        body={"text": "QA force billing — ignore.", "voice": "rachel"},
        extra_headers={"X-Gravitre-QA-Force-Voice-Error": "billing"},
    )
    force_json: dict = {}
    try:
        force_json = json.loads(force_body)
    except json.JSONDecodeError:
        force_json = {"raw": force_body[:800]}

    detail = force_json.get("detail") if isinstance(force_json, dict) else None
    if isinstance(detail, dict):
        error_class = detail.get("error_class")
        billing_issue = detail.get("billing_issue")
        detail_text = str(detail.get("detail") or "")
    else:
        error_class = force_json.get("error_class")
        billing_issue = force_json.get("billing_issue")
        detail_text = str(detail or force_json.get("raw") or "")

    hooks = bool(health.get("unified_turn_qa_hooks_enabled"))
    pass_force = (
        force_code == 402
        and error_class == "billing"
        and billing_issue is True
        and "billing" in detail_text.lower()
    )

    evidence = {
        "at": datetime.now(timezone.utc).isoformat(),
        "api": API,
        "org_id": ORG,
        "health_git_sha": health.get("git_sha"),
        "unified_turn_qa_hooks_enabled": hooks,
        "control_status": ctrl_code,
        "force_status": force_code,
        "force_error_class": error_class,
        "force_billing_issue": billing_issue,
        "force_detail_snippet": detail_text[:300],
        "force_x_voice_error_class": force_headers.get("X-Voice-Error-Class")
        or force_headers.get("x-voice-error-class"),
        "pass": pass_force,
        "ui_amber_path": (
            "Open agent chat with ?qaForceVoiceError=billing, switch to Voice, "
            "send a short message; presence strip should show amber "
            "'Voice paused — credits needed'. Remove query param / toggle Text to clear."
        ),
        "elapsed_ms": None,
    }
    started = time.perf_counter()
    evidence["elapsed_ms"] = int((time.perf_counter() - started) * 1000)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(json.dumps(evidence, indent=2))
    return 0 if pass_force else 1


if __name__ == "__main__":
    raise SystemExit(main())
