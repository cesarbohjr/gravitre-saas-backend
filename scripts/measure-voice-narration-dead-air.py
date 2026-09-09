#!/usr/bin/env python3
"""How much silence does tool narration actually cover on a voice turn?

Narration ("Let me check your knowledge base. Found 5.") costs four sentences of
mechanics before the answer on a tool-using turn. Whether that is worth keeping
depends on a number nobody has measured: how long the user would otherwise wait
in silence while the tools run.

This timestamps every ``assistant_text`` delta on a real production turn and
reports the gap between the narration sentences and the first word of the actual
answer. That gap is the dead air narration exists to fill.

Honesty label: real ElevenLabs-synthesized speech into the real deployed
``/api/voice/pipecat/ws``. NOT a human at a browser mic.

Credentials from the environment only: SUPABASE_URL, SUPABASE_JWT_SECRET,
ELEVENLABS_API_KEY.

Usage:
  python scripts/measure-voice-narration-dead-air.py [runs]
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

# A question that reliably drives real tool calls.
UTTERANCE = "Did the HubSpot sync finish today?"

# Narration phrasing comes from voice_tool_narration; anything matching these
# openers is mechanics rather than answer content.
NARRATION_PREFIXES = ("let me check", "found ", "i'm ", "done", "one moment")


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
            "email": "voice-deadair-probe@gravitre.internal",
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
    return urlunparse((scheme, parsed.netloc, path, "", urlencode(params), ""))


def _synthesize(text: str) -> bytes:
    from app.config import get_settings
    from app.services.tier1_voice_service import synthesize_speech_stream

    return b"".join(
        synthesize_speech_stream(get_settings(), text=text, output_format="pcm_16000")
    )


def _is_narration(text: str) -> bool:
    return text.strip().lower().startswith(NARRATION_PREFIXES)


async def _run(token: str, speech: bytes) -> dict:
    import websockets

    url = _ws_url(
        "/api/voice/pipecat/ws",
        {
            "access_token": token,
            "org_id": ISOLATED_ORG,
            "conversation_id": str(uuid.uuid4()),
        },
    )
    try:
        import certifi

        ssl_ctx: ssl.SSLContext | bool = ssl.create_default_context(cafile=certifi.where())
    except Exception:  # noqa: BLE001
        ssl_ctx = True

    events: list[dict] = []
    t_speech_end: float | None = None

    async with websockets.connect(
        url, open_timeout=30, close_timeout=10, max_size=8_000_000, ssl=ssl_ctx
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
        deadline = time.monotonic() + 90.0
        while time.monotonic() < deadline:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=20.0)
            except asyncio.TimeoutError:
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

    narration = [e for e in events if _is_narration(e["delta"])]
    answer = [e for e in events if not _is_narration(e["delta"])]

    out = {
        "ok": True,
        "utterance": UTTERANCE,
        "first_delta_ms": ms(events[0]["at"]),
        "narration_deltas": [
            {"ms": ms(e["at"]), "text": e["delta"].strip()} for e in narration
        ],
        "first_answer_ms": ms(answer[0]["at"]) if answer else None,
        "narration_word_count": sum(len(e["delta"].split()) for e in narration),
    }
    if narration and answer:
        # The window narration is covering: from the first narration sentence to
        # the first word of the real answer.
        out["dead_air_covered_ms"] = round(
            ms(answer[0]["at"]) - ms(narration[0]["at"]), 1
        )
        # Largest single silence between consecutive narration/answer events.
        ordered = sorted(events, key=lambda e: e["at"])
        gaps = [
            round((b["at"] - a["at"]) * 1000, 1)
            for a, b in zip(ordered, ordered[1:], strict=False)
        ]
        out["max_gap_ms"] = max(gaps) if gaps else None
    return out


def main() -> int:
    runs = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    token = _service_token(DEFAULT_ACTOR)
    print(f"[dead-air] synthesizing {UTTERANCE!r}...", flush=True)
    speech = _synthesize(UTTERANCE)

    results = []
    for i in range(runs):
        print(f"[dead-air] run {i + 1}/{runs}...", flush=True)
        res = asyncio.run(_run(token, speech))
        results.append(res)
        print(
            f"  first_delta={res.get('first_delta_ms')}ms "
            f"first_answer={res.get('first_answer_ms')}ms "
            f"dead_air_covered={res.get('dead_air_covered_ms')}ms "
            f"max_gap={res.get('max_gap_ms')}ms "
            f"narration_words={res.get('narration_word_count')}",
            flush=True,
        )

    ok = [r for r in results if r.get("ok")]
    summary = {
        "runs": runs,
        "n_ok": len(ok),
        "dead_air_covered_ms": sorted(
            r["dead_air_covered_ms"] for r in ok if r.get("dead_air_covered_ms") is not None
        ),
        "first_answer_ms": sorted(
            r["first_answer_ms"] for r in ok if r.get("first_answer_ms") is not None
        ),
        "narration_word_counts": [r.get("narration_word_count") for r in ok],
    }
    out_path = REPO / "docs" / "delivery" / "voice-narration-dead-air-2026-09-08.json"
    out_path.write_text(
        json.dumps({"summary": summary, "runs": results}, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )
    print("\n" + json.dumps(summary, indent=2), flush=True)
    print(f"wrote {out_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
