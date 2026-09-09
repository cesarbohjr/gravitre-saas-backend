#!/usr/bin/env python3
"""Live Phase 5 verification: response-length adaptation, keyterms, message audit.

Honesty label: real ElevenLabs-synthesized speech into the real deployed
``/api/voice/pipecat/ws``. Real Flux STT, real CognitiveTurnKernel, real
ElevenLabs TTS. NOT a human at a browser mic.

Reports per scenario:
  * every message ``type`` received (counts) — surfaces whether final transcripts
    ever reach the client at all,
  * the final user transcript text if one arrives (keyterm fidelity),
  * the assistant reply and its word count (response-length adaptation).

Credentials from the environment only: SUPABASE_URL, SUPABASE_JWT_SECRET,
ELEVENLABS_API_KEY.

Usage:
  python scripts/verify-voice-phase5-live.py
"""
from __future__ import annotations

import asyncio
import base64
import json
import os
import re
import ssl
import sys
import time
import uuid
from collections import Counter
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

WORD_RE = re.compile(r"[\w'’-]+")

SCENARIOS = [
    # (label, spoken text, expected length band from resolve_response_length_band)
    ("terse_question", "Status?", "terse"),
    ("brief_question", "Did the HubSpot sync finish today?", "brief"),
    (
        "expansive_question",
        "I want to understand the whole picture here, so walk me through what the "
        "operator actually does when a request comes in, what it checks first, and "
        "how it decides whether something needs my approval before it runs.",
        "expansive",
    ),
    (
        "keyterm_utterance",
        "Check the Apollo and HubSpot connectors, then look at the Decision Queue "
        "for anything Gravitre flagged as blocked.",
        None,
    ),
]


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
            "email": "voice-phase5-probe@gravitre.internal",
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


async def _run(token: str, org_id: str, speech: bytes, label: str) -> dict:
    import websockets

    conversation_id = str(uuid.uuid4())
    url = _ws_url(
        "/api/voice/pipecat/ws",
        {"access_token": token, "org_id": org_id, "conversation_id": conversation_id},
    )
    try:
        import certifi

        ssl_ctx: ssl.SSLContext | bool = ssl.create_default_context(cafile=certifi.where())
    except Exception:  # noqa: BLE001
        ssl_ctx = True

    out: dict = {"label": label, "conversation_id": conversation_id, "ok": False}
    kinds: Counter = Counter()
    transcripts: list[dict] = []
    assistant_bits: list[str] = []
    ready: dict | None = None
    last_text_at: float | None = None

    async with websockets.connect(
        url, open_timeout=30, close_timeout=10, max_size=8_000_000, ssl=ssl_ctx
    ) as ws:

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
                raw = await asyncio.wait_for(ws.recv(), timeout=20.0)
            except asyncio.TimeoutError:
                break
            if isinstance(raw, bytes):
                kinds["<binary>"] += 1
                continue
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            kind = str(msg.get("type") or "")
            kinds[kind] += 1

            if kind == "session.ready":
                ready = msg
                send_task = asyncio.create_task(_send_speech())
            elif kind == "transcript":
                transcripts.append(
                    {"text": str(msg.get("text") or ""), "final": bool(msg.get("final"))}
                )
            elif kind == "assistant_text":
                delta = str(msg.get("delta") or "")
                if delta:
                    assistant_bits.append(delta)
                    last_text_at = time.monotonic()
            elif kind == "error":
                out["error_event"] = msg
                break

            # Stop once the reply has clearly stopped growing.
            if last_text_at is not None and time.monotonic() - last_text_at > 4.0:
                break

        if send_task is not None and not send_task.done():
            send_task.cancel()

    reply = "".join(assistant_bits).strip()
    finals = [t for t in transcripts if t["final"]]
    out.update(
        {
            "ok": bool(reply),
            "message_kinds": dict(kinds),
            "n_transcript_msgs": len(transcripts),
            "n_transcript_final": len(finals),
            "final_transcript_text": finals[-1]["text"] if finals else None,
            "interim_transcript_sample": [t["text"] for t in transcripts if not t["final"]][:3],
            "assistant_reply": reply,
            # Spoken-register check: any of these in the client transcript means
            # markdown leaked into a voice turn (measured failure 2026-09-08).
            "markdown_markers": {
                "asterisk": reply.count("*"),
                "backtick": reply.count("`"),
                "heading_or_bullet_line": sum(
                    1
                    for line in reply.split("\n")
                    if line.strip().startswith(("#", "- ", "* ", "+ "))
                ),
            },
            "markdown_clean": "*" not in reply and "`" not in reply,
            "assistant_word_count": len(WORD_RE.findall(reply)),
            "assistant_sentence_count": len([s for s in re.split(r"[.!?]+", reply) if s.strip()]),
            "spoken_prompt_v2_flag": (ready or {}).get("spoken_prompt_v2"),
            "response_length_adapt_flag": (ready or {}).get("response_length_adapt_v1"),
            "keyterms_applied": (ready or {}).get("keyterms_applied"),
            "keyterm_count": (ready or {}).get("keyterm_count"),
            "stt_model": (ready or {}).get("stt_model"),
        }
    )
    return out


def main() -> int:
    token = _service_token(DEFAULT_ACTOR)
    results = []
    for label, text, expected_band in SCENARIOS:
        print(f"[phase5] synthesizing {label}...", flush=True)
        speech = _synthesize(text)
        print(f"[phase5] running {label} ({len(speech)} bytes)...", flush=True)
        res = asyncio.run(_run(token, ISOLATED_ORG, speech, label))
        res["spoken_text_sent"] = text
        res["expected_band"] = expected_band
        results.append(res)
        print(
            f"[phase5] {label}: words={res.get('assistant_word_count')} "
            f"sentences={res.get('assistant_sentence_count')} "
            f"final_transcripts={res.get('n_transcript_final')} "
            f"markdown_clean={res.get('markdown_clean')} "
            f"markers={res.get('markdown_markers')}",
            flush=True,
        )

    out_path = REPO / "docs" / "delivery" / "voice-phase5-live-verification-2026-09-08.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    # ensure_ascii=True on stdout: Windows consoles default to cp1252 and the
    # replies contain curly quotes / em dashes, which raise UnicodeEncodeError.
    print(json.dumps(results, indent=2, ensure_ascii=True))
    print(f"\nwrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
