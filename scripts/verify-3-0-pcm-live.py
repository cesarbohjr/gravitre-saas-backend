#!/usr/bin/env python3
"""Voice-C PCM into the real Pipecat WS (not a physical mic, not lane B).

Synthesizes 16 kHz PCM16 (Windows SAPI when ElevenLabs is absent), speaks it
into /api/voice/pipecat/ws, and records session.ready / transcript / assistant_text.
"""
from __future__ import annotations

import asyncio
import base64
import json
import os
import subprocess
import sys
import tempfile
import time
import uuid
import wave
from array import array
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(ROOT / "scripts"))

from _voice_probe_lib import CHUNK_BYTES, CHUNK_MS, SAMPLE_RATE, service_token, ws_url  # noqa: E402

LIVE_API = os.environ.get("LIVE_API_BASE", "https://api.gravitre.app").rstrip("/")
OUT = ROOT / "docs" / "delivery" / "gravitre-3.0-pcm-live.json"
PHRASE = "Create a HubSpot contact named Gravitre PCM Probe. Do not create it until I approve."


def _load_env() -> None:
    for path in (BACKEND / ".env", ROOT / ".env", BACKEND / ".env.operator.local"):
        if not path.is_file():
            continue
        for enc in ("utf-8", "utf-8-sig", "cp1252"):
            try:
                loaded = dotenv_values(path, encoding=enc)
                break
            except UnicodeDecodeError:
                loaded = {}
        for key, value in loaded.items():
            if value and not os.environ.get(key):
                os.environ[key] = value


def _sapi_pcm16(text: str) -> bytes:
    wav_path = Path(tempfile.gettempdir()) / "gravitre-3-0-pcm-live.wav"
    spoken = text.replace("'", "")
    ps = (
        "Add-Type -AssemblyName System.Speech; "
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        "$s.Rate = -4; "
        f"$s.SetOutputToWaveFile('{wav_path}'); "
        f"$s.Speak('{spoken}'); "
        "$s.Dispose()"
    )
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True, timeout=60)
    with wave.open(str(wav_path), "rb") as handle:
        rate = handle.getframerate()
        channels = handle.getnchannels()
        width = handle.getsampwidth()
        frames = handle.readframes(handle.getnframes())
    if width != 2:
        raise RuntimeError(f"unexpected sample width {width}")
    samples = array("h")
    samples.frombytes(frames)
    if channels == 2:
        samples = array("h", [samples[i] for i in range(0, len(samples), 2)])
    if rate != SAMPLE_RATE:
        ratio = rate / float(SAMPLE_RATE)
        out = array("h")
        n = int(len(samples) / ratio)
        for i in range(n):
            out.append(samples[min(int(i * ratio), len(samples) - 1)])
        samples = out
    return samples.tobytes()


async def _drive(token: str, speech: bytes) -> dict:
    import ssl
    import websockets

    try:
        import certifi

        ssl_ctx: ssl.SSLContext | bool = ssl.create_default_context(cafile=certifi.where())
    except Exception:  # noqa: BLE001
        ssl_ctx = True

    url = ws_url(
        "/api/voice/pipecat/ws",
        {
            "access_token": token,
            "org_id": "f07e57c0-1501-4000-8000-c04e57a00001",
            "conversation_id": str(uuid.uuid4()),
            "audio_origin": "probe_pcm",
        },
    )
    types: list[str] = []
    transcripts: list[str] = []
    assistant: list[str] = []
    ready = False
    t_speech_end = None
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
            for _ in range(int((2.4 * 1000) / CHUNK_MS)):
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

        deadline = time.monotonic() + 75.0
        while time.monotonic() < deadline:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=20.0)
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
            elif kind == "assistant_text":
                delta = str(msg.get("delta") or "").strip()
                if delta:
                    assistant.append(delta)
            if assistant and t_speech_end is not None and time.monotonic() - t_speech_end > 22:
                break
        if send_task is not None and not send_task.done():
            send_task.cancel()
    return {
        "session_ready": ready,
        "types": types[:40],
        "transcripts": transcripts[:8],
        "assistant_text": " ".join(assistant)[:400],
        "spoke": t_speech_end is not None,
        "pcm_bytes": len(speech),
    }


def main() -> int:
    _load_env()
    health = httpx.get(f"{LIVE_API}/health", timeout=45.0).json()
    speech = _sapi_pcm16(PHRASE)
    driven = asyncio.run(_drive(service_token(), speech))
    ok = bool(driven.get("session_ready") and (driven.get("transcripts") or driven.get("assistant_text")))
    report = {
        "probe": "3.0_pcm_live",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "health": {"git_sha": health.get("git_sha"), "timestamp": health.get("timestamp")},
        "proof_class": "SYNTHESIZED_PCM_INTO_PIPECAT_WS",
        "pcm_source": "windows_sapi",
        "phrase": PHRASE,
        "physical_mic": False,
        "lane_b_webrtc": False,
        **driven,
        "pass": ok,
    }
    OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
