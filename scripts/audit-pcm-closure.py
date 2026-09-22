#!/usr/bin/env python3
"""PCM evidence closure: capture interrupts, user-llm-text, audio, assistant_text."""
from __future__ import annotations

import asyncio
import base64
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
import importlib.util

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

spec = importlib.util.spec_from_file_location(
    "pcm_src", ROOT / "scripts" / "verify-3-0-pcm-live.py"
)
mod = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(mod)

from _voice_probe_lib import CHUNK_BYTES, CHUNK_MS, SAMPLE_RATE, service_token, ws_url  # noqa: E402

LIVE_API = os.environ.get("LIVE_API_BASE", "https://api.gravitre.app").rstrip("/")
OUT = ROOT / "docs" / "audits" / "gravitre-pcm-closure-live.json"
ORG = "f07e57c0-1501-4000-8000-c04e57a00001"


async def _drive(token: str, speech: bytes) -> dict:
    import ssl
    import uuid

    import websockets

    try:
        import certifi

        ssl_ctx = ssl.create_default_context(cafile=certifi.where())
    except Exception:  # noqa: BLE001
        ssl_ctx = True

    url = ws_url(
        "/api/voice/pipecat/ws",
        {
            "access_token": token,
            "org_id": ORG,
            "conversation_id": str(uuid.uuid4()),
            "audio_origin": "probe_pcm",
        },
    )
    types: list[str] = []
    transcripts: list[str] = []
    assistant: list[str] = []
    user_llm: list[str] = []
    ready = False
    t_speech_end = None
    t_stt_final = None
    t_first_assistant = None
    t_first_audio = None
    audio_frames = 0
    interrupts = 0
    bot_llm_stopped = False
    async with websockets.connect(
        url, open_timeout=30, close_timeout=10, max_size=8_000_000, ssl=ssl_ctx
    ) as ws:
        send_task = None

        async def _send() -> None:
            nonlocal t_speech_end
            for i in range(0, len(speech), CHUNK_BYTES):
                await ws.send(
                    json.dumps(
                        {
                            "type": "audio",
                            "pcm16_b64": base64.b64encode(speech[i : i + CHUNK_BYTES]).decode(
                                "ascii"
                            ),
                            "sample_rate": SAMPLE_RATE,
                            "num_channels": 1,
                            "audio_origin": "probe_pcm",
                        }
                    )
                )
                await asyncio.sleep(CHUNK_MS / 1000)
            t_speech_end = time.monotonic()
            silence = base64.b64encode(b"\x00" * CHUNK_BYTES).decode("ascii")
            for _ in range(int((1.2 * 1000) / CHUNK_MS)):
                await ws.send(
                    json.dumps(
                        {
                            "type": "audio",
                            "pcm16_b64": silence,
                            "sample_rate": SAMPLE_RATE,
                            "num_channels": 1,
                            "audio_origin": "probe_pcm",
                        }
                    )
                )
                await asyncio.sleep(CHUNK_MS / 1000)

        deadline = time.monotonic() + 90.0
        while time.monotonic() < deadline:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=25.0)
            except asyncio.TimeoutError:
                break
            except Exception:  # noqa: BLE001
                break
            if isinstance(raw, bytes):
                types.append("_binary")
                continue
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                types.append("_non_json")
                continue
            kind = str(msg.get("type") or "")
            types.append(kind)
            if kind == "session.ready" and send_task is None:
                ready = True
                send_task = asyncio.create_task(_send())
            elif kind == "transcript":
                text = str(msg.get("text") or msg.get("delta") or "").strip()
                if text:
                    transcripts.append(text)
                    if t_stt_final is None:
                        t_stt_final = time.monotonic()
            elif kind == "assistant_text":
                delta = str(msg.get("delta") or "").strip()
                if delta:
                    assistant.append(delta)
                    if t_first_assistant is None:
                        t_first_assistant = time.monotonic()
            elif kind == "user-llm-text":
                t = str(msg.get("text") or msg.get("delta") or "").strip()
                if t:
                    user_llm.append(t)
            elif kind in {"audio", "voice.audio.delta"}:
                audio_frames += 1
                if t_first_audio is None:
                    t_first_audio = time.monotonic()
            elif "interrupt" in kind:
                interrupts += 1
            elif kind == "bot-llm-stopped":
                bot_llm_stopped = True
            if bot_llm_stopped and t_speech_end is not None:
                if time.monotonic() - t_speech_end > 12:
                    break
        if send_task is not None and not send_task.done():
            send_task.cancel()

    def rel(ts):
        if ts is None or t_speech_end is None:
            return None
        return int((ts - t_speech_end) * 1000)

    return {
        "session_ready": ready,
        "types": types[:60],
        "transcripts": transcripts[:8],
        "assistant_text": " ".join(assistant)[:400],
        "user_llm_text": user_llm[:6],
        "spoke": t_speech_end is not None,
        "pcm_bytes": len(speech),
        "audio_frames": audio_frames,
        "interrupt_events": interrupts,
        "bot_llm_stopped": bot_llm_stopped,
        "ms_speech_end_to_stt_final": rel(t_stt_final),
        "ms_speech_end_to_first_assistant_text": rel(t_first_assistant),
        "ms_speech_end_to_first_audio": rel(t_first_audio),
        "empty_assistant_text": not bool(" ".join(assistant).strip()),
    }


def main() -> int:
    mod._load_env()
    health = httpx.get(f"{LIVE_API}/health", timeout=45.0).json()
    speech = mod._sapi_pcm16(mod.PHRASE)
    driven = asyncio.run(_drive(service_token(), speech))
    report = {
        "probe": "pcm_closure",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "health": {"git_sha": health.get("git_sha"), "timestamp": health.get("timestamp")},
        "proof_class": "SYNTHESIZED_PCM_INTO_PIPECAT_WS",
        "physical_mic": False,
        "phrase": mod.PHRASE,
        **driven,
    }
    OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2)[:4000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
