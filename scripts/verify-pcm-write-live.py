#!/usr/bin/env python3
"""Synthetic PCM → Pipecat: stage, ambiguous, confirm WRITE, duplicate, follow-up.

Not a physical microphone. Same conversation_id throughout.
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
from typing import Any

import httpx
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(ROOT / "scripts"))

from _voice_probe_lib import CHUNK_BYTES, CHUNK_MS, SAMPLE_RATE, service_token, ws_url  # noqa: E402
from isolated_conversation_org import (  # noqa: E402
    resolve_isolated_conversation_actor,
    smoke_http_headers,
)

LIVE_API = os.environ.get("LIVE_API_BASE", "https://api.gravitre.app").rstrip("/")
OUT = ROOT / "docs" / "delivery" / "gravitre-pcm-write-live.json"
ISOLATED_ORG = "f07e57c0-1501-4000-8000-c04e57a00001"


def _load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
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
            if value:
                merged.setdefault(key, value)
                if not os.environ.get(key):
                    os.environ[key] = value
    return merged


def _sapi_pcm16(text: str) -> bytes:
    wav_path = Path(tempfile.gettempdir()) / "gravitre-pcm-write.wav"
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


async def _send_pcm(ws, speech: bytes, *, trailing_silence_s: float = 3.2) -> None:
    for i in range(0, len(speech), CHUNK_BYTES):
        await ws.send(
            json.dumps(
                {
                    "type": "audio",
                    "pcm16_b64": base64.b64encode(speech[i : i + CHUNK_BYTES]).decode("ascii"),
                    "sample_rate": SAMPLE_RATE,
                    "num_channels": 1,
                    "audio_origin": "probe_pcm",
                }
            )
        )
        await asyncio.sleep(CHUNK_MS / 1000)
    silence = base64.b64encode(b"\x00" * CHUNK_BYTES).decode("ascii")
    for _ in range(int((trailing_silence_s * 1000) / CHUNK_MS)):
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


async def _collect(ws, *, settle_s: float, deadline_s: float, require_assistant: bool) -> dict:
    types: list[str] = []
    transcripts: list[str] = []
    assistant: list[str] = []
    t0 = time.monotonic()
    last_text = time.monotonic()
    while time.monotonic() - t0 < deadline_s:
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=14.0)
        except asyncio.TimeoutError:
            if assistant and time.monotonic() - last_text > settle_s:
                break
            if (not require_assistant) and time.monotonic() - t0 > 10 and not assistant:
                break
            continue
        if isinstance(raw, bytes):
            types.append("_binary")
            continue
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            continue
        kind = str(msg.get("type") or "")
        types.append(kind)
        if kind == "transcript":
            text = str(msg.get("text") or msg.get("delta") or "").strip()
            if text:
                transcripts.append(text)
        elif kind == "assistant_text":
            delta = str(msg.get("delta") or "").strip()
            if delta:
                assistant.append(delta)
                last_text = time.monotonic()
        if assistant and time.monotonic() - last_text > settle_s:
            break
    return {
        "types": types[:48],
        "transcripts": transcripts[:8],
        "assistant_text": " ".join(assistant)[:1800],
        "elapsed_ms": int((time.monotonic() - t0) * 1000),
    }


async def _session(token: str, conv: str, utterances: list[tuple[str, bytes]]) -> dict:
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
            "org_id": ISOLATED_ORG,
            "conversation_id": conv,
            "audio_origin": "probe_pcm",
        },
    )
    turns: dict[str, Any] = {}
    ready = False
    async with websockets.connect(
        url, open_timeout=30, close_timeout=15, max_size=8_000_000, ssl=ssl_ctx
    ) as ws:
        while not ready:
            raw = await asyncio.wait_for(ws.recv(), timeout=25.0)
            if isinstance(raw, bytes):
                continue
            msg = json.loads(raw)
            if str(msg.get("type") or "") == "session.ready":
                ready = True
        for name, pcm in utterances:
            await _send_pcm(ws, pcm, trailing_silence_s=3.6 if name == "confirm" else 3.0)
            require = name in {"stage", "ambiguous", "confirm", "duplicate", "follow"}
            settle = 45.0 if name == "confirm" else (22.0 if name == "stage" else 12.0)
            deadline = 130.0 if name == "confirm" else 70.0
            turns[name] = await _collect(
                ws,
                settle_s=settle,
                deadline_s=deadline,
                require_assistant=require,
            )
            await asyncio.sleep(3.5)
    return {"session_ready": ready, "turns": turns}


def main() -> int:
    env = _load_env()
    from supabase import create_client

    sb = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
    org_id, user_id, email = resolve_isolated_conversation_actor(env, sb)
    health = httpx.get(f"{LIVE_API}/health", timeout=45.0).json()
    tag = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    conv = str(uuid.uuid4())
    probe_email = f"gravitre-pcm-write-{tag}@alpha.test.gravitre.app"
    name = f"Gravitre PCM Write {tag}"
    phrases = {
        "stage": f"Create a HubSpot contact named {name} with email {probe_email}. Do not create it until I approve.",
        "ambiguous": "yes maybe",
        "confirm": "Yes, create it.",
        "duplicate": "yes",
        "follow": "Did that contact already get created?",
    }
    pcms = {key: _sapi_pcm16(text) for key, text in phrases.items()}
    token = service_token(user_id)
    json_headers = {
        **smoke_http_headers(),
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "x-org-id": org_id,
    }
    created = httpx.post(
        f"{LIVE_API}/api/conversations",
        headers=json_headers,
        json={"title": f"pcm-write-{tag}", "id": conv},
        timeout=60,
    )
    if created.status_code < 400:
        body = created.json() or {}
        conv = str(body.get("id") or conv)
    driven = asyncio.run(
        _session(
            token,
            conv,
            [
                ("stage", pcms["stage"]),
                ("ambiguous", pcms["ambiguous"]),
                ("confirm", pcms["confirm"]),
                ("duplicate", pcms["duplicate"]),
                ("follow", pcms["follow"]),
            ],
        )
    )
    state = httpx.get(
        f"{LIVE_API}/api/assistant/conversation/{conv}/state",
        headers=json_headers,
        timeout=60,
    )
    task_state = (state.json() or {}).get("task_state") if state.status_code == 200 else {}
    plan = (task_state or {}).get("execution_plan") if isinstance(task_state, dict) else {}
    pending = (task_state or {}).get("pending_task") if isinstance(task_state, dict) else {}
    obs = (task_state or {}).get("execution_observations") if isinstance(task_state, dict) else []
    last_obs = obs[-1] if isinstance(obs, list) and obs else {}
    confirm_text = str((driven.get("turns") or {}).get("confirm", {}).get("assistant_text") or "")
    amb_text = str((driven.get("turns") or {}).get("ambiguous", {}).get("assistant_text") or "")
    dup_text = str((driven.get("turns") or {}).get("duplicate", {}).get("assistant_text") or "")
    follow_text = str((driven.get("turns") or {}).get("follow", {}).get("assistant_text") or "")
    stage_text = str((driven.get("turns") or {}).get("stage", {}).get("assistant_text") or "")
    report = {
        "probe": "pcm_pipecat_write",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "proof_class": "SYNTHESIZED_PCM_INTO_PIPECAT_WS",
        "physical_mic": False,
        "health_sha": health.get("git_sha"),
        "org_id": org_id,
        "actor_email": email,
        "conversation_id": conv,
        "probe_email": probe_email,
        "probe_name": name,
        "prior_placeholder_contact_id": "278972733388",
        "conversation_create_http": created.status_code,
        "session_ready": driven.get("session_ready"),
        "turns": driven.get("turns"),
        "state_http": state.status_code,
        "pending_status": pending.get("status") if isinstance(pending, dict) else None,
        "plan_id": plan.get("plan_id") if isinstance(plan, dict) else None,
        "plan_terminal": plan.get("terminal_status") if isinstance(plan, dict) else None,
        "observation_success": last_obs.get("success") if isinstance(last_obs, dict) else None,
        "identity_in_approval": probe_email in stage_text or name in stage_text,
        "ambiguous_no_create_claim": "confirmed" not in amb_text.lower() and "created" not in amb_text.lower(),
        "confirm_verified": "confirmed" in confirm_text.lower() or "verified" in confirm_text.lower(),
        "duplicate_blocked": "already" in dup_text.lower() or "not running" in dup_text.lower(),
        "follow_used_observation": probe_email in follow_text or "created" in follow_text.lower(),
        "robotic_on_it": "on it" in (stage_text + confirm_text).lower(),
    }
    OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "turns"}, indent=2))
    print(json.dumps(report.get("turns"), indent=2)[:8000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
