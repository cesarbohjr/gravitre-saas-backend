#!/usr/bin/env python3
"""Live smoke: Pipecat voice WebSocket (text ingress) when VOICE_PIPECAT_ENABLED.

Proves (API-level):
  1. GET /api/voice/status reports pipecat_* fields
  2. With flag off: WS closes with not_enabled (or status says disabled)
  3. With flag on: session.ready + audio/transcript response to text ingress
  4. Existing /api/voice/session/turn path still reachable (health check only here)

Writes docs/delivery/voice-pipecat-phase1-live.json

Usage:
  python scripts/verify-voice-pipecat-phase1-live.py
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode, urlparse, urlunparse

import httpx
from dotenv import dotenv_values

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))

BASE = os.environ.get(
    "BACKEND_URL",
    "https://gravitre-saas-backend-production.up.railway.app",
).rstrip("/")
OUT = REPO / "docs" / "delivery" / "voice-pipecat-phase1-live.json"
ISOLATED_ORG = "f07e57c0-1501-4000-8000-c04e57a00001"
DEFAULT_ACTOR = "a9f1240f-910a-42ca-aebf-38caeac288c3"


def _load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for path in (BACKEND / ".env", BACKEND / ".env.operator.local", REPO / ".env"):
        if not path.is_file():
            continue
        try:
            merged.update({k: v for k, v in dotenv_values(path).items() if v})
        except UnicodeDecodeError:
            text = path.read_bytes().decode("utf-8", errors="ignore")
            for line in text.splitlines():
                if "=" not in line or line.lstrip().startswith("#"):
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and value:
                    merged[key] = value
    merged.update({k: v for k, v in os.environ.items() if v})
    return merged


def _health() -> dict:
    try:
        return httpx.get(f"{BASE}/health", timeout=60.0).json()
    except Exception as exc:  # noqa: BLE001
        return {"git_sha": None, "error": f"{exc.__class__.__name__}:{exc}"}


def _service_token(env: dict[str, str], org_id: str, actor_id: str) -> str | None:
    _ = org_id
    bearer = (env.get("OPERATOR_BEARER") or env.get("GRAVITRE_OPERATOR_BEARER") or "").strip()
    if bearer:
        return bearer if not bearer.lower().startswith("bearer ") else bearer.split(" ", 1)[1]
    url = (env.get("SUPABASE_URL") or "").rstrip("/")
    secret = (env.get("SUPABASE_JWT_SECRET") or "").strip()
    if not url or not secret:
        return None
    try:
        import jwt

        now = int(datetime.now(timezone.utc).timestamp())
        payload = {
            "sub": actor_id,
            "aud": "authenticated",
            "role": "authenticated",
            "iat": now,
            "exp": now + 3600,
            "email": "voice-pipecat-probe@gravitre.internal",
        }
        return jwt.encode(payload, secret, algorithm="HS256")
    except Exception:  # noqa: BLE001
        return None


def _ws_url(path: str, params: dict[str, str]) -> str:
    parsed = urlparse(BASE)
    scheme = "wss" if parsed.scheme == "https" else "ws"
    q = urlencode({k: v for k, v in params.items() if v})
    return urlunparse((scheme, parsed.netloc, path, "", q, ""))


async def _probe_ws(token: str, org_id: str, *, send_text: bool) -> dict:
    try:
        import websockets
    except ImportError:
        return {"ok": False, "error": "websockets package missing"}

    url = _ws_url(
        "/api/voice/pipecat/ws",
        {
            "access_token": token,
            "org_id": org_id,
            "conversation_id": str(uuid.uuid4()),
        },
    )
    events: list[dict] = []
    audio_frames = 0
    try:
        async with websockets.connect(url, open_timeout=30, close_timeout=10, max_size=8_000_000) as ws:
            deadline = asyncio.get_event_loop().time() + 90.0
            while asyncio.get_event_loop().time() < deadline:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=45.0)
                except asyncio.TimeoutError:
                    events.append({"type": "_timeout"})
                    break
                if isinstance(raw, bytes):
                    events.append({"type": "_binary", "bytes": len(raw)})
                    continue
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    events.append({"type": "_non_json", "preview": raw[:120]})
                    continue
                kind = str(msg.get("type") or "")
                if kind == "audio":
                    audio_frames += 1
                    if audio_frames <= 2:
                        events.append({"type": "audio", "sample_rate": msg.get("sample_rate")})
                else:
                    # Truncate large payloads
                    slim = {k: v for k, v in msg.items() if k != "pcm16_b64"}
                    if "error" in slim and isinstance(slim["error"], str):
                        slim["error"] = slim["error"][:300]
                    events.append(slim)
                if kind == "session.ready" and send_text:
                    await ws.send(
                        json.dumps(
                            {
                                "type": "text",
                                "text": "In one short sentence, what is two plus two?",
                            }
                        )
                    )
                if kind == "error":
                    break
                if audio_frames >= 3 or kind in {"transcript"} and audio_frames >= 1:
                    break
                # After ready+text, wait for audio; also accept early error
                if kind == "session.ready" and not send_text:
                    break
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "error": f"{exc.__class__.__name__}:{exc}",
            "events": events,
            "audio_frames": audio_frames,
        }

    err = next((e for e in events if e.get("type") == "error"), None)
    ready = next((e for e in events if e.get("type") == "session.ready"), None)
    return {
        "ok": True,
        "events": events[:40],
        "audio_frames": audio_frames,
        "session_ready": ready is not None,
        "error_event": err,
        "cognitive_path": (ready or {}).get("cognitive_path"),
        "architecture": (ready or {}).get("architecture"),
    }


def main() -> int:
    env = _load_env()
    org_id = (env.get("VOICE_PROBE_ORG_ID") or ISOLATED_ORG).strip()
    actor_id = (env.get("VOICE_PROBE_ACTOR_ID") or DEFAULT_ACTOR).strip()
    token = _service_token(env, org_id, actor_id)
    health = _health()

    status_probe: dict = {"ok": False}
    if token:
        try:
            r = httpx.get(
                f"{BASE}/api/voice/status",
                headers={"Authorization": f"Bearer {token}", "x-org-id": org_id},
                timeout=30.0,
            )
            body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
            status_probe = {
                "ok": r.status_code == 200,
                "http_status": r.status_code,
                "pipecat_enabled": body.get("pipecat_enabled"),
                "pipecat_available": body.get("pipecat_available"),
                "pipecat_ws_path": body.get("pipecat_ws_path"),
                "default_orchestration": body.get("default_orchestration"),
                "architecture": body.get("architecture"),
            }
        except Exception as exc:  # noqa: BLE001
            status_probe = {"ok": False, "error": f"{exc.__class__.__name__}:{exc}"}

    ws_probe: dict = {"ok": False, "skipped": True, "reason": "no_token"}
    if token:
        enabled = bool(status_probe.get("pipecat_enabled"))
        ws_probe = asyncio.run(_probe_ws(token, org_id, send_text=enabled))
        if enabled:
            ws_probe["verdict"] = (
                "PASS"
                if ws_probe.get("session_ready") and (ws_probe.get("audio_frames") or 0) > 0
                else "FAIL"
            )
        else:
            # Flag off: expect not_enabled error or no session.ready
            err = ws_probe.get("error_event") or {}
            not_enabled = (
                err.get("error_class") == "not_enabled"
                or "VOICE_PIPECAT_ENABLED" in str(err.get("error") or "")
            )
            ws_probe["verdict"] = "PASS" if not_enabled or not ws_probe.get("session_ready") else "INCONCLUSIVE"

    status_ok = bool(status_probe.get("ok")) and "pipecat_ws_path" in status_probe
    overall = "PASS" if status_ok and ws_probe.get("verdict") == "PASS" else "PARTIAL"
    if not status_ok:
        overall = "FAIL"

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "backend_url": BASE,
        "git_sha": health.get("git_sha"),
        "health": health,
        "status_probe": status_probe,
        "ws_probe": ws_probe,
        "verdict": overall,
        "notes": (
            "Default duplex remains /api/voice/session/turn. Pipecat path is flag-gated. "
            "Enable VOICE_PIPECAT_ENABLED on Railway to exercise session.ready + audio."
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"verdict": overall, "out": str(OUT), "git_sha": health.get("git_sha")}, indent=2))
    return 0 if overall == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
