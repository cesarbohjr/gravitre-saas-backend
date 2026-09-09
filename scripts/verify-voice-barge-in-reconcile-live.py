#!/usr/bin/env python3
"""Live barge-in probe for Phase 5 played-audio reconciliation.

Honesty label: this sends REAL ElevenLabs-synthesized speech into the REAL
deployed ``/api/voice/pipecat/ws``, lets the agent start speaking, then sends a
REAL ``{"type":"interrupt"}`` mid-playback and captures the resulting
``speech.interrupted`` payload. It is NOT a human speaking into a browser mic, so
it excludes browser capture overhead and human barge-in timing. It DOES exercise
the real STT, the real CognitiveTurnKernel, the real ElevenLabs TTS WebSocket,
and the real SpokenTextTapProcessor / ElevenLabsInterruptReporter path.

What it proves (or disproves): whether ``spoken_source`` is ``tap_ledger`` and
whether ``dropped_chars > 0``. A ``draft_fallback`` source or zero dropped chars
means reconciliation is still inert.

Credentials are read from the environment only (never written to disk). Required:
  SUPABASE_URL, SUPABASE_JWT_SECRET, ELEVENLABS_API_KEY

Usage:
  python scripts/verify-voice-barge-in-reconcile-live.py
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
sys.path.insert(0, str(REPO / "backend"))

BASE = os.environ.get("BACKEND_URL", "https://api.gravitre.app").rstrip("/")
ISOLATED_ORG = "f07e57c0-1501-4000-8000-c04e57a00001"
DEFAULT_ACTOR = "a9f1240f-910a-42ca-aebf-38caeac288c3"

SAMPLE_RATE = 16000
CHUNK_MS = 20
CHUNK_BYTES = int(SAMPLE_RATE * 2 * (CHUNK_MS / 1000))
TRAILING_SILENCE_S = 1.3

# Long enough that the agent is still mid-answer when we cut in, so there is a
# real unheard tail to drop.
PROMPT = "Explain in a few sentences what the Gravitre operator does day to day."
# How long to let the agent speak before barging in.
SPEAK_BEFORE_INTERRUPT_S = float(os.environ.get("BARGE_IN_AFTER_S", "2.0"))


def _service_token(actor_id: str) -> str:
    url = (os.environ.get("SUPABASE_URL") or "").rstrip("/")
    secret = (os.environ.get("SUPABASE_JWT_SECRET") or "").strip()
    if not url or not secret:
        raise SystemExit("SUPABASE_URL and SUPABASE_JWT_SECRET required")
    import jwt

    now = int(time.time())
    return jwt.encode(
        {
            "sub": actor_id,
            "email": "voice-bargein-probe@gravitre.internal",
            "aud": "authenticated",
            "iss": f"{url}/auth/v1",
            "iat": now,
            "exp": now + 3600,
            "role": "authenticated",
        },
        secret,
        algorithm="HS256",
    )


def _ws_url(path: str, params: dict[str, str]) -> str:
    parsed = urlparse(BASE)
    scheme = "wss" if parsed.scheme == "https" else "ws"
    return urlunparse(
        (scheme, parsed.netloc, path, "", urlencode({k: v for k, v in params.items() if v}), "")
    )


def _synthesize(text: str) -> bytes:
    from app.config import get_settings
    from app.services.tier1_voice_service import synthesize_speech_stream

    return b"".join(
        synthesize_speech_stream(get_settings(), text=text, output_format="pcm_16000")
    )


async def _run(token: str, org_id: str, conversation_id: str, speech: bytes) -> dict:
    import websockets

    url = _ws_url(
        "/api/voice/pipecat/ws",
        {"access_token": token, "org_id": org_id, "conversation_id": conversation_id},
    )
    out: dict = {"ok": False, "conversation_id": conversation_id}
    try:
        import certifi

        ssl_ctx: ssl.SSLContext | bool = ssl.create_default_context(cafile=certifi.where())
    except Exception:  # noqa: BLE001
        ssl_ctx = True

    async with websockets.connect(
        url, open_timeout=30, close_timeout=10, max_size=8_000_000, ssl=ssl_ctx
    ) as ws:
        ready: dict | None = None
        assistant_bits: list[str] = []
        first_audio_at: float | None = None
        interrupt_sent_at: float | None = None
        audio_frames = 0
        all_reports: list[dict] = []

        async def _send_speech() -> None:
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
        deadline = time.monotonic() + 90.0
        while time.monotonic() < deadline:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=25.0)
            except asyncio.TimeoutError:
                out["timeout"] = True
                break
            if isinstance(raw, bytes):
                continue
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            kind = str(msg.get("type") or "")

            if kind == "session.ready":
                ready = msg
                send_task = asyncio.create_task(_send_speech())
            elif kind == "assistant_text":
                delta = str(msg.get("delta") or "")
                if delta:
                    assistant_bits.append(delta)
            elif kind == "audio":
                audio_frames += 1
                if first_audio_at is None:
                    first_audio_at = time.monotonic()
                # Let real playback progress so the tap records spoken words,
                # then cut in exactly like a browser barge-in would.
                if (
                    interrupt_sent_at is None
                    and time.monotonic() - first_audio_at >= SPEAK_BEFORE_INTERRUPT_S
                ):
                    offset_ms = round((time.monotonic() - first_audio_at) * 1000)
                    await ws.send(
                        json.dumps({"type": "interrupt", "playback_offset_ms": offset_ms})
                    )
                    interrupt_sent_at = time.monotonic()
                    out["playback_offset_ms_sent"] = offset_ms
            elif kind == "speech.interrupted":
                # Flux fires its own interruption when the *user* starts speaking,
                # before any agent audio exists. That payload is empty and is not
                # what we are testing — keep every one, but only finish on a report
                # that arrives after our own mid-playback interrupt was sent.
                all_reports.append(msg)
                if interrupt_sent_at is not None:
                    out["ok"] = True
                    out["speech_interrupted"] = msg
                    break
            elif kind == "error":
                out["error_event"] = msg
                break

        if send_task is not None and not send_task.done():
            send_task.cancel()

        out["session_ready"] = ready is not None
        out["played_audio_reconcile_v1_flag"] = (ready or {}).get("played_audio_reconcile_v1")
        out["tts_model"] = (ready or {}).get("tts_model")
        out["stt_model"] = (ready or {}).get("stt_model")
        out["audio_frames_before_break"] = audio_frames
        out["assistant_text_draft"] = "".join(assistant_bits)[:600]
        out["all_speech_interrupted_reports"] = all_reports
        out["interrupt_was_sent"] = interrupt_sent_at is not None
    return out


def main() -> int:
    token = _service_token(DEFAULT_ACTOR)
    conversation_id = str(uuid.uuid4())
    print(f"synthesizing probe speech: {PROMPT!r}", flush=True)
    speech = _synthesize(PROMPT)
    print(f"speech bytes={len(speech)} conversation_id={conversation_id}", flush=True)
    result = asyncio.run(_run(token, ISOLATED_ORG, conversation_id, speech))
    print(json.dumps(result, indent=2, default=str))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
