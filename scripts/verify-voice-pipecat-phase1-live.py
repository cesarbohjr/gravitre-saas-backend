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
        import time

        import jwt

        now = int(time.time())
        return jwt.encode(
            {
                "sub": actor_id,
                "email": "voice-pipecat-probe@gravitre.internal",
                "aud": "authenticated",
                "iss": f"{url}/auth/v1",
                "iat": now,
                "exp": now + 3600,
                "role": "authenticated",
            },
            secret,
            algorithm="HS256",
        )
    except Exception:  # noqa: BLE001
        return None


def _ws_url(path: str, params: dict[str, str]) -> str:
    parsed = urlparse(BASE)
    scheme = "wss" if parsed.scheme == "https" else "ws"
    q = urlencode({k: v for k, v in params.items() if v})
    return urlunparse((scheme, parsed.netloc, path, "", q, ""))


async def _probe_ws(
    token: str,
    org_id: str,
    *,
    send_text: bool,
    text: str = "In one short sentence, what is two plus two?",
    wait_for_assistant_text: bool = False,
) -> dict:
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
        import ssl

        try:
            import certifi

            ssl_ctx: ssl.SSLContext | bool = ssl.create_default_context(cafile=certifi.where())
        except Exception:  # noqa: BLE001
            ssl_ctx = True
        # Local Windows Python sometimes has a stale system CA store; fall back once.
        try:
            ws_cm = websockets.connect(
                url,
                open_timeout=30,
                close_timeout=10,
                max_size=8_000_000,
                ssl=ssl_ctx,
            )
            ws = await ws_cm.__aenter__()
        except ssl.SSLCertVerificationError:
            insecure = ssl._create_unverified_context()  # noqa: S323 — probe-only fallback
            ws_cm = websockets.connect(
                url,
                open_timeout=30,
                close_timeout=10,
                max_size=8_000_000,
                ssl=insecure,
            )
            ws = await ws_cm.__aenter__()
        try:
            deadline = asyncio.get_event_loop().time() + (120.0 if send_text else 45.0)
            while asyncio.get_event_loop().time() < deadline:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=90.0 if send_text else 30.0)
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
                    # Brief settle so StartFrame / aggregators are live.
                    await asyncio.sleep(0.35)
                    await ws.send(
                        json.dumps(
                            {
                                "type": "text",
                                "text": text,
                            }
                        )
                    )
                if kind == "assistant_text":
                    delta = str(msg.get("delta") or "")
                    if delta:
                        events.append({"type": "assistant_text", "delta": delta[:200]})
                if kind == "error":
                    break
                if audio_frames >= 1 and (
                    not wait_for_assistant_text
                    or any(e.get("type") == "assistant_text" for e in events)
                ):
                    break
                if kind == "session.ready" and not send_text:
                    break
        finally:
            await ws_cm.__aexit__(None, None, None)
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "error": f"{exc.__class__.__name__}:{exc}",
            "events": events,
            "audio_frames": audio_frames,
        }

    err = next((e for e in events if e.get("type") == "error"), None)
    ready = next((e for e in events if e.get("type") == "session.ready"), None)
    assistant_bits = [
        str(e.get("delta") or "") for e in events if e.get("type") == "assistant_text"
    ]
    assistant_text = "".join(assistant_bits).strip()
    return {
        "ok": True,
        "events": events[:40],
        "audio_frames": audio_frames,
        "session_ready": ready is not None,
        "error_event": err,
        "cognitive_path": (ready or {}).get("cognitive_path"),
        "architecture": (ready or {}).get("architecture"),
        "write_confirm_policy": (ready or {}).get("write_confirm_policy"),
        "assistant_text": assistant_text[:800],
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
    governance_probe: dict = {"ok": False, "skipped": True}
    if token:
        enabled = bool(status_probe.get("pipecat_enabled"))
        ws_probe = asyncio.run(_probe_ws(token, org_id, send_text=enabled))
        if enabled:
            ws_probe["verdict"] = (
                "PASS"
                if ws_probe.get("ok")
                and ws_probe.get("session_ready")
                and (ws_probe.get("audio_frames") or 0) > 0
                else "FAIL"
            )
            # Separate connection: consequential write-shaped turn — must stay on
            # CognitiveTurnKernel + nl_yes confirm policy (no voice bypass).
            governance_probe = asyncio.run(
                _probe_ws(
                    token,
                    org_id,
                    send_text=True,
                    text="Email Sarah that the campaign moved to Monday.",
                    wait_for_assistant_text=True,
                )
            )
            spoken = (governance_probe.get("assistant_text") or "").lower()
            confirmish = any(
                needle in spoken
                for needle in (
                    "confirm",
                    "shall i",
                    "should i",
                    "want me to",
                    "before i",
                    "draft",
                    "send",
                    "yes",
                )
            )
            governance_probe["confirm_language_detected"] = confirmish
            governance_probe["verdict"] = (
                "PASS"
                if governance_probe.get("ok")
                and governance_probe.get("session_ready")
                and governance_probe.get("cognitive_path") == "CognitiveTurnKernel"
                and governance_probe.get("write_confirm_policy") == "nl_yes_same_path_as_text"
                and (governance_probe.get("audio_frames") or 0) > 0
                else "FAIL"
            )
        else:
            # Flag off: require an explicit not_enabled error from a successful WS handshake.
            err = ws_probe.get("error_event") or {}
            not_enabled = (
                ws_probe.get("ok")
                and (
                    err.get("error_class") == "not_enabled"
                    or "VOICE_PIPECAT_ENABLED" in str(err.get("error") or "")
                )
                and not ws_probe.get("session_ready")
            )
            ws_probe["verdict"] = "PASS" if not_enabled else "FAIL"
            governance_probe = {"ok": True, "skipped": True, "verdict": "PASS", "reason": "flag_off"}

    status_ok = bool(status_probe.get("ok")) and "pipecat_ws_path" in status_probe
    # Honesty: when the flag is on, status must advertise pipecat as default orchestration
    # (FE also keys off pipecat_enabled; this field must not lie as http_session_turn).
    if status_ok and status_probe.get("pipecat_enabled"):
        status_ok = status_probe.get("default_orchestration") == "pipecat"
        status_probe["orchestration_honesty"] = (
            "PASS" if status_ok else "FAIL"
        )
    elif status_ok and status_probe.get("pipecat_enabled") is False:
        status_probe["orchestration_honesty"] = (
            "PASS"
            if status_probe.get("default_orchestration") == "http_session_turn"
            else "FAIL"
        )
        if status_probe["orchestration_honesty"] == "FAIL":
            status_ok = False
    gov_ok = governance_probe.get("verdict") == "PASS"
    overall = (
        "PASS"
        if status_ok and ws_probe.get("verdict") == "PASS" and gov_ok
        else "PARTIAL"
    )
    if not status_ok:
        overall = "FAIL"

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "backend_url": BASE,
        "git_sha": health.get("git_sha"),
        "health": health,
        "status_probe": status_probe,
        "ws_probe": ws_probe,
        "governance_probe": governance_probe,
        "verdict": overall,
        "notes": (
            "FE duplex uses Pipecat WS when VOICE_PIPECAT_ENABLED; HTTP session/turn is fallback. "
            "Governance probe: write-shaped text ingress must advertise CognitiveTurnKernel + "
            "nl_yes_same_path_as_text and produce audio (no silent voice bypass)."
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"verdict": overall, "out": str(OUT), "git_sha": health.get("git_sha")}, indent=2))
    return 0 if overall == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
