"""Shared machinery for driving a real production voice turn.

Extracted from ``measure-voice-narration-dead-air.py`` so the latency harness and
the dead-air probe drive turns identically instead of drifting.

Honesty label: real ElevenLabs-synthesized speech into the real deployed
``/api/voice/pipecat/ws``. NOT a human at a browser mic.

Credentials from the environment only: SUPABASE_URL, SUPABASE_JWT_SECRET,
ELEVENLABS_API_KEY.
"""
from __future__ import annotations

import asyncio
import base64
import json
import os
import ssl
import sys
import time
import uuid
from pathlib import Path
from urllib.parse import urlencode, urlparse, urlunparse

REPO = Path(__file__).resolve().parent.parent
if str(REPO / "backend") not in sys.path:
    sys.path.insert(0, str(REPO / "backend"))

BASE = os.environ.get("BACKEND_URL", "https://api.gravitre.app").rstrip("/")
ISOLATED_ORG = "f07e57c0-1501-4000-8000-c04e57a00001"
DEFAULT_ACTOR = "a9f1240f-910a-42ca-aebf-38caeac288c3"

SAMPLE_RATE = 16000
CHUNK_MS = 20
CHUNK_BYTES = int(SAMPLE_RATE * 2 * (CHUNK_MS / 1000))
TRAILING_SILENCE_S = 1.3

# Narration phrasing comes from voice_tool_narration; anything matching these
# openers is mechanics rather than answer content.
NARRATION_PREFIXES = ("let me check", "found ", "i'm ", "done", "one moment")


def service_token(actor_id: str = DEFAULT_ACTOR) -> str:
    url = (os.environ.get("SUPABASE_URL") or "").rstrip("/")
    secret = (os.environ.get("SUPABASE_JWT_SECRET") or "").strip()
    if not url or not secret:
        raise SystemExit("SUPABASE_URL and SUPABASE_JWT_SECRET required")
    import jwt

    now = int(time.time())
    return jwt.encode(
        {
            "sub": actor_id,
            "email": "voice-latency-probe@gravitre.internal",
            "aud": "authenticated",
            "iss": f"{url}/auth/v1",
            "iat": now,
            "exp": now + 3600,
            "role": "authenticated",
        },
        secret,
        algorithm="HS256",
    )


def ws_url(path: str, params: dict[str, str]) -> str:
    parsed = urlparse(BASE)
    scheme = "wss" if parsed.scheme == "https" else "ws"
    return urlunparse((scheme, parsed.netloc, path, "", urlencode(params), ""))


def synthesize(text: str) -> bytes:
    from app.config import get_settings
    from app.services.tier1_voice_service import synthesize_speech_stream

    return b"".join(
        synthesize_speech_stream(get_settings(), text=text, output_format="pcm_16000")
    )


def is_narration(text: str) -> bool:
    return text.strip().lower().startswith(NARRATION_PREFIXES)


def _ssl_context() -> ssl.SSLContext | bool:
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:  # noqa: BLE001
        return True


async def drive_turn(token: str, speech: bytes, *, deadline_s: float = 90.0) -> dict:
    """Speak ``speech`` into a fresh session and timestamp every text delta.

    Returns ``{"ok": False}`` when no deltas arrive, so callers can drop failed
    runs rather than average them into a percentile.
    """
    import websockets

    url = ws_url(
        "/api/voice/pipecat/ws",
        {
            "access_token": token,
            "org_id": ISOLATED_ORG,
            "conversation_id": str(uuid.uuid4()),
        },
    )

    events: list[dict] = []
    t_speech_end: float | None = None

    async with websockets.connect(
        url, open_timeout=30, close_timeout=10, max_size=8_000_000, ssl=_ssl_context()
    ) as ws:

        async def _send() -> None:
            nonlocal t_speech_end
            for i in range(0, len(speech), CHUNK_BYTES):
                await ws.send(
                    json.dumps(
                        {
                            "type": "audio",
                            "pcm16_b64": base64.b64encode(
                                speech[i : i + CHUNK_BYTES]
                            ).decode("ascii"),
                            "sample_rate": SAMPLE_RATE,
                            "num_channels": 1,
                        }
                    )
                )
                await asyncio.sleep(CHUNK_MS / 1000)
            t_speech_end = time.monotonic()
            silence = base64.b64encode(b"\x00" * CHUNK_BYTES).decode("ascii")
            for _ in range(int((TRAILING_SILENCE_S * 1000) / CHUNK_MS)):
                await ws.send(
                    json.dumps(
                        {
                            "type": "audio",
                            "pcm16_b64": silence,
                            "sample_rate": SAMPLE_RATE,
                            "num_channels": 1,
                        }
                    )
                )
                await asyncio.sleep(CHUNK_MS / 1000)

        send_task: asyncio.Task | None = None
        last_text_at: float | None = None
        deadline = time.monotonic() + deadline_s
        while time.monotonic() < deadline:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=20.0)
            except asyncio.TimeoutError:
                break
            except Exception:  # noqa: BLE001 — a dropped socket is a failed run
                break
            if isinstance(raw, bytes):
                continue
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            kind = str(msg.get("type") or "")
            if kind == "session.ready":
                send_task = asyncio.create_task(_send())
            elif kind == "assistant_text":
                delta = str(msg.get("delta") or "")
                if delta.strip():
                    events.append({"at": time.monotonic(), "delta": delta})
                    last_text_at = time.monotonic()
            if last_text_at is not None and time.monotonic() - last_text_at > 4.0:
                break

        if send_task is not None and not send_task.done():
            send_task.cancel()

    if not events or t_speech_end is None:
        return {"ok": False, "n_deltas": len(events)}

    def ms(at: float) -> float:
        return round((at - t_speech_end) * 1000, 1)

    narration = [e for e in events if is_narration(e["delta"])]
    answer = [e for e in events if not is_narration(e["delta"])]

    out: dict = {
        "ok": True,
        "first_delta_ms": ms(events[0]["at"]),
        "first_answer_ms": ms(answer[0]["at"]) if answer else None,
        "narration_word_count": sum(len(e["delta"].split()) for e in narration),
        "narration_deltas": [
            {"ms": ms(e["at"]), "text": e["delta"].strip()} for e in narration
        ],
    }
    if narration and answer:
        out["dead_air_covered_ms"] = round(
            ms(answer[0]["at"]) - ms(narration[0]["at"]), 1
        )
        ordered = sorted(events, key=lambda e: e["at"])
        gaps = [
            round((b["at"] - a["at"]) * 1000, 1)
            for a, b in zip(ordered, ordered[1:], strict=False)
        ]
        out["max_gap_ms"] = max(gaps) if gaps else None
    return out
